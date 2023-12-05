import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Sequence
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


def dunder_enter(ctxs: Sequence[AGenCtxMngr[T]]) -> AGenCtxMngr[list[T]]:
    match len(ctxs):
        case 0:
            return dunder_enter_null(ctxs)
        case 1:
            return dunder_enter_single(ctxs)
        case 2:
            return dunder_enter_double(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.asynccontextmanager
async def dunder_enter_null(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert not ctxs
    yield []


@contextlib.asynccontextmanager
async def dunder_enter_single(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
    y = await ctx.__aenter__()
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
async def _dunder_enter_double(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    y0 = await ctx0.__aenter__()
    try:
        y1 = await ctx1.__aenter__()
        try:
            sent = yield [y0, y1]
            try:
                while True:
                    sent = yield list(
                        await asyncio.gather(ctx1.gen.asend(sent), ctx0.gen.asend(sent))
                    )
            except StopAsyncIteration:
                pass
        except BaseException:
            if not await ctx1.__aexit__(*sys.exc_info()):
                raise
        else:
            await ctx1.__aexit__(None, None, None)
    except BaseException:
        if not await ctx0.__aexit__(*sys.exc_info()):
            raise
    else:
        await ctx0.__aexit__(None, None, None)


@contextlib.asynccontextmanager
async def dunder_enter_double(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    try:
        try:
            sent = yield list(await asyncio.gather(_enter(ctx0), _enter(ctx1)))
            try:
                while True:
                    sent = yield list(
                        await asyncio.gather(ctx1.gen.asend(sent), ctx0.gen.asend(sent))
                    )
            except StopAsyncIteration:
                pass
        except BaseException:
            if ctx1 not in entered:
                raise
            ic()
            ic(sys.exc_info())
            if not await ctx1.__aexit__(*sys.exc_info()):
                ic()
                raise
        else:
            if ctx1 in entered:
                await ctx1.__aexit__(None, None, None)
    except BaseException:
        ic()
        ic(sys.exc_info())
        if ctx0 not in entered:
            raise
        if not await ctx0.__aexit__(*sys.exc_info()):
            raise
    else:
        if ctx0 in entered:
            await ctx0.__aexit__(None, None, None)
