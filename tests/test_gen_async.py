import pytest

import apluggy as pluggy
from apluggy import wrap, asynccontextmanager

hookspec = pluggy.HookspecMarker('project')
hookimpl = pluggy.HookimplMarker('project')


class Spec:
    @hookspec
    @asynccontextmanager
    async def context(self, arg):
        pass


class Plugin_1:
    @hookimpl
    @asynccontextmanager
    async def context(self, arg):
        n = yield
        assert n is None
        y = arg
        s = yield y
        y += s
        s = yield y
        assert n is None


@pytest.mark.skip(reason=f'The implementation is commented out in {wrap.__name__}')
async def test_asend():

    pm = pluggy.PluginManager('project')
    pm.add_hookspecs(Spec)
    _ = pm.register(Plugin_1())

    async with (c := pm.awith.context(arg=1)) as y:
        assert [None] == y
        y = await c.gen.asend(None)
        assert [1] == y
        y = await c.gen.asend(2)
        assert [3] == y
