import contextlib
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


def async_stack_nested_with(ctxs: Iterable[AGenCtxMngr[T]]) -> AGenCtxMngr[list[T]]:
    '''A reference implementation of `async_stack_gen_ctxs` for tests.'''
    ctxs = list(ctxs)
    if not ctxs:
        return async_stack_nested_with_null(ctxs)
    if len(ctxs) == 1:
        return async_stack_nested_with_single(ctxs)
    if len(ctxs) == 2:
        return async_stack_nested_with_double(ctxs)
    if len(ctxs) == 3:
        return async_stack_nested_with_triple(ctxs)
    raise NotImplementedError()


@contextlib.asynccontextmanager
async def async_stack_nested_with_null(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert not ctxs
    yield []


@contextlib.asynccontextmanager
async def async_stack_nested_with_single(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
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
async def async_stack_nested_with_double(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    async with ctx0 as y0, ctx1 as y1:
        sent = yield [y0, y1]
        try:
            while True:
                sent = yield [
                    await ctx1.gen.asend(sent),
                    await ctx0.gen.asend(sent),
                ]
        except StopAsyncIteration:
            pass


@contextlib.asynccontextmanager
async def async_stack_nested_with_triple(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    async with ctx0 as y0, ctx1 as y1, ctx2 as y2:
        sent = yield [y0, y1, y2]
        try:
            while True:
                sent = yield [
                    await ctx2.gen.asend(sent),
                    await ctx1.gen.asend(sent),
                    await ctx0.gen.asend(sent),
                ]
        except StopAsyncIteration:
            pass
