import apluggy as pluggy
from apluggy import contextmanager

hookspec = pluggy.HookspecMarker('project')
hookimpl = pluggy.HookimplMarker('project')


class Spec:
    @hookspec
    @contextmanager
    def context(self, arg):
        pass


class Plugin_1:
    @hookimpl
    @contextmanager
    def context(self, arg):
        n = yield
        assert n is None
        y = arg
        s = yield y
        y += s
        s = yield y
        assert n is None

        return y


def test_send():

    pm = pluggy.PluginManager('project')
    pm.add_hookspecs(Spec)
    _ = pm.register(Plugin_1())

    with (c := pm.with_.context(arg=1)) as y:
        assert [None] == y
        y = c.gen.send(None)
        assert [1] == y
        y = c.gen.send(2)
        assert [3] == y


def test_return():

    pm = pluggy.PluginManager('project')
    pm.add_hookspecs(Spec)
    _ = pm.register(Plugin_1())

    with (c := pm.with_.context(arg=1)) as y:
        assert [None] == y
        y = c.gen.send(None)
        assert [1] == y
        y = c.gen.send(2)
        assert [3] == y

        try:
            c.gen.send(3)
        except StopIteration as e:
            assert [3] == e.value
