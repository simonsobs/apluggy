import asyncio
import contextlib
from collections.abc import AsyncGenerator, Sequence
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Sequence[AGenCtxMngr[T]]) -> AGenCtxMngr[list[T]]:
    match len(ctxs):
        case 0:
            return nested_with_null(ctxs)
        case 1:
            return nested_with_single(ctxs)
        case 2:
            return nested_with_double(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.asynccontextmanager
async def nested_with_null(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert not ctxs
    yield []


@contextlib.asynccontextmanager
async def nested_with_single(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
    async with ctx as y:
        sent = yield [y]
        try:
            while True:
                sent = yield [await ctx.gen.asend(sent)]
        except StopAsyncIteration:
            pass


@contextlib.asynccontextmanager
async def nested_with_double(
    ctxs: Sequence[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    async with ctx0 as y0, ctx1 as y1:
        sent = yield [y0, y1]
        try:
            while True:
                sent = yield list(
                    await asyncio.gather(ctx1.gen.asend(sent), ctx0.gen.asend(sent))
                )
        except StopAsyncIteration:
            pass
