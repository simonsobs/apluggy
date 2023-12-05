import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from apluggy.stack.aexit import patch_aexit

from .types import AGenCtxMngr

T = TypeVar('T')


@contextlib.asynccontextmanager
async def async_stack_gen_ctxs(
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool = True,
    sequential: bool = False,
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)

    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    with contextlib.ExitStack() as stack:
        if fix_reraise:
            for ctx in ctxs:
                stack.enter_context(patch_aexit(ctx))

        try:
            if sequential:
                ys = [await _enter(ctx) for ctx in ctxs]
            else:
                ys = await asyncio.gather(*[_enter(ctx) for ctx in ctxs])
            sent = yield ys
            if ctxs:
                try:
                    while True:
                        if sequential:
                            ys = [await ctx.gen.asend(sent) for ctx in reversed(ctxs)]
                        else:
                            ys = await asyncio.gather(
                                *[ctx.gen.asend(sent) for ctx in reversed(ctxs)]
                            )
                        sent = yield ys
                except StopAsyncIteration:
                    pass

        except BaseException:
            exc_info = sys.exc_info()
        else:
            exc_info = (None, None, None)
        finally:
            for ctx in reversed(ctxs):
                if ctx not in entered:
                    continue
                try:
                    if await ctx.__aexit__(*exc_info):
                        exc_info = (None, None, None)
                except BaseException:
                    exc_info = sys.exc_info()
            if isinstance(exc_info[1], BaseException):
                raise exc_info[1].with_traceback(exc_info[2])
