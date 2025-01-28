from collections.abc import Generator
from contextlib import contextmanager
from itertools import count
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs
from apluggy.stack import GenCtxMngr

from .refs import dunder_enter, exit_stack, nested_with


class MockContext:
    def __init__(self) -> None:
        self._count = count(1).__next__
        self._created = list[int]()
        self._entered = list[int]()
        self._exiting = list[int]()

    def __len__(self) -> int:
        return len(self._created)

    def __call__(self) -> GenCtxMngr:
        id = self._count()
        self._created.append(id)

        @contextmanager
        def _ctx() -> Generator:
            self._entered.append(id)
            try:
                yield id
            finally:
                self._exiting.append(id)

        return _ctx()

    def assert_entered(self) -> None:
        assert self._entered == self._created

    def assert_exited(self) -> None:
        assert self._exiting == list(reversed(self._entered))


class StatefulTest:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw

        self._n_ctxs = self._draw(st.integers(min_value=0, max_value=6))
        self._to_send = self._draw(st.booleans())

        stacks = [stack_gen_ctxs]
        if self._n_ctxs <= 4:
            stacks.extend([dunder_enter, nested_with])
        if not self._to_send:
            stacks.append(exit_stack)
        stack = self._draw(st.sampled_from(stacks))

        self._mock_context = MockContext()
        ctxs = [self._mock_context() for _ in range(self._n_ctxs)]
        assert len(self._mock_context) == self._n_ctxs

        self._obj = stack(iter(ctxs))

    def __enter__(self) -> 'StatefulTest':
        y = self._obj.__enter__()
        assert y == list(range(1, self._n_ctxs + 1))
        self._mock_context.assert_entered()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        self._obj.__exit__(*args, **kwargs)
        self._mock_context.assert_exited()


@settings(max_examples=100)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    test = StatefulTest(data)

    with test:
        pass
