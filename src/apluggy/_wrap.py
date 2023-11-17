'''Extend pluggy.PluginManager.

It supports async hooks and context managers.
It accepts plugin factories in addition to plugins themselves for registration.

pluggy: https://pluggy.readthedocs.io/en/stable/

>>> import apluggy as pluggy
>>> from apluggy import asynccontextmanager, contextmanager

>>> hookspec = pluggy.HookspecMarker('project')
>>> hookimpl = pluggy.HookimplMarker('project')

>>> class Spec:
...     """A hook specification namespace."""
...
...     @hookspec
...     async def afunc(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @contextmanager
...     def context(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         pass

>>> class Plugin_1:
...     """A hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_1.afunc()')
...         return arg1 + arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_1.context()')
...         yield arg1 + arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_1.acontext()')
...         yield arg1 + arg2

>>> class Plugin_2:
...     """A 2nd hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_2.afunc()')
...         return arg1 - arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_2.context()')
...         yield arg1 - arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_2.acontext()')
...         yield arg1 - arg2

>>> pm = pluggy.PluginManager('project')
>>> pm.add_hookspecs(Spec)
>>> _ = pm.register(Plugin_1())  # instantiation is optional.
>>> _ = pm.register(Plugin_2)  # callable is considered a plugin factory.

>>> async def call_afunc():
...     results = await pm.ahook.afunc(arg1=1, arg2=2)  # ahook instead of hook
...     print(results)

>>> asyncio.run(call_afunc())
inside Plugin_2.afunc()
inside Plugin_1.afunc()
[-1, 3]

>>> with pm.with_.context(arg1=1, arg2=2) as y:  # with_ instead of hook
...     print(y)
inside Plugin_2.context()
inside Plugin_1.context()
[-1, 3]

>>> async def call_acontext():
...     async with pm.awith.acontext(arg1=1, arg2=2) as y:  # awith instead of hook
...         print(y)

>>> asyncio.run(call_acontext())
inside Plugin_2.acontext()
inside Plugin_1.acontext()
[-1, 3]

'''

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable, Generator
from dataclasses import dataclass
from typing import Any, AsyncContextManager, Coroutine, Optional

from exceptiongroup import BaseExceptionGroup
from pluggy import HookCaller
from pluggy import PluginManager as PluginManager_
from pluggy._hooks import _Plugin


class _AHook:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., Coroutine[Any, Any, list]]:
        async def call(*args: Any, **kwargs: Any) -> list:
            hook: HookCaller = getattr(self.pm.hook, name)
            coros: list[asyncio.Future] = hook(*args, **kwargs)
            return await asyncio.gather(*coros)

        return call


class _With:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(
        self, name: str
    ) -> Callable[..., contextlib._GeneratorContextManager]:
        @contextlib.contextmanager
        def call(*args: Any, **kwargs: Any) -> Generator[list, Any, list]:
            hook = getattr(self.pm.hook, name)
            with contextlib.ExitStack() as stack:
                hook_impls = hook(*args, **kwargs)
                yields = [stack.enter_context(imp) for imp in hook_impls]

                # yield yields

                # This function could end here with the above line uncommented
                # for a normal usage of context managers.

                # Instead, yield from another generator method that supports
                # `send()` and `throw()` and returns the return values of the
                # hook implementations.

                returns = yield from self._support_gen(yields, hook_impls)
            return returns

        return call

    def _support_gen(
        self, yields: list, hook_impls: list[contextlib._GeneratorContextManager]
    ) -> Generator[list, Any, list]:
        '''This generator method
        1. supports `send()` through the `gen` attribute
           (https://stackoverflow.com/a/68304565/7309855),
        2. supports `throw()` through the `gen` attribute,
        3. and returns the return values of the hook implementations.

        TODO: Support `close()`.
        '''

        @dataclass
        class _Context:
            context: contextlib._GeneratorContextManager
            stop_iteration: Optional[StopIteration] = None

        contexts = [_Context(context=imp) for imp in hook_impls]

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
                returns = [
                    c.stop_iteration and c.stop_iteration.value for c in contexts
                ]
                return returns


class _AWith:
    def __init__(self, pm: PluginManager_) -> None:
        self.pm = pm

    def __getattr__(self, name: str) -> Callable[..., AsyncContextManager]:
        @contextlib.asynccontextmanager
        async def call(*args: Any, **kwargs: Any) -> AsyncIterator[list]:
            hook: HookCaller = getattr(self.pm.hook, name)
            async with contextlib.AsyncExitStack() as stack:
                ctxs: list[AsyncContextManager] = hook(*args, **kwargs)
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


class PluginManager(PluginManager_):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.ahook = _AHook(self)
        self.with_ = _With(self)
        self.awith = _AWith(self)

    def register(
        self, plugin: _Plugin | Callable[[], _Plugin], name: Optional[str] = None
    ) -> None:
        if callable(plugin):
            plugin = plugin()
        super().register(plugin, name=name)

    def get_canonical_name(self, plugin: _Plugin) -> str:
        '''Override to include class names in plugin names.'''
        if name := getattr(plugin, '__name__', None):
            # a module
            return name
        if class_ := getattr(plugin, '__class__', None):
            # a class instance
            # NOTE: Class definitions are instantiated in register()
            if name := getattr(class_, '__name__', None):
                # add the id so that multiple instances can be registered
                return f'{name}_{id(plugin)}'
        return str(id(plugin))
