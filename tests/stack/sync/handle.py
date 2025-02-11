import sys
from collections.abc import Iterable, MutableMapping, Sequence
from typing import Literal, Optional, Union

from hypothesis import note
from hypothesis import strategies as st

from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import CtxId
from .exc import ExceptionExpectation, MockException, wrap_exc

ExceptActionName = Literal['handle', 'reraise', 'raise']
EXCEPT_ACTIONS: Sequence[ExceptActionName] = ('handle', 'reraise', 'raise')


_ActionItem: TypeAlias = Union[
    tuple[Literal['handle'], None],
    tuple[Literal['reraise'], None],
    tuple[Literal['raise'], Exception],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]


@st.composite
def st_exception_handler(
    draw: st.DrawFn,
    exp: ExceptionExpectation,
    ids: Iterable[CtxId],
    enabled_actions: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
) -> 'ExceptionHandler':
    return ExceptionHandler(draw, exp, ids, enabled_actions)


class ExceptionHandler:
    def __init__(
        self,
        draw: st.DrawFn,
        exp: ExceptionExpectation,
        ids: Iterable[CtxId],
        enabled_actions: Sequence[ExceptActionName],
    ) -> None:
        # The expected exception to be raised in the innermost context.
        self._exp = exp

        self._action_map = draw(_st_action_map(ids, enabled_actions))
        note(f'{self.__class__.__name__}: {self._action_map=}')

        self._expected = _compose_expected(exp, self._action_map)
        note(f'{self.__class__.__name__}: {self._expected=}')

        self._actual: list[tuple[CtxId, Exception]] = []

    def handle(self, id: CtxId, exc: Exception) -> None:
        self._actual.append((id, exc))
        action_item = self._action_map.pop(id)
        if action_item[0] == 'reraise':
            raise
        if action_item[0] == 'raise':
            raise action_item[1]
        assert action_item[0] == 'handle'

    def expect_outermost_exc(
        self,
        exp_on_handle: Optional[ExceptionExpectation] = None,
    ) -> ExceptionExpectation:
        # From the innermost to the outermost.
        action_items = reversed(list(self._action_map.values()))
        if exp_on_handle is None:
            exp_on_handle = wrap_exc(None)
        return _expect_last_exc(
            action_items, exp_on_reraise=self._exp, exp_on_handle=exp_on_handle
        )

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        assert not self._action_map, f'{self._action_map=}'
        self._assert_raised()

    def _assert_raised(self) -> None:
        note(f'{self._actual=!r} {self._expected=!r}')
        assert self._actual == list(self._expected)


@st.composite
def _st_action_map(
    draw: st.DrawFn,
    ids: Iterable[CtxId],
    enabled_actions: Sequence[ExceptActionName],
) -> _ActionMap:
    '''Draw ways to handle exceptions in each context.'''
    # e.g., [4, 3, 2, 1]
    ids = list(ids)

    st_actions = st.sampled_from(enabled_actions)

    # e.g., ['reraise', 'reraise', 'raise', 'handle']
    actions: list[ExceptActionName]
    actions = draw(st_list_until(st_actions, last='handle', max_size=len(ids)))
    note(f'{ExceptionHandler.__name__}: {actions=}')

    def _action_item(id: CtxId, action: ExceptActionName) -> _ActionItem:
        if action == 'raise':
            return ('raise', MockException(f'{id}'))
        elif action == 'reraise':
            return ('reraise', None)
        elif action == 'handle':
            return ('handle', None)
        else:  # pragma: no cover
            raise ValueError(action)

    # e.g., {
    #     4: ('reraise', None),
    #     3: ('reraise', None),
    #     2: ('raise', MockException('2')),
    #     1: ('handle', None),
    # }
    return {id: _action_item(id, a) for id, a in zip(ids, actions)}


def _compose_expected(
    exp: ExceptionExpectation, action_map: _ActionMap
) -> tuple[tuple[CtxId, ExceptionExpectation], ...]:
    '''Expected exceptions from the innermost to the outermost context.

    This method relies on the order of the items in `action_map`.
    '''
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
            exp = wrap_exc(exc1)

    # e.g., (
    #     (4, ExceptionExpectation(MockException('0'), method='is')),
    #     (3, ExceptionExpectation(MockException('0'), method='is')),
    #     (2, ExceptionExpectation(MockException('0'), method='is')),
    #     (1, ExceptionExpectation(MockException('2'), method='is')),
    # )
    return tuple(ret)


def _expect_last_exc(
    action_items: Iterable[_ActionItem],
    exp_on_reraise: ExceptionExpectation,
    exp_on_handle: ExceptionExpectation,
) -> ExceptionExpectation:
    for action, exc1 in action_items:
        if action == 'handle':
            return exp_on_handle
        if action == 'raise':
            return wrap_exc(exc1)
    return exp_on_reraise


class ExceptionHandlerNull(ExceptionHandler):
    def __init__(self) -> None:
        pass

    def expect_outermost_exc(
        self,
        exp_on_handle: Optional[ExceptionExpectation] = None,
    ) -> ExceptionExpectation:
        return wrap_exc(None)

    def handle(self, id: CtxId, exc: Exception) -> None:
        assert False  # pragma: no cover

    def assert_on_exited(self, exc: Union[BaseException, None]) -> None:
        assert True
