import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


@contextlib.asynccontextmanager
async def async_stack_gen_ctxs(
    ctxs: Iterable[AGenCtxMngr[T]], sequential: bool = True
) -> AsyncGenerator[list[T], Any]:
    '''Manage multiple async context managers with the support of the `gen` attribute.

    The async version of `stack_gen_ctxs()`.
    '''
    ctxs = list(ctxs)

    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    try:
        # Enter the async context managers
        if sequential:
            ys = [await _enter(ctx) for ctx in ctxs]
        else:
            ys = await asyncio.gather(*[_enter(ctx) for ctx in ctxs])

        # Yield at least once even if an empty `ctxs` is given.
        # Receive a value from the `with` block sent by `gen.asend()`.
        sent = yield ys

        if ctxs:
            try:
                # Send the received value to the async context managers
                # until at least one of them exits.
                while True:
                    if sequential:
                        ys = [await ctx.gen.asend(sent) for ctx in reversed(ctxs)]
                    else:
                        ys = await asyncio.gather(
                            *[ctx.gen.asend(sent) for ctx in reversed(ctxs)]
                        )
                    sent = yield ys
            except StopAsyncIteration:
                # An async context manager exited.

                # TODO: When `sequential` is `False`, some `asend()` tasks can be
                # still running.  It is probably necessary to wait for them before
                # exiting the async context manager.

                pass

    except BaseException:
        exc_info = sys.exc_info()
    else:
        exc_info = (None, None, None)
    finally:
        # Exit the async context managers sequentially in the reverse order.
        for ctx in reversed(ctxs):
            if ctx not in entered:
                continue
            try:
                if await ctx.__aexit__(*exc_info):
                    exc_info = (None, None, None)
            except BaseException:
                exc_info = sys.exc_info()

        if isinstance(exc_info[1], BaseException):
            # An exception is unhandled after all async context managers have exited.
            raise exc_info[1].with_traceback(exc_info[2])
