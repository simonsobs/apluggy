import contextlib
import sys
from collections.abc import AsyncGenerator, Generator
from typing import TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')
U = TypeVar('U')

if sys.version_info < (3, 10):

    async def anext(ait):
        return await ait.__anext__()


@contextlib.contextmanager
def patch_aexit(ctx: AGenCtxMngr[T]):
    '''Make `__aexit__()` re-raise just like (sync) generator's `__exit__()` does.

        TODO: Deprecate this patch. This patch doesn't work with `async with`
        because it doesn't call the instance's `__aexit__()` but the class's
        `__aexit__()` as `type(ctx).__aexit__()` (PEP 492).


    The problem that this function solves is that, unlike a (sync) context
    manager, an async context manager doesn't raise the same exception at the
    exit if the `asend()` method of the `gen` attribute is used.

    We will demonstrate the problem with an example.

    This is the exception that we will raise:
    >>> exc = ValueError('exc')

    This (sync) context manager raises the exception after the `yield`:
    >>> @contextlib.contextmanager
    ... def ctx():
    ...     yield
    ...     raise exc

    The exception is raised at the exit when the `send()` method of the `gen`
    attribute is used:
    >>> try:
    ...     with (c := ctx()):
    ...         c.gen.send('sent')
    ... except Exception as _e:
    ...     e = _e
    >>> e is exc
    True

    This is not the case with an async context manager.

    This async context manager raises the exception after the `yield`:
    >>> @contextlib.asynccontextmanager
    ... async def actx():
    ...     yield
    ...     raise exc

    The same exception is not raised at the exit when the `asend()` method of the
    `gen` attribute is used:
    >>> async def main():
    ...     try:
    ...         async with (ac := actx()):
    ...             await ac.gen.asend('sent')
    ...     except Exception as _e:
    ...         e = _e
    ...     return e
    >>> import asyncio
    >>> e = asyncio.run(main())

    The exception raised at the exit is not the same as the one raised inside
    the `async with` block:
    >>> e is exc
    False

    A RuntimeError is raised instead:
    >>> e
    RuntimeError(...)

    This will make debugging difficult when an async context manager raises an
    exception.

    This function patches the `__aexit__()` method so that it re-raises the
    same exception.

    However, unfortunately, we will need to call `__aexit__()` explicitly
    because `async with` doesn't call the instance's `__aexit__()`. Instead, it
    calls the `__aexit__()` from the class definition, i.e.,
    `type(ctx).__aexit__()` (PEP 492).

    >>> import sys
    >>> async def main():
    ...     ac = actx()
    ...     try:
    ...         with patch_aexit(ac):
    ...             await ac.__aenter__()
    ...             try:
    ...                 await ac.gen.asend('sent')
    ...             except Exception:
    ...                 if not await ac.__aexit__(*sys.exc_info()):
    ...                     raise
    ...             else:
    ...                 await ac.__aexit__(None, None, None)
    ...     except Exception as _e:
    ...         e = _e
    ...     return e
    >>> e = asyncio.run(main())


    The exception raised by `__aexit__()` is the same as the one raised inside
    >>> e is exc
    True
    '''
    _org_aexit = ctx.__aexit__

    async def aexit(*exc_info):
        with _wrap_gen(ctx):
            return await _org_aexit(*exc_info)

    ctx.__aexit__ = aexit  # type: ignore
    try:
        yield
    finally:
        ctx.__aexit__ = _org_aexit  # type: ignore


@contextlib.contextmanager
def _wrap_gen(ctx: AGenCtxMngr[T]) -> Generator[None, None, None]:
    _org_gen = ctx.gen
    ctx.gen = AGenWrapForAexit(_org_gen)
    try:
        yield
    finally:
        ctx.gen = _org_gen


class AGenWrapForAexit(AsyncGenerator[T, U]):
    '''Patch `athrow()` to re-raise if the generator is exhausted.

    This class is intended to be used during the execution of `__aexit__()`

    '''

    def __init__(self, agen: AsyncGenerator[T, U]):
        self._wrapped = agen

    async def asend(self, value: U) -> T:
        return await self._wrapped.asend(value)

    async def athrow(self, typ, val=None, tb=None):
        # `athrow()` is called by `__aexit__()` when an exception is raised.

        await self._wrapped.athrow(typ, val, tb)
        # `athrow()` didn't raise, which implies two possibilities:
        # 1. The generator is not exhausted and the exception is handled.
        # 2. The generator is exhausted.
        #
        # The second possibility is different from the sync generator's
        # `throw()`, which re-raises the same exception if the generator is
        # exhausted.
        #
        # We will check if the generator is exhausted by calling `anext()`. If
        # the generator is exhausted, we will re-raised the exception.
        try:
            await anext(self._wrapped)
        except StopAsyncIteration:
            # The generator is exhausted. But don't raise the exception
            # instance raised by anext() because __aexit__() distinguishes
            # the instances of StopAsyncIteration. Raise the original
            # exception instead.

            # TODO: Consider catching Exception instead of StopAsyncIteration, in which
            # case we re-raised the original exception if `anext()` raises any exception.

            # NOTE: It is possible that the generator wasn't in fact exhausted
            # after `athrow()` was called and then exhausted after `anext()`,
            # in which case, the behavior is not perfectly consistent with
            # sync generator's `throw()`.

            if isinstance(typ, type):  # The old signature deprecated in Python 3.12
                raise val.with_traceback(tb)
            raise typ  # The only argument is val in the new signature

        # The generator is not exhausted. The exception is handled. `__aexit__()` will
        # raise RuntimeError("generator didn't stop after athrow()")

    async def aclose(self) -> None:
        await self._wrapped.aclose()
