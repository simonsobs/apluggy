import asyncio
from collections.abc import Callable
from typing import Any, Coroutine

from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_

from apluggy.stack import AGenCtxMngr, GenCtxMngr, async_stack_gen_ctxs, stack_gen_ctxs


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

    def __getattr__(self, name: str) -> Callable[..., GenCtxMngr[list]]:
        hook: HookCaller = getattr(self.pm.hook, name)

        def call(*args: Any, **kwargs: Any) -> GenCtxMngr[list]:
            ctxs = hook(*args, **kwargs)
            if self.reverse:
                ctxs = list(reversed(ctxs))
            return stack_gen_ctxs(ctxs)

        return call


class AWith:
    def __init__(self, pm: PluginManager_, reverse: bool = False) -> None:
        self.pm = pm
        self.reverse = reverse

    def __getattr__(self, name: str) -> Callable[..., AGenCtxMngr]:
        hook: HookCaller = getattr(self.pm.hook, name)

        def call(*args: Any, **kwargs: Any) -> AGenCtxMngr[list]:
            ctxs = hook(*args, **kwargs)
            if self.reverse:
                ctxs = list(reversed(ctxs))

            # TODO: Make `sequential` configurable.  It is set to `True` for
            # now because nextline-graphql doesn't work with `False`.
            return async_stack_gen_ctxs(ctxs, sequential=True)

        return call
