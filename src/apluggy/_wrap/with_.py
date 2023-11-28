import contextlib
from collections.abc import Callable
from typing import Any

from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_

from ..gen import stack_gen_ctxs

GenCtxManager = contextlib._GeneratorContextManager


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
