import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any, AsyncContextManager

from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_


class AWith:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., AsyncContextManager]:
        hook: HookCaller = getattr(self.pm.hook, name)
        return _Call(hook)


class AWithReverse:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., AsyncContextManager]:
        hook: HookCaller = getattr(self.pm.hook, name)
        return _Call(hook, reverse=True)


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

    return call
