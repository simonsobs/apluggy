import apluggy as pluggy
from apluggy import asynccontextmanager, contextmanager

hookspec = pluggy.HookspecMarker('myproject')
hookimpl = pluggy.HookimplMarker('myproject')


@hookspec
def func(arg1, arg2):
    pass


@hookspec
async def afunc(arg1, arg2):
    pass


@hookspec
@contextmanager
def context(arg1, arg2):
    yield


@hookspec
@asynccontextmanager
async def acontext(arg1, arg2):
    yield
