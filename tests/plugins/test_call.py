import pytest

from apluggy import PluginManager, asynccontextmanager, contextmanager

from . import module_plugin, spec


class ClassPlugin:
    @spec.hookimpl
    def func(self, arg1, arg2):
        return arg1 - arg2

    @spec.hookimpl
    async def afunc(self, arg1, arg2):
        return arg1 - arg2

    @spec.hookimpl
    @contextmanager
    def context(self, arg1, arg2):
        yield arg1 - arg2

    @spec.hookimpl
    @asynccontextmanager
    async def acontext(self, arg1, arg2):
        yield arg1 - arg2


instance_plugin = ClassPlugin()


def test_hook(pm: PluginManager):
    assert pm.hook.func(arg1=1, arg2=2) == [-1, -1, 3]


async def test_ahook(pm: PluginManager):
    assert await pm.ahook.afunc(arg1=1, arg2=2) == [-1, -1, 3]


def test_with(pm: PluginManager):
    with pm.with_.context(arg1=1, arg2=2) as r:
        assert r == [-1, -1, 3]


def test_with_reverse(pm: PluginManager):
    with pm.with_reverse.context(arg1=1, arg2=2) as r:
        assert r == [3, -1, -1]


async def test_awith(pm: PluginManager):
    async with pm.awith.acontext(arg1=1, arg2=2) as r:
        assert r == [-1, -1, 3]


def test_name(pm: PluginManager):
    id_ = id(pm.list_name_plugin()[1][1])  # the object id of the 2nd plugin

    expected = [
        module_plugin.__name__,
        f'{instance_plugin.__class__.__name__}_{id_}',
        f'{instance_plugin.__class__.__name__}_{id(instance_plugin)}',
    ]
    assert [n for n, _ in pm.list_name_plugin()] == expected


@pytest.fixture
def pm():
    _pm = PluginManager('myproject')
    _pm.add_hookspecs(spec)
    _pm.register(module_plugin)
    _pm.register(ClassPlugin)
    _pm.register(instance_plugin)
    return _pm
