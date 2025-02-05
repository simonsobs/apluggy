import sys
from collections.abc import Iterable, Mapping
from typing import Literal, Optional, Union

from hypothesis import note
from hypothesis import strategies as st

from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import CtxId
from .exc import ExceptionExpectation, GeneratorDidNotYield, MockException


@st.composite
def st_exception_handler_before_enter(
    draw: st.DrawFn, exc: Exception, ids: Iterable[CtxId]
) -> 'ExceptionHandler':
    return ExceptionHandler.before_enter(draw, exc, ids)


@st.composite
def st_exception_handler_before_raise(
    draw: st.DrawFn, exc: Exception, ids: Iterable[CtxId]
) -> 'ExceptionHandler':
    return ExceptionHandler.before_raise(draw, exc, ids)


@st.composite
def st_exception_handler_before_send(draw: st.DrawFn) -> 'ExceptionHandler':
    return ExceptionHandlerBeforeRaise(draw)


_ActionName = Literal['handle', 'reraise', 'raise']
_ActionItem: TypeAlias = Union[
    tuple[Literal['handle', 'reraise'], None],
    tuple[Literal['raise'], Exception],
]
_ActionMap: TypeAlias = Mapping[CtxId, _ActionItem]
_ACTIONS: tuple[_ActionName, ...] = ('handle', 'reraise', 'raise')


class ExceptionHandler:
    def __init__(
        self, draw: st.DrawFn, exp: ExceptionExpectation, ids: Iterable[CtxId]
    ) -> None:
        self._exc_actual: list[tuple[CtxId, Exception]] = []

        self._action_map = draw(_st_action_map(ids))
        note(f'{self.__class__.__name__}: {self._action_map=}')

        self._exc_expected = _expect_exc(exp, self._action_map)
        note(f'{self.__class__.__name__}: {self._exc_expected=}')

        self._exc_on_exit_expected: ExceptionExpectation

    @classmethod
    def before_enter(
        cls, draw: st.DrawFn, exc: Exception, ids: Iterable[CtxId]
    ) -> 'ExceptionHandler':
        exp_on_reraise = _wrap_exc(exc)
        self = cls(draw, exp_on_reraise, ids)
        exp_on_handle = ExceptionExpectation(GeneratorDidNotYield, method='type-msg')
        self._exc_on_exit_expected = self.expect_outermost_exc(
            exp_on_reraise, exp_on_handle
        )
        note(f'{self.__class__.__name__}: {self._exc_on_exit_expected=}')
        return self

    @classmethod
    def before_raise(
        cls, draw: st.DrawFn, exc: Exception, ids: Iterable[CtxId]
    ) -> 'ExceptionHandler':
        exp_on_reraise = ExceptionExpectation(exc)
        self = cls(draw, exp_on_reraise, ids)
        self._exc_on_exit_expected = self.expect_outermost_exc(exp_on_reraise)
        note(f'{self.__class__.__name__}: {self._exc_on_exit_expected=}')
        return self

    def handle(self, id: CtxId, exc: Exception) -> None:
        self._exc_actual.append((id, exc))
        action_item = self._action_map[id]
        if action_item[0] == 'reraise':
            raise
        if action_item[0] == 'raise':
            raise action_item[1]
        assert action_item[0] == 'handle'

    def expect_outermost_exc(
        self,
        exp_on_reraise: ExceptionExpectation,
        exp_on_handle: Optional[ExceptionExpectation] = None,
    ) -> ExceptionExpectation:
        # From the innermost to the outermost.
        action_items = reversed(list(self._action_map.values()))
        return _expect_last_exc(action_items, exp_on_reraise, exp_on_handle)

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        self._assert_raised()
        note(f'{exc=!r} {self._exc_on_exit_expected=!r}')
        assert exc == self._exc_on_exit_expected

    def _assert_raised(self) -> None:
        note(f'{self._exc_actual=!r} {self._exc_expected=!r}')
        assert self._exc_actual == list(self._exc_expected)


@st.composite
def _st_action_map(draw: st.DrawFn, ids: Iterable[CtxId]) -> _ActionMap:
    # e.g., [4, 3, 2, 1]
    ids = list(ids)

    st_actions = st.sampled_from(_ACTIONS)

    # e.g., ['reraise', 'reraise', 'raise', 'handle']
    actions: list[_ActionName]
    actions = draw(st_list_until(st_actions, last='handle', max_size=len(ids)))
    note(f'{ExceptionHandler.__name__}: {actions=}')

    # e.g., {
    #     4: ('reraise', None),
    #     3: ('reraise', None),
    #     2: ('raise', MockException('2')),
    #     1: ('handle', None),
    # }
    return {id: _create_action_item(id, a) for id, a in zip(ids, actions)}


def _create_action_item(id: CtxId, action: _ActionName) -> _ActionItem:
    if action == 'raise':
        return (action, MockException(f'{id}'))
    return (action, None)


def _expect_exc(
    exp: ExceptionExpectation, action_map: _ActionMap
) -> tuple[tuple[CtxId, ExceptionExpectation], ...]:
    # This method relies on the order of the items in `action_map`.
    # e.g.:
    # exp = ExceptionExpectation(MockException('0'), method='is')
    # action_map = {
    #     4: ('reraise', None),
    #     3: ('reraise', None),
    #     2: ('raise', MockException('2')),
    #     1: ('handle', None),
    # }

    ret = list[tuple[CtxId, ExceptionExpectation]]()
    for id, (action, exc1) in action_map.items():
        ret.append((id, exp))
        if action == 'handle':
            break
        if action == 'raise':
            assert exc1 is not None
            exp = _wrap_exc(exc1)

    # e.g., (
    #     (4, ExceptionExpectation(MockException('0'), method='is')),
    #     (3, ExceptionExpectation(MockException('0'), method='is')),
    #     (2, ExceptionExpectation(MockException('0'), method='is')),
    #     (1, ExceptionExpectation(MockException('2'), method='is')),
    # )
    return tuple(ret)


def _wrap_exc(exc: Exception) -> ExceptionExpectation:
    method: ExceptionExpectation.Method
    method = 'is' if isinstance(exc, MockException) else 'type-msg'
    return ExceptionExpectation(exc, method=method)


def _expect_last_exc(
    action_items: Iterable[_ActionItem],
    exp_on_reraise: ExceptionExpectation,
    exp_on_handle: Optional[ExceptionExpectation] = None,
) -> ExceptionExpectation:
    for action, exc1 in action_items:
        if action == 'handle':
            if exp_on_handle is None:
                return ExceptionExpectation(None)
            return exp_on_handle
        if action == 'raise':
            return ExceptionExpectation(exc1)
    return exp_on_reraise


class ExceptionHandlerBeforeRaise(ExceptionHandler):
    def __init__(self, draw: st.DrawFn) -> None:
        self._exc_on_exit_expected = ExceptionExpectation(
            StopIteration(), method='type'
        )
        note(f'{self.__class__.__name__}: {self._exc_on_exit_expected=}')

    def handle(self, id: CtxId, exc: Exception) -> None:
        note(f'{self.__class__.__name__}: {id=} {exc=}')

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        note(f'{self.__class__.__name__}: {exc=}')
        assert self._exc_on_exit_expected == exc
