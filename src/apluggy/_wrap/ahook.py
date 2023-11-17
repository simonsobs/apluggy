import asyncio
from collections.abc import Callable
from typing import Any, Coroutine

from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_


class AHook:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, list]]:
        async def call(*args: Any, **kwargs: Any) -> list:
            hook: HookCaller = getattr(self.pm.hook, name)
            coros: list[asyncio.Future] = hook(*args, **kwargs)
            return await asyncio.gather(*coros)

        return call
