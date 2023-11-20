import contextlib
from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any, Optional

from exceptiongroup import BaseExceptionGroup
from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_

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
            return _cm_gen(ctxs)

        return call


@contextlib.contextmanager
def _cm_gen(ctxs: list[GenCtxManager]) -> Generator[list, Any, list]:
    with contextlib.ExitStack() as stack:
        yields = [stack.enter_context(ctx) for ctx in ctxs]

        # yield yields

        # This function could end here with the above line uncommented
        # for a normal usage of context managers.

        # Instead, yield from another generator method that supports
        # `send()` and `throw()` and returns the return values of the
        # hook implementations.

        # NOTE: ExitStack correctly executes the code after the yield
        # statement in the reverse order of entering the contexts and
        # propagates exceptions from inner contexts to outer contexts.
        # _support_gen() executes the code after the first yield in the
        # reverse order. _support_gen() doesn't propagate the exceptions in
        # the same way as ExitStack.

        returns = yield from _support_gen(yields, ctxs)
    return returns


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
        for c in reversed(contexts):  # close in the reversed order after yielding
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
