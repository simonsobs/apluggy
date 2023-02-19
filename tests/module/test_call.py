import pytest

from apluggy import PluginManager

from . import plugin1, plugin2, spec


def test_hook(pm: PluginManager):
    assert pm.hook.func(arg1=1, arg2=2) == [-1, 3]


async def test_ahook(pm: PluginManager):
    assert await pm.ahook.afunc(arg1=1, arg2=2) == [-1, 3]


def test_with(pm: PluginManager):
    with pm.with_.context(arg1=1, arg2=2) as r:
        assert r == [-1, 3]


async def test_awith(pm: PluginManager):
    async with pm.awith.acontext(arg1=1, arg2=2) as r:
        assert r == [-1, 3]


@pytest.fixture
def pm():
    r = PluginManager('myproject')
    r.add_hookspecs(spec)
    r.register(plugin1)
    r.register(plugin2)
    return r
