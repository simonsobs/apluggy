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


class MockContext:
    ExceptActionName = Literal['handle', 'reraise', 'raise']
    ExceptActionMap: TypeAlias = Mapping[
        int, tuple[ExceptActionName, Union[None, Exception]]
    ]
    EXCEPT_ACTIONS: tuple[ExceptActionName, ...] = ('handle', 'reraise', 'raise')

    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._count = count(1).__next__
        self._created = list[int]()
        self._entered = list[int]()
        self._exiting = list[int]()
        self._raised = list[tuple[int, Exception]]()
        self._raised_expected: Sequence[tuple[int, Exception]] = ()
        self._except_action: Union[MockContext.ExceptActionMap | None] = None
        self._handled_expected: Union[bool, None] = False
        self._raised_on_exit_expected: Union[Exception, None] = None

    def __call__(self) -> GenCtxMngr:
        id = self._count()
        self._created.append(id)

        @contextmanager
        def _ctx() -> Generator:
            self._entered.append(id)
            try:
                yield id
            except MockException as e:
                self._raised.append((id, e))
                assert self._except_action is not None
                action, exc = self._except_action[id]
                if action == 'reraise':
                    raise
                if action == 'raise':
                    assert exc is not None
                    raise exc
                assert action == 'handle'
            finally:
                self._exiting.append(id)

        return _ctx()

    @contextmanager
    def context(self) -> Iterator[None]:
        self._raised.clear()
        self._raised_expected = ()
        self._except_action = None
        self._handled_expected = False
        self._raised_on_exit_expected = None
        yield

    def assert_created(self, n: int) -> None:
        assert len(self._created) == n

    def assert_entered(self) -> None:
        assert self._entered == self._created

    def assert_exited(
        self, handled: Union[bool, None], raised: Union[Exception, None]
    ) -> None:
        assert self._exiting == list(reversed(self._entered))
        # assert not handled
        assert handled is self._handled_expected
        assert raised is self._raised_on_exit_expected
        self.assert_raised()

    def assert_raised(self) -> None:
        # The `__eq__` comparison of `Exception` objects is default to the
        # `__eq__` method of `object`, which uses the `is` comparison.
        # https://docs.python.org/3/reference/datamodel.html#object.__eq__
        assert self._raised == list(self._raised_expected)

    def before_raise(self, exc: Exception) -> None:
        self._except_action = self._draw_except_actions(reversed(self._entered))
        self._raised_expected = self._compose_raised_expected(exc, self._except_action)
        self._handled_expected = self._determine_handled_expected(self._except_action)
        self._raised_on_exit_expected = self._determine_raised_on_exit_expected(
            self._except_action
        )

    def _draw_except_actions(self, ids: Iterable[int]) -> ExceptActionMap:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        st_actions = st.sampled_from(self.EXCEPT_ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions: Iterator[MockContext.ExceptActionName] = self._draw(
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

    def _compose_raised_expected(
        self, exc: Exception, action_map: ExceptActionMap
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

    def _determine_handled_expected(
        self, action_map: ExceptActionMap
    ) -> Union[bool, None]:
        # This method relies on the order of the items in `action_map`.
        for action, _ in reversed(list(action_map.values())):
            if action == 'handle':
                return True
            if action == 'raise':
                return None
        return False

    def _determine_raised_on_exit_expected(
        self, action_map: ExceptActionMap
    ) -> Union[Exception, None]:
        # This method relies on the order of the items in `action_map`.
        for action, exc1 in reversed(list(action_map.values())):
            if action == 'handle':
                return None
            if action == 'raise':
                return exc1
        return None
