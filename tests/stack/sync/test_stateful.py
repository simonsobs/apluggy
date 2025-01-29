from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from itertools import count
from types import TracebackType
from typing import Optional

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs
from apluggy.stack import GenCtxMngr

from .refs import dunder_enter, exit_stack, nested_with


class MockException(Exception):
    pass


class MockContext:
    def __init__(self) -> None:
        self._count = count(1).__next__
        self._created = list[int]()
        self._entered = list[int]()
        self._exiting = list[int]()
        self._raised = list[tuple[int, Exception]]()
        self._raised_expected = list[tuple[int, Exception]]()

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
                assert e is self._exc
                raise
            finally:
                self._exiting.append(id)

        return _ctx()

    @contextmanager
    def context(self) -> Iterator[None]:
        self._raised.clear()
        self._raised_expected.clear()
        yield

    def assert_created(self, n: int) -> None:
        assert len(self._created) == n

    def assert_entered(self) -> None:
        assert self._entered == self._created

    def assert_exited(self, handled: bool | None) -> None:
        assert self._exiting == list(reversed(self._entered))
        assert not handled
        self.assert_raised()

    def assert_raised(self) -> None:
        # The `__eq__` comparison of `Exception` objects is default to the
        # `__eq__` method of `object`, which uses the `is` comparison.
        # https://docs.python.org/3/reference/datamodel.html#object.__eq__
        assert self._raised == self._raised_expected

    def before_raise(self, exc: Exception) -> None:
        self._exc = exc
        self._raised_expected[:] = [(id, exc) for id in reversed(self._entered)]


class StatefulTest:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw

        self._n_ctxs = self._draw(st.integers(min_value=0, max_value=6))
        self._gen_enabled = self._draw(st.booleans())

        stacks = [stack_gen_ctxs]
        if self._n_ctxs <= 4:
            stacks.extend([dunder_enter, nested_with])
        if not self._gen_enabled:
            stacks.append(exit_stack)
        stack = self._draw(st.sampled_from(stacks))

        # self._n_ctxs = 1
        # self._gen_enabled = True
        # stack = dunder_enter

        self._mock_context = MockContext()
        ctxs = [self._mock_context() for _ in range(self._n_ctxs)]
        self._mock_context.assert_created(self._n_ctxs)

        self._obj = stack(iter(ctxs))

    @property
    def methods(self) -> list[Callable[[], None]]:
        ret = [self.raise_]
        if self._gen_enabled:
            ret.append(self.send)
        return ret

    @contextmanager
    def context(self) -> Iterator[None]:
        self._raised: Exception | None = None
        with self._mock_context.context():
            yield

    def send(self) -> None:
        pass

    def raise_(self) -> None:
        exc = MockException('0')
        self._mock_context.before_raise(exc)
        self._raised = exc
        raise exc

    def __enter__(self) -> 'StatefulTest':
        y = self._obj.__enter__()
        assert y == list(range(1, self._n_ctxs + 1))
        self._mock_context.assert_entered()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        assert exc_value is self._raised
        handled = self._obj.__exit__(exc_type, exc_value, traceback)
        self._mock_context.assert_exited(handled=handled)
        return True


@settings(max_examples=100)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    # print()
    test = StatefulTest(data)

    methods = data.draw(st.lists(st.sampled_from(test.methods)))

    with test:
        with test.context():
            # test.raise_()
            # raise MockException()
            for method in methods:
                method()
