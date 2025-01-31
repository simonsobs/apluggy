import sys
from collections.abc import Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from itertools import count
from typing import Literal, Union

from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_iter_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .exc import MockException


class ExceptionHandler:
    ActionName = Literal['handle', 'reraise', 'raise']
    ActionMap: TypeAlias = Mapping[int, tuple[ActionName, Union[None, Exception]]]
    ACTIONS: tuple[ActionName, ...] = ('handle', 'reraise', 'raise')

    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._clear()

    def _clear(self) -> None:
        self._exc_actual: list[tuple[int, Exception]] = []
        self._exc_expected: Sequence[tuple[int, Exception]] = ()
        self._action_map: Union[ExceptionHandler.ActionMap | None] = None
        self._exit_expected: Union[bool, None] = False
        self._exc_on_exit_expected: Union[Exception, None] = None

    @contextmanager
    def context(self) -> Iterator[None]:
        self._clear()
        yield

    def handle(self, id: int, exc: Exception) -> None:
        self._exc_actual.append((id, exc))
        assert self._action_map is not None
        action, exc1 = self._action_map[id]
        if action == 'reraise':
            raise
        if action == 'raise':
            assert exc1 is not None
            raise exc1
        assert action == 'handle'

    def assert_exited(
        self, handled: Union[bool, None], raised: Union[Exception, None]
    ) -> None:
        assert handled is self._exit_expected
        assert raised is self._exc_on_exit_expected
        self.assert_raised()

    def assert_raised(self) -> None:
        # The `__eq__` comparison of `Exception` objects is default to the
        # `__eq__` method of `object`, which uses the `is` comparison.
        # https://docs.python.org/3/reference/datamodel.html#object.__eq__
        assert self._exc_actual == list(self._exc_expected)

    def before_raise(self, exc: Exception, ids: Iterable[int]) -> None:
        self._action_map = self._draw_actions(ids)
        self._exc_expected = self._expect_exc(exc, self._action_map)
        self._exit_expected = self._expect_exit(self._action_map)
        self._exc_on_exit_expected = self._expect_exc_on_exit(self._action_map)

    def _draw_actions(self, ids: Iterable[int]) -> ActionMap:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        st_actions = st.sampled_from(self.ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions: Iterator[ExceptionHandler.ActionName] = self._draw(
            st_iter_until(st_actions, last='handle', max_size=len(ids))
        )

        # e.g., {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }
        return {
            id: (a, MockException(f'{id}') if a == 'raise' else None)
            for id, a in zip(ids, actions)
        }

    def _expect_exc(
        self, exc: Exception, action_map: ActionMap
    ) -> tuple[tuple[int, Exception], ...]:
        # This method relies on the order of the items in `action_map`.
        # e.g.:
        # exc = MockException('0')
        # action_map = {
        #     4: ('reraise', None),
        #     3: ('reraise', None),
        #     2: ('raise', MockException('2')),
        #     1: ('handle', None),
        # }

        ret = list[tuple[int, Exception]]()
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

    def _expect_exit(self, action_map: ActionMap) -> Union[bool, None]:
        # This method relies on the order of the items in `action_map`.
        for action, _ in reversed(list(action_map.values())):
            if action == 'handle':
                return True
            if action == 'raise':
                return None
        return False

    def _expect_exc_on_exit(self, action_map: ActionMap) -> Union[Exception, None]:
        # This method relies on the order of the items in `action_map`.
        for action, exc1 in reversed(list(action_map.values())):
            if action == 'handle':
                return None
            if action == 'raise':
                return exc1
        return None


class MockContext:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._count = count(1).__next__
        self._n_ctxs = 0
        self._created = list[int]()
        self._entered = list[int]()
        self._exiting = list[int]()

        self._exception_handler = ExceptionHandler(data)

    def __call__(self) -> GenCtxMngr:
        id = self._n_ctxs = self._count()
        self._created.append(id)

        @contextmanager
        def _ctx() -> Generator:
            self._entered.append(id)
            try:
                yield id
            except MockException as e:
                self._exception_handler.handle(id, e)
            finally:
                self._exiting.append(id)

        return _ctx()

    @contextmanager
    def context(self) -> Iterator[None]:
        with self._exception_handler.context():
            yield

    def assert_created(self) -> None:
        assert len(self._created) == self._n_ctxs

    def assert_entered(self) -> None:
        assert self._entered == self._created

    def assert_exited(
        self, handled: Union[bool, None], raised: Union[Exception, None]
    ) -> None:
        assert self._exiting == list(reversed(self._entered))
        self._exception_handler.assert_exited(handled, raised)

    def before_raise(self, exc: Exception) -> None:
        self._exception_handler.before_raise(exc, reversed(self._entered))
