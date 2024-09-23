from collections.abc import Callable
from typing import Any, Optional, Union

from pluggy import PluginManager as PluginManager_
from pluggy._hooks import _Plugin

from .ext import AHook, AWith, With


class PluginManager(PluginManager_):
    '''Extend pluggy.PluginManager.

    It supports async hooks and context managers.
    It accepts plugin factories in addition to plugins themselves for registration.

    pluggy: https://pluggy.readthedocs.io/en/stable/

    >>> import asyncio
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.ahook = AHook(self)
        self.with_ = With(self)
        self.with_reverse = With(self, reverse=True)
        self.awith = AWith(self)
        self.awith_reverse = AWith(self, reverse=True)

    def register(
        self, plugin: Union[_Plugin, Callable[[], _Plugin]], name: Optional[str] = None
    ) -> Union[str, None]:
        if callable(plugin):
            plugin = plugin()
        return super().register(plugin, name=name)

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
