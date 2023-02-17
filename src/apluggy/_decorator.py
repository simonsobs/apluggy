'''Implement asynccontextmanager in the same way as decorator.contextmanager.

decorator: https://pypi.org/project/decorator/


>>> import asyncio
>>> import inspect
>>> import contextlib
>>> from apluggy import asynccontextmanager

With the original `asynccontextmanager` from `contextlib`:

>>> @contextlib.asynccontextmanager
... async def context(arg1, arg2):
...     yield arg1 + arg2

the arguments signature becomes `(*args, **kwds)`:

>>> inspect.getfullargspec(context)
FullArgSpec(args=[], varargs='args', varkw='kwds', ...)


With the `asynccontextmanager` from this module:

>>> @asynccontextmanager
... async def context(arg1, arg2):
...     yield arg1 + arg2

the arguments signature is preserved:

>>> inspect.getfullargspec(context)
FullArgSpec(args=['arg1', 'arg2'], varargs=None, varkw=None, ...)

It runs as expected:

>>> async def main():
...     async with context(1, 2) as result:
...         print(result)
...
>>> asyncio.run(main())
3

'''

__all__ = ['asynccontextmanager']

import contextlib

from decorator import decorate, decorator


class AsyncContextManager(contextlib._AsyncGeneratorContextManager):
    def __init__(self, g, *a, **k):
        super().__init__(g, a, k)

    def __call__(self, func):
        async def caller(f, *a, **k):
            async with self.__class__(self.func, *self.args, **self.kwds):
                return f(*a, **k)

        return decorate(func, caller)


_asynccontextmanager = decorator(AsyncContextManager)


def asynccontextmanager(func):
    return _asynccontextmanager(func)
