import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


@contextlib.asynccontextmanager
async def async_stack_gen_ctxs(
    ctxs: Iterable[AGenCtxMngr[T]],
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
        # Yield at least once even if an empty `ctxs` is given.
        # Receive a value from the `with` block sent by `gen.asend()`.
        sent = yield [await _enter(ctx) for ctx in ctxs]

        if ctxs:
            try:
                # Send the received value to the async context managers
                # until at least one of them exits.
                while True:
                    sent = yield [await ctx.gen.asend(sent) for ctx in reversed(ctxs)]
            except StopAsyncIteration:
                # An async context manager exited.
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
