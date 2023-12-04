import contextlib
from collections.abc import AsyncGenerator, Generator
from typing import NoReturn, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')
U = TypeVar('U')


@contextlib.contextmanager
def patch_aexit(ctx: AGenCtxMngr[T]):
    '''Make `__aexit__()` re-raise just like (sync) generator's `__exit__()` does.

    Replace the `gen` attribute of the async context manager during the `__aexit__()`
    call so that an exception is re-raised if the generator is exhausted.

    This function doesn't work with `async with`. `__aexit__()` must be called
    explicitly. `async with` doesn't call the instance's `__aexit__()`.
    Instead, it calls the `__aexit__()` from the class definition, e.g.,
    `type(ctx).__aexit__()` (PEP 492).

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

    async def athrow(self, typ, val=None, tb=None) -> NoReturn:
        await self._wrapped.athrow(typ, val, tb)
        # athrow() didn't raise.
        try:
            await anext(self._wrapped)  # Check if the generator is exhausted.
        except StopAsyncIteration:
            # The generator is exhausted. But don't raise the exception
            # instance raised by anext() because __aexit__() distinguishes
            # the instances of StopAsyncIteration. Raise the original
            # exception instead.
            pass
        if isinstance(typ, type):  # The old signature deprecated in 3.12
            raise val.with_traceback(tb)
        raise typ  # The only argument is val in the new signature

    async def aclose(self) -> None:
        await self._wrapped.aclose()
