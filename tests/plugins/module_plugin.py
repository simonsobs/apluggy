from contextlib import asynccontextmanager, contextmanager

from . import spec


@spec.hookimpl
def func(arg1, arg2):
    return arg1 + arg2


@spec.hookimpl
async def afunc(arg1, arg2):
    return arg1 + arg2


@spec.hookimpl
@contextmanager
def context(arg1, arg2):
    yield arg1 + arg2


@spec.hookimpl
@asynccontextmanager
async def acontext(arg1, arg2):
    yield arg1 + arg2
