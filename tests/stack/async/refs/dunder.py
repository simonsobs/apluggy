import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar


from apluggy.stack import patch_aexit

from .types import AGenCtxMngr

T = TypeVar('T')


def dunder_enter(
    ctxs: Iterable[AGenCtxMngr[T]], fix_reraise: bool = True
) -> AGenCtxMngr[list[T]]:
    ctxs = list(ctxs)
    match len(ctxs):
        case 0:
            return dunder_enter_null(ctxs)
        case 1:
            return dunder_enter_single(ctxs, fix_reraise=fix_reraise)
        case 2:
            return dunder_enter_double(ctxs, fix_reraise=fix_reraise)
        case _:
            raise NotImplementedError()


@contextlib.asynccontextmanager
async def dunder_enter_null(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert not ctxs
    yield []


@contextlib.asynccontextmanager
async def dunder_enter_single(
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool,
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 1
    ctx = ctxs[0]
    y = await ctx.__aenter__()
    with patch_aexit(ctx) if fix_reraise else contextlib.nullcontext():
        try:
            sent = yield [y]
            try:
                while True:
                    sent = yield [await ctx.gen.asend(sent)]
            except StopAsyncIteration:
                pass
        except BaseException:
            if not await ctx.__aexit__(*sys.exc_info()):
                raise
        else:
            await ctx.__aexit__(None, None, None)


@contextlib.asynccontextmanager
async def dunder_enter_double(
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool,
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    with patch_aexit(ctx0) if fix_reraise else contextlib.nullcontext():
        with patch_aexit(ctx1) if fix_reraise else contextlib.nullcontext():
            try:
                try:
                    sent = yield list(await asyncio.gather(_enter(ctx0), _enter(ctx1)))
                    try:
                        while True:
                            sent = yield list(
                                await asyncio.gather(
                                    ctx1.gen.asend(sent), ctx0.gen.asend(sent)
                                )
                            )
                    except StopAsyncIteration:
                        pass
                except BaseException:
                    if ctx1 not in entered:
                        raise
                    if not await ctx1.__aexit__(*sys.exc_info()):
                        raise
                else:
                    if ctx1 in entered:
                        await ctx1.__aexit__(None, None, None)
            except BaseException:
                if ctx0 not in entered:
                    raise
                if not await ctx0.__aexit__(*sys.exc_info()):
                    raise
            else:
                if ctx0 in entered:
                    await ctx0.__aexit__(None, None, None)
