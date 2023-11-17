import contextlib
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any, Optional

from exceptiongroup import BaseExceptionGroup
from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_

GenCtxManager = contextlib._GeneratorContextManager


class With:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., GenCtxManager]:
        hook: HookCaller = getattr(self.pm.hook, name)
        return _Call(hook)


class WithReverse:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., GenCtxManager]:
        hook: HookCaller = getattr(self.pm.hook, name)
        return _Call(hook, reverse=True)


def _Call(
    hook: Callable[..., list[GenCtxManager]], reverse: bool = False
) -> Callable[..., GenCtxManager]:
    @contextlib.contextmanager
    def call(*args: Any, **kwargs: Any) -> Generator[list, Any, list]:
        ctxs = hook(*args, **kwargs)
        if reverse:
            ctxs = list(reversed(ctxs))
        with contextlib.ExitStack() as stack:
            yields = [stack.enter_context(ctx) for ctx in ctxs]

            # yield yields

            # This function could end here with the above line uncommented
            # for a normal usage of context managers.

            # Instead, yield from another generator method that supports
            # `send()` and `throw()` and returns the return values of the
            # hook implementations.

            returns = yield from _support_gen(yields, ctxs)
        return returns

    return call


def _support_gen(yields: list, ctxs: list[GenCtxManager]) -> Generator[list, Any, list]:
    '''This generator method
    1. supports `send()` through the `gen` attribute
       (https://stackoverflow.com/a/68304565/7309855),
    2. supports `throw()` through the `gen` attribute,
    3. and returns the return values of the hook implementations.

    TODO: Support `close()`.
    '''

    @dataclass
    class _Context:
        context: GenCtxManager
        stop_iteration: Optional[StopIteration] = None

    contexts = [_Context(context=ctx) for ctx in ctxs]

    while True:
        try:
            sent = yield yields
        except BaseException as thrown:
            # gen.throw() has been called.
            # Throw the exception to all hook implementations
            # that have not exited.
            raised: list[BaseException] = []
            for c in contexts:
                if c.stop_iteration:
                    continue
                try:
                    c.context.gen.throw(thrown)
                except StopIteration:
                    pass
                except BaseException as e:
                    raised.append(e)
            if raised:
                raise BaseExceptionGroup('Raised in hook implementations.', raised)
            raise

        yields = []
        for c in contexts:
            y = None
            if not c.stop_iteration:
                try:
                    y = c.context.gen.send(sent)
                except StopIteration as e:
                    c.stop_iteration = e
            yields.append(y)

        if all(c.stop_iteration for c in contexts):
            # All hook implementations have exited.
            # Collect return values from StopIteration.
            returns = [c.stop_iteration and c.stop_iteration.value for c in contexts]
            return returns
