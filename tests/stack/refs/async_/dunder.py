import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from .types import AGenCtxMngr

T = TypeVar('T')


def async_stack_dunder_enter(
    ctxs: Iterable[AGenCtxMngr[T]], sequential: bool = True
) -> AGenCtxMngr[list[T]]:
    '''A reference implementation of `async_stack_gen_ctxs` for tests.'''
    ctxs = list(ctxs)
    if not ctxs:
        return async_stack_dunder_enter_null(ctxs)
    if len(ctxs) == 1:
        return async_stack_dunder_enter_single(ctxs)
    if len(ctxs) == 2:
        return async_stack_dunder_enter_double(ctxs, sequential=sequential)
    if len(ctxs) == 3:
        return async_stack_dunder_enter_triple(ctxs, sequential=sequential)
    raise NotImplementedError()


@contextlib.asynccontextmanager
async def async_stack_dunder_enter_null(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert not ctxs
    yield []


@contextlib.asynccontextmanager
async def async_stack_dunder_enter_single(
    ctxs: Iterable[AGenCtxMngr[T]],
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
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
async def async_stack_dunder_enter_double(
    ctxs: Iterable[AGenCtxMngr[T]], sequential: bool = True
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    try:
        try:
            if sequential:
                ys = [await _enter(ctx0), await _enter(ctx1)]
            else:
                ys = list(await asyncio.gather(_enter(ctx0), _enter(ctx1)))
            sent = yield ys
            try:
                while True:
                    if sequential:
                        ys = [
                            await ctx1.gen.asend(sent),
                            await ctx0.gen.asend(sent),
                        ]
                    else:
                        ys = list(
                            await asyncio.gather(
                                ctx1.gen.asend(sent),
                                ctx0.gen.asend(sent),
                            )
                        )
                    sent = yield ys
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


@contextlib.asynccontextmanager
async def async_stack_dunder_enter_triple(  # noqa: C901
    ctxs: Iterable[AGenCtxMngr[T]], sequential: bool = True
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    try:
        try:
            try:
                if sequential:
                    ys = [
                        await _enter(ctx0),
                        await _enter(ctx1),
                        await _enter(ctx2),
                    ]
                else:
                    ys = list(
                        await asyncio.gather(_enter(ctx0), _enter(ctx1), _enter(ctx2))
                    )
                sent = yield ys
                try:
                    while True:
                        if sequential:
                            ys = [
                                await ctx2.gen.asend(sent),
                                await ctx1.gen.asend(sent),
                                await ctx0.gen.asend(sent),
                            ]
                        else:
                            ys = list(
                                await asyncio.gather(
                                    ctx2.gen.asend(sent),
                                    ctx1.gen.asend(sent),
                                    ctx0.gen.asend(sent),
                                )
                            )
                        sent = yield ys
                except StopAsyncIteration:
                    pass
            except BaseException:
                if ctx2 not in entered:
                    raise
                if not await ctx2.__aexit__(*sys.exc_info()):
                    raise
            else:
                if ctx2 in entered:
                    await ctx2.__aexit__(None, None, None)
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
