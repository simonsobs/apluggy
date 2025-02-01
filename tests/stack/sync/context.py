import sys
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from itertools import count
from typing import Literal, NewType, Union

from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_iter_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .exc import MockException

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
    _ActionMap: TypeAlias = Mapping[
        _CtxId,
        Union[
            tuple[Literal['handle', 'reraise'], None],
            tuple[Literal['raise'], Exception],
        ],
    ]
    _ACTIONS: tuple[_ActionName, ...] = ('handle', 'reraise', 'raise')

    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._clear()

    def _clear(self) -> None:
        self._exc_actual: list[tuple[_CtxId, Exception]] = []
        self._exc_expected: Sequence[tuple[_CtxId, Exception]] = ()
        self._action_map: Union[ExceptionHandler._ActionMap, None] = None
        self._exc_on_exit_expected: Union[Exception, None] = None

    @contextmanager
    def context(self) -> Iterator[None]:
        # TODO: Delete this method if it's not used.
        # self._clear()
        yield

    def handle(self, id: _CtxId, exc: Exception) -> None:
        self._exc_actual.append((id, exc))
        assert self._action_map is not None
        action_item = self._action_map[id]
        if action_item[0] == 'reraise':
            raise
        if action_item[0] == 'raise':
            raise action_item[1]
        assert action_item[0] == 'handle'

    def assert_exited(self, exc: Union[BaseException, None]) -> None:
        assert exc is self._exc_on_exit_expected
        self.assert_raised()

    def assert_raised(self) -> None:
        # The `__eq__` comparison of `Exception` objects is default to the
        # `__eq__` method of `object`, which uses the `is` comparison.
        # https://docs.python.org/3/reference/datamodel.html#object.__eq__
        assert self._exc_actual == list(self._exc_expected)

    def before_raise(self, exc: Exception, ids: Iterable[_CtxId]) -> None:
        self._clear()
        self._action_map = self._draw_actions(ids)
        self._exc_expected = self._expect_exc(exc, self._action_map)
        self._exc_on_exit_expected = self._expect_exc_on_exit(exc, self._action_map)

    def _draw_actions(self, ids: Iterable[_CtxId]) -> _ActionMap:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        st_actions = st.sampled_from(self._ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions: Iterator[ExceptionHandler._ActionName] = self._draw(
            st_iter_until(st_actions, last='handle', max_size=len(ids))
        )

        # e.g., {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }
        return {
            id: (a, MockException(f'{id}')) if a == 'raise' else (a, None)
            for id, a in zip(ids, actions)
        }

    def _expect_exc(
        self, exc: Exception, action_map: _ActionMap
    ) -> tuple[tuple[_CtxId, Exception], ...]:
        # This method relies on the order of the items in `action_map`.
        # e.g.:
        # exc = MockException('0')
        # action_map = {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }

        ret = list[tuple[_CtxId, Exception]]()
        for id, (action, exc1) in action_map.items():
            ret.append((id, exc))
            if action == 'handle':
                break
            if action == 'raise':
                assert exc1 is not None
                exc = exc1

        # e.g., (
        #     (4, MockException('0')),
        #     (3, MockException('0')),
        #     (2, MockException('0')),
        #     (1, MockException('2')),
        # )
        return tuple(ret)

    def _expect_exc_on_exit(
        self, exc: Exception, action_map: _ActionMap
    ) -> Union[Exception, None]:
        # This method relies on the order of the items in `action_map`.
        for action, exc1 in reversed(list(action_map.values())):
            if action == 'handle':
                return None
            if action == 'raise':
                return exc1
        return exc


class MockContext:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._generate_ctx_id = _ContextIdGenerator()
        self._ctxs_map: dict[_CtxId, GenCtxMngr] = {}
        self._created: list[_CtxId] = []
        self._entered: list[_CtxId] = []
        self._exiting: list[_CtxId] = []
        self._exception_handler = ExceptionHandler(data)
        self._clear()

    def _clear(self) -> None:
        self._to_yield: Mapping[_CtxId, str] = {}

    def __call__(self) -> GenCtxMngr:
        id = self._generate_ctx_id()
        self._created.append(id)

        @contextmanager
        def _ctx() -> Generator:
            self._entered.append(id)
            try:
                yield self._to_yield[id]
            except MockException as e:
                self._exception_handler.handle(id, e)
            finally:
                self._exiting.append(id)

        ctx = _ctx()
        self._ctxs_map[id] = ctx
        return ctx

    @contextmanager
    def context(self) -> Iterator[None]:
        # TODO: Delete this method if it's not used.
        # self._clear()
        with self._exception_handler.context():
            yield

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == [self._ctxs_map[id] for id in self._created]

    def before_enter(self) -> None:
        self._to_yield = {id: f'{id}' for id in self._created}

    def assert_entered(self, yields: Iterable[str]) -> None:
        assert self._entered == self._created
        assert list(yields) == [self._to_yield[id] for id in self._entered]

    def assert_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._exiting == list(reversed(self._entered))
        self._exception_handler.assert_exited(exc)

    def before_raise(self, exc: Exception) -> None:
        self._exception_handler.before_raise(exc, reversed(self._entered))
