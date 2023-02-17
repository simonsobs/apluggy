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

from pluggy import PluginManager as PluginManager_


class _AHook:
    def __init__(self, pm: PluginManager_):
        self.pm = pm

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            hook = getattr(self.pm.hook, name)
            coros = hook(*args, **kwargs)
            return await asyncio.gather(*coros)

        return call


class _With:
    def __init__(self, pm: PluginManager_):
        self.pm = pm

    def __getattr__(self, name):
        @contextlib.contextmanager
        def call(*args, **kwargs):
            hook = getattr(self.pm.hook, name)
            with contextlib.ExitStack() as stack:
                contexts = hook(*args, **kwargs)
                y = [stack.enter_context(context) for context in contexts]
                yield y

        return call


class _AWith:
    def __init__(self, pm: PluginManager_):
        self.pm = pm

    def __getattr__(self, name):
        @contextlib.asynccontextmanager
        async def call(*args, **kwargs):
            hook = getattr(self.pm.hook, name)
            async with contextlib.AsyncExitStack() as stack:
                contexts = hook(*args, **kwargs)
                y = [await stack.enter_async_context(context) for context in contexts]
                yield y

        return call


class PluginManager(PluginManager_):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ahook = _AHook(self)
        self.with_ = _With(self)
        self.awith = _AWith(self)

    def register(self, plugin, name=None):
        if callable(plugin):
            plugin = plugin()
        super().register(plugin, name=name)
