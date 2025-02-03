import sys
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from itertools import count
from typing import Literal, NewType, Optional, Union

from hypothesis import note
from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .exc import ExceptionExpectation, GeneratorDidNotYield, MockException

_CtxId = NewType('_CtxId', int)


def _ContextIdGenerator() -> Callable[[], _CtxId]:
    '''Return a function that returns a new `_CtxId` each time it is called.

    >>> gen = _ContextIdGenerator()
    >>> id1 = gen()
    >>> id2 = gen()
    >>> id1 is id2
    False
    '''
    _count = count(1).__next__

    def _gen() -> _CtxId:
        return _CtxId(_count())

    return _gen


class ExceptionHandler:
    _ActionName = Literal['handle', 'reraise', 'raise']
    _ActionItem: TypeAlias = Union[
        tuple[Literal['handle', 'reraise'], None],
        tuple[Literal['raise'], Exception],
    ]
    _ActionMap: TypeAlias = Mapping[_CtxId, _ActionItem]
    _ACTIONS: tuple[_ActionName, ...] = ('handle', 'reraise', 'raise')

    def __init__(
        self,
        data: st.DataObject,
        exc: Exception,
        ids: Iterable[_CtxId],
        before_enter: bool = False,
    ) -> None:
        self._draw = data.draw
        self._exc_actual: list[tuple[_CtxId, Exception]] = []

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

    def handle(self, id: _CtxId, exc: Exception) -> None:
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

    def _draw_actions(self, ids: Iterable[_CtxId]) -> _ActionMap:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        st_actions = st.sampled_from(self._ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions: list[ExceptionHandler._ActionName] = self._draw(
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

    def _create_action_item(self, id: _CtxId, action: _ActionName) -> _ActionItem:
        if action == 'raise':
            return (action, MockException(f'{id}'))
        return (action, None)

    def _expect_exc(
        self, exc: Exception, action_map: _ActionMap
    ) -> tuple[tuple[_CtxId, ExceptionExpectation], ...]:
        # This method relies on the order of the items in `action_map`.
        # e.g.:
        # exc = MockException('0')
        # action_map = {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }

        ret = list[tuple[_CtxId, ExceptionExpectation]]()
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


class MockContext:
    _ActionName = Literal['yield', 'raise', 'break']
    _ActionItem: TypeAlias = Union[
        tuple[Literal['yield'], str],
        tuple[Literal['raise'], Exception],
        tuple[Literal['break'], None],
    ]
    _ActionMap: TypeAlias = Mapping[_CtxId, _ActionItem]
    _ACTIONS: tuple[_ActionName, ...] = ('yield', 'raise', 'break')

    def __init__(self, data: st.DataObject) -> None:
        self._data = data
        self._draw = data.draw
        self._generate_ctx_id = _ContextIdGenerator()
        self._ctxs_map: dict[_CtxId, GenCtxMngr] = {}
        self._created_ctx_ids: list[_CtxId] = []
        self._entered_ctx_ids: list[_CtxId] = []
        self._exiting_ctx_ids: list[_CtxId] = []
        self._exception_handler: Union[ExceptionHandler, None] = None
        self._clear()

    def _clear(self) -> None:
        self._action_map: Union[MockContext._ActionMap, None] = None

    def __call__(self) -> GenCtxMngr[str]:
        id = self._generate_ctx_id()
        self._created_ctx_ids.append(id)

        @contextmanager
        def _ctx() -> Iterator[str]:
            self._entered_ctx_ids.append(id)
            try:
                for _ in range(1):
                    assert self._action_map is not None
                    action_item = self._action_map[id]
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    if action_item[0] == 'break':
                        break
                    try:
                        assert action_item[0] == 'yield'
                        yield action_item[1]
                    except Exception as e:
                        note(f'ctx {id=} except: {e=}')
                        assert self._exception_handler is not None
                        self._exception_handler.handle(id, e)
            finally:
                self._exiting_ctx_ids.append(id)

        ctx = _ctx()
        self._ctxs_map[id] = ctx
        return ctx

    @contextmanager
    def context(self) -> Iterator[None]:
        # TODO: Delete this method if it's not used.
        # self._clear()
        yield

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == [self._ctxs_map[id] for id in self._created_ctx_ids]

    def before_enter(self) -> None:
        self._clear()
        self._action_map = self._draw_actions(self._created_ctx_ids)
        note(f'{self.__class__.__name__}: {self._action_map=}')

        self._exception_handler = self._draw_exception_handler()

    def _draw_exception_handler(self) -> Union[ExceptionHandler, None]:
        if not self._action_map:
            return None

        id, last_action_item = list(self._action_map.items())[-1]
        ids = self._created_ctx_ids[: self._created_ctx_ids.index(id)]
        if last_action_item[0] == 'raise':
            exc = last_action_item[1]
            return ExceptionHandler(
                self._data, exc=exc, ids=reversed(ids), before_enter=True
            )
        elif last_action_item[0] == 'break':
            return ExceptionHandler(
                self._data,
                exc=GeneratorDidNotYield,
                ids=reversed(ids),
                before_enter=True,
            )
        return None

    def on_entered(self, yields: Iterable[str]) -> None:
        assert self._entered_ctx_ids == self._created_ctx_ids
        assert self._action_map is not None
        assert list(yields) == [self._action_map[id][1] for id in self._entered_ctx_ids]

    def on_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._exiting_ctx_ids == list(reversed(self._entered_ctx_ids))
        if self._exception_handler is None:
            assert exc is None
        else:
            self._exception_handler.assert_exited(exc)

    def before_raise(self, exc: Exception) -> None:
        self._exception_handler = ExceptionHandler(
            self._data, exc=exc, ids=reversed(self._entered_ctx_ids)
        )

    def _draw_actions(self, ids: Iterable[_CtxId]) -> _ActionMap:
        ids = list(ids)
        st_actions = st.sampled_from(self._ACTIONS)
        actions: list[MockContext._ActionName] = self._draw(
            st_list_until(st_actions, last={'raise', 'break'}, max_size=len(ids)),
            label=f'{self.__class__.__name__}: actions',
        )
        return {id: self._create_action_item(id, a) for id, a in zip(ids, actions)}

    def _create_action_item(self, id: _CtxId, action: _ActionName) -> _ActionItem:
        if action == 'raise':
            return (action, MockException(f'{id}'))
        if action == 'yield':
            return (action, f'{id}')
        return (action, None)
