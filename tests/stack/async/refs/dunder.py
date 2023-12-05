import asyncio
import contextlib
import sys
from collections.abc import AsyncGenerator, Iterable
from typing import Any, TypeVar

from apluggy.stack import patch_aexit

from .types import AGenCtxMngr

T = TypeVar('T')


def dunder_enter(
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool = True,
    sequential: bool = False,
) -> AGenCtxMngr[list[T]]:
    ctxs = list(ctxs)
    match len(ctxs):
        case 0:
            return dunder_enter_null(ctxs)
        case 1:
            return dunder_enter_single(ctxs, fix_reraise=fix_reraise)
        case 2:
            return dunder_enter_double(
                ctxs, fix_reraise=fix_reraise, sequential=sequential
            )
        case 3:
            return dunder_enter_triple(
                ctxs, fix_reraise=fix_reraise, sequential=sequential
            )
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
    sequential: bool = False,
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    with contextlib.ExitStack() as stack:
        if fix_reraise:
            stack.enter_context(patch_aexit(ctx0))
            stack.enter_context(patch_aexit(ctx1))
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
async def dunder_enter_triple(  # noqa: C901
    ctxs: Iterable[AGenCtxMngr[T]],
    fix_reraise: bool,
    sequential: bool = False,
) -> AsyncGenerator[list[T], Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    entered = set[AGenCtxMngr[T]]()

    async def _enter(ctx: AGenCtxMngr[T]) -> T:
        y = await ctx.__aenter__()
        entered.add(ctx)
        return y

    with contextlib.ExitStack() as stack:
        if fix_reraise:
            stack.enter_context(patch_aexit(ctx0))
            stack.enter_context(patch_aexit(ctx1))
            stack.enter_context(patch_aexit(ctx2))
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
                            await asyncio.gather(
                                _enter(ctx0), _enter(ctx1), _enter(ctx2)
                            )
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
