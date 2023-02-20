from typing import ContextManager, Generator, List, Optional

import pytest
from exceptiongroup import BaseExceptionGroup
from hypothesis import given
from hypothesis import strategies as st

import apluggy as pluggy
from apluggy import contextmanager

hookspec = pluggy.HookspecMarker('project')
hookimpl = pluggy.HookimplMarker('project')


class Spec:
    @hookspec
    @contextmanager
    def hook(self):
        pass


class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `contextmanager.gen.throw()`.
    '''

    pass


class Raised(Exception):
    '''To be rased by the context manager when it catches `Thrown`.'''

    def __init__(self, thrown: Thrown):
        self.thrown = thrown


@contextmanager
def context(
    yields: List[str], expected_receives: List[str], ret: Optional[str], handle: bool
) -> Generator[str, str, Optional[str]]:
    '''To be hooked as hook implementation in plugins.'''

    # If multiple items to yield, expect receive some values via
    # contextmanager.gen.send() except for the last yield.
    assert len(yields[:-1]) == len(expected_receives)
    for y, expected in zip(yields[:-1], expected_receives):
        received = yield y
        assert received == expected

    try:
        yield yields[-1]
    except Thrown as thrown:
        if handle:
            pass
        else:
            raise Raised(thrown)
    return ret


class Plugin:
    def __init__(
        self,
        yields: List[str],
        expected_receives: List[str],
        ret: Optional[str],
        handle: bool,
    ):
        self._yields = yields
        self._expected_receives = expected_receives
        self._ret = ret
        self._handle = handle

    def bare(self) -> ContextManager[str]:
        return context(
            yields=self._yields,
            expected_receives=self._expected_receives,
            ret=self._ret,
            handle=self._handle,
        )

    hook = hookimpl(bare)


def check_context(
    yields: List[str], sends: List[str], ret: Optional[str], throw: bool, handle: bool
):
    '''Test context() by itself without being hooked in a plugin.'''
    c = context(yields=yields, expected_receives=sends, ret=ret, handle=handle)
    with c as yielded:
        assert yields[0] == yielded

        assert len(sends) == len(yields[1:])
        for s, expected in zip(sends, yields[1:]):
            yielded = c.gen.send(s)
            assert expected == yielded

        if throw:
            thrown = Thrown()
            if handle:
                with pytest.raises(StopIteration):
                    c.gen.throw(thrown)
            else:
                with pytest.raises(Raised) as excinfo_raised:
                    c.gen.throw(thrown)
                assert excinfo_raised.type is Raised
                assert excinfo_raised.value.thrown == thrown

        elif ret is not None:
            with pytest.raises(StopIteration) as excinfo_ret:
                c.gen.send(None)
            assert ret == excinfo_ret.value.value


@given(st.data())
def test_context(data: st.DataObject):
    test_send = True
    test_throw = True

    n_yields = data.draw(st.integers(min_value=1, max_value=10)) if test_send else 1
    n_sends = n_yields - 1

    yields = data.draw(
        st.lists(st.text(), min_size=n_yields, max_size=n_yields, unique=True)
    )
    sends = data.draw(
        st.lists(st.text(), min_size=n_sends, max_size=n_sends, unique=True)
    )

    throw = data.draw(st.booleans()) if test_throw else False
    handle = data.draw(st.booleans()) if throw else False

    ret = data.draw(st.one_of(st.none(), st.text())) if not throw else None

    if not test_send:
        assert len(yields) == 1
        assert len(sends) == 0

    if not test_throw:
        assert not throw
        assert not handle

    check_context(yields=yields, sends=sends, ret=ret, throw=throw, handle=handle)


@given(st.data())
def test_one(data: st.DataObject):
    test_send = True
    test_throw = True

    n_yields = data.draw(st.integers(min_value=1, max_value=10)) if test_send else 1
    n_sends = n_yields - 1

    yields = data.draw(
        st.lists(st.text(), min_size=n_yields, max_size=n_yields, unique=True)
    )
    sends = data.draw(
        st.lists(st.text(), min_size=n_sends, max_size=n_sends, unique=True)
    )

    throw = data.draw(st.booleans()) if test_throw else False
    handle = data.draw(st.booleans()) if throw else False

    ret = data.draw(st.one_of(st.none(), st.text())) if not throw else None

    if not test_send:
        assert len(yields) == 1
        assert len(sends) == 0

    if not test_throw:
        assert not throw
        assert not handle

    check_context(yields=yields, sends=sends, ret=ret, throw=throw, handle=handle)

    pm = pluggy.PluginManager('project')
    pm.add_hookspecs(Spec)

    for _ in range(2):
        plugin = Plugin(yields=yields, expected_receives=sends, ret=ret, handle=handle)
        _ = pm.register(plugin)

    with (c := pm.with_.hook()) as yielded:
        assert [yields[0]] * 2 == yielded
        assert len(sends) == len(yields[1:])

        for s, expected in zip(sends, yields[1:]):
            yielded = c.gen.send(s)
            assert [expected] * 2 == yielded

        if throw:
            thrown = Thrown()
            with pytest.raises((Thrown, BaseExceptionGroup)) as excinfo_throw:
                c.gen.throw(thrown)
            if handle:
                assert excinfo_throw.type is Thrown
            else:
                assert isinstance(excinfo_throw.value, BaseExceptionGroup)
                assert all(
                    [
                        isinstance(e, Raised) and e.thrown == thrown
                        for e in excinfo_throw.value.exceptions
                    ]
                )
        elif ret is not None:
            with pytest.raises(StopIteration) as excinfo_ret:
                c.gen.send(None)
            assert [ret, ret] == excinfo_ret.value.value
