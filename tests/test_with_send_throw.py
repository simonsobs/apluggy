from itertools import zip_longest
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

    # NOTE: A context manager normally yields exactly once. However, it is possible
    # to yield multiple times to receive some values via contextmanager.gen.send().
    # (https://stackoverflow.com/a/68304565/7309855)

    # The first yield is executed when the context manager is entered. Then,
    # the subsequent yields are executed when contextmanager.gen.send() is
    # called.

    assert len(yields[:-1]) == len(expected_receives)

    try:
        # Expect for send() to be called for each yield except the last one.
        for y, expected in zip(yields[:-1], expected_receives):
            received = yield y
            assert received == expected
        # The last yield. The only yield in the normal use case without send().
        yield yields[-1]
    except Thrown as thrown:
        # gen.throw() has been called.
        if handle:
            pass
        else:
            raise Raised(thrown)
    finally:
        # NOTE: If a `return` statement is executed in the finally clause,
        # the exception will not be re-raised.
        # https://docs.python.org/3/tutorial/errors.html
        if ret is not None:
            return ret

    return None


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
        '''To be hooked as hook implementation.'''
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
def test_plugins(data: st.DataObject):
    test_send = True
    test_throw = True

    n_plugins = data.draw(st.integers(min_value=0, max_value=5), label='n_plugins')

    n_max_yields = (
        data.draw(st.integers(min_value=1, max_value=10), label='n_max_yields')
        if test_send
        else 1
    )

    yields_list = data.draw(
        st.lists(
            st.lists(st.text(), min_size=1, max_size=n_max_yields, unique=True),
            min_size=n_plugins,
            max_size=n_plugins,
        ),
        label='yields_list',
    )

    n_yields_list = list(map(len, yields_list))
    n_max_yields = max(n_yields_list) if n_yields_list else 1

    n_sends = n_max_yields - 1

    sends = data.draw(
        st.lists(st.text(), min_size=n_sends, max_size=n_sends, unique=True),
        label='sends',
    )

    throw = data.draw(st.booleans(), label='throw') if test_throw else False

    handle_list = [
        data.draw(st.booleans(), label='handle') if n_yields == n_max_yields else False
        for n_yields in n_yields_list
    ]

    ret_list = (
        data.draw(
            st.lists(
                st.one_of(st.none(), st.text()),
                min_size=n_plugins,
                max_size=n_plugins,
            ),
            label='ret_list',
        )
        if not throw
        else [None] * n_plugins
    )

    assert len(yields_list) == len(handle_list) == len(ret_list) == n_plugins

    if not test_send:
        assert all(len(yields) == 1 for yields in yields_list)
        assert len(sends) == 0

    if not test_throw:
        assert not throw
        assert not any(handle_list)

    for i in range(n_plugins):
        yields = yields_list[i]
        handle = handle_list[i]
        ret = ret_list[i]

        check_context(
            yields=yields,
            sends=sends[: len(yields) - 1],
            ret=ret,
            throw=throw and len(yields) == n_max_yields,
            handle=handle,
        )

    pm = pluggy.PluginManager('project')
    pm.add_hookspecs(Spec)

    for i in range(n_plugins):
        yields = yields_list[i]
        handle = handle_list[i]
        ret = ret_list[i]
        plugin = Plugin(
            yields=yields,
            expected_receives=sends[: len(yields) - 1],
            ret=ret,
            handle=handle,
        )
        _ = pm.register(plugin)

    # transpose yields_list. Fill with None if necessary
    yields_tr = list(map(list, zip_longest(*reversed(yields_list), fillvalue=None)))  # type: ignore

    if not yields_tr:
        assert not n_plugins
        yields_tr = [[]]

    with (c := pm.with_.hook()) as yielded:
        assert yields_tr[0] == yielded
        assert len(sends) == len(yields_tr[1:])

        for s, expected in zip(sends, yields_tr[1:]):
            yielded = c.gen.send(s)
            assert expected == yielded

        if throw:
            thrown = Thrown()
            n_raised = len(
                [
                    (n, h)
                    for n, h in zip(n_yields_list, handle_list)
                    if n == n_max_yields and not h
                ]
            )
            with pytest.raises((Thrown, BaseExceptionGroup)) as excinfo_throw:
                c.gen.throw(thrown)
            if not n_raised:
                assert excinfo_throw.type is Thrown
            else:
                assert isinstance(excinfo_throw.value, BaseExceptionGroup)
                expected_exceptions = [thrown] * n_raised
                actual_exceptions = [
                    isinstance(e, Raised) and e.thrown
                    for e in excinfo_throw.value.exceptions
                ]
                assert expected_exceptions == actual_exceptions
        elif any(ret is not None for ret in ret_list):
            with pytest.raises(StopIteration) as excinfo_ret:
                c.gen.send(None)
            assert list(reversed(ret_list)) == excinfo_ret.value.value
