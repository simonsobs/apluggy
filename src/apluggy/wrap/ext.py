import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any, AsyncContextManager, Coroutine

from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_

from ..gen import stack_gen_ctxs

GenCtxManager = contextlib._GeneratorContextManager


class AHook:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, list]]:
        async def call(*args: Any, **kwargs: Any) -> list:
            hook: HookCaller = getattr(self.pm.hook, name)
            coros: list[asyncio.Future] = hook(*args, **kwargs)
            return await asyncio.gather(*coros)

        return call


class With:
    def __init__(self, pm: PluginManager_, reverse: bool = False) -> None:
        self.pm = pm
        self.reverse = reverse

    def __getattr__(self, name: str) -> Callable[..., GenCtxManager[list]]:
        hook: HookCaller = getattr(self.pm.hook, name)

        def call(*args: Any, **kwargs: Any) -> GenCtxManager[list]:
            ctxs = hook(*args, **kwargs)
            if self.reverse:
                ctxs = list(reversed(ctxs))
            return stack_gen_ctxs(ctxs)

        return call


class AWith:
    def __init__(self, pm: PluginManager_, reverse: bool = False) -> None:
        self.pm = pm
        self.reverse = reverse

    def __getattr__(self, name: str) -> Callable[..., AsyncContextManager]:
        hook: HookCaller = getattr(self.pm.hook, name)
        return _Call(hook, reverse=self.reverse)


def _Call(
    hook: Callable[..., list[AsyncContextManager]], reverse: bool = False
) -> Callable[..., AsyncContextManager]:
    @contextlib.asynccontextmanager
    async def call(*args: Any, **kwargs: Any) -> AsyncIterator[list]:
        ctxs = hook(*args, **kwargs)
        if reverse:
            ctxs = list(reversed(ctxs))
        async with contextlib.AsyncExitStack() as stack:
            yields = [await stack.enter_async_context(ctx) for ctx in ctxs]

            # TODO: Consider entering the contexts asynchronously as in the
            # following commented out code.

            # yields = await asyncio.gather(
            #     *[stack.enter_async_context(ctx) for ctx in ctxs]
            # )

            yield yields

            # TODO: The following commented out code is an attempt to support
            # `asend()` through the `gen` attribute. It only works for
            # simple cases. It doesn't work with starlette.lifespan().
            # When starlette is shutting down, an exception is raised
            # `RuntimeError: generator didn't stop after athrow()`.

            # stop = False
            # while not stop:
            #     sent = yield yields
            #     try:
            #         yields = await asyncio.gather(
            #             *[ctx.gen.asend(sent) for ctx in ctxs]
            #         )
            #     except StopAsyncIteration:
            #         stop = True

    return call
