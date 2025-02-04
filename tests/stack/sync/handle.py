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

_ActionName = Literal['handle', 'reraise', 'raise']
_ActionItem: TypeAlias = Union[
    tuple[Literal['handle', 'reraise'], None],
    tuple[Literal['raise'], Exception],
]
_ActionMap: TypeAlias = Mapping[CtxId, _ActionItem]
_ACTIONS: tuple[_ActionName, ...] = ('handle', 'reraise', 'raise')


class ExceptionHandler:
    def __init__(
        self,
        data: st.DataObject,
        exc: Exception,
        ids: Iterable[CtxId],
        before_enter: bool = False,
    ) -> None:
        self._draw = data.draw
        self._exc_actual: list[tuple[CtxId, Exception]] = []

        self._action_map = self._draw_actions(ids)
        note(f'{self.__class__.__name__}: {self._action_map=}')

        self._exc_expected = self._expect_exc(exc, self._action_map)
        note(f'{self.__class__.__name__}: {self._exc_expected=}')

        self._exc_on_exit_expected = (
            self._expect_exc_on_enter(exc, self._action_map)
            if before_enter
            else self._expect_exc_on_exit(exc, self._action_map)
        )
        note(f'{self.__class__.__name__}: {self._exc_on_exit_expected=}')

    def handle(self, id: CtxId, exc: Exception) -> None:
        self._exc_actual.append((id, exc))
        action_item = self._action_map[id]
        if action_item[0] == 'reraise':
            raise
        if action_item[0] == 'raise':
            raise action_item[1]
        assert action_item[0] == 'handle'

    def assert_exited(self, exc: Union[BaseException, None]) -> None:
        self.assert_raised()
        note(f'{exc=!r} {self._exc_on_exit_expected=!r}')
        assert exc == self._exc_on_exit_expected

    def assert_raised(self) -> None:
        note(f'{self._exc_actual=!r} {self._exc_expected=!r}')
        assert self._exc_actual == list(self._exc_expected)

    def _draw_actions(self, ids: Iterable[CtxId]) -> _ActionMap:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        st_actions = st.sampled_from(_ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions: list[_ActionName] = self._draw(
            st_list_until(st_actions, last='handle', max_size=len(ids)),
            label=f'{self.__class__.__name__}: actions',
        )

        # e.g., {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }
        return {id: self._create_action_item(id, a) for id, a in zip(ids, actions)}

    def _create_action_item(self, id: CtxId, action: _ActionName) -> _ActionItem:
        if action == 'raise':
            return (action, MockException(f'{id}'))
        return (action, None)

    def _expect_exc(
        self, exc: Exception, action_map: _ActionMap
    ) -> tuple[tuple[CtxId, ExceptionExpectation], ...]:
        # This method relies on the order of the items in `action_map`.
        # e.g.:
        # exc = MockException('0')
        # action_map = {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }

        ret = list[tuple[CtxId, ExceptionExpectation]]()
        for id, (action, exc1) in action_map.items():
            method: ExceptionExpectation.Method
            method = 'is' if isinstance(exc, MockException) else 'type-msg'
            ret.append((id, ExceptionExpectation(exc, method=method)))
            if action == 'handle':
                break
            if action == 'raise':
                assert exc1 is not None
                exc = exc1

        # e.g., (
        #     (4, ExceptionExpectation(MockException('0'), method='is')),
        #     (3, ExceptionExpectation(MockException('0'), method='is')),
        #     (2, ExceptionExpectation(MockException('0'), method='is')),
        #     (1, ExceptionExpectation(MockException('2'), method='is')),
        # )
        return tuple(ret)

    def _expect_exc_on_enter(
        self, exc: Exception, action_map: _ActionMap
    ) -> ExceptionExpectation:
        exp_on_handle = ExceptionExpectation(GeneratorDidNotYield, method='type-msg')
        return self._expect_outermost_exc(exc, action_map, exp_on_handle=exp_on_handle)

    def _expect_exc_on_exit(
        self, exc: Exception, action_map: _ActionMap
    ) -> ExceptionExpectation:
        return self._expect_outermost_exc(exc, action_map)

    def _expect_outermost_exc(
        self,
        exc: Exception,
        action_map: _ActionMap,
        exp_on_handle: Optional[ExceptionExpectation] = None,
    ) -> ExceptionExpectation:
        # This method relies on the order of the items in `action_map`.
        for action, exc1 in reversed(list(action_map.values())):
            if action == 'handle':
                if exp_on_handle is None:
                    return ExceptionExpectation(None)
                return exp_on_handle
            if action == 'raise':
                return ExceptionExpectation(exc1)
        method: ExceptionExpectation.Method
        method = 'is' if isinstance(exc, MockException) else 'type-msg'
        return ExceptionExpectation(exc, method=method)
