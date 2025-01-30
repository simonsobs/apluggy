from collections.abc import Callable, Generator, Iterable, Iterator
from contextlib import contextmanager
from hmac import new
from itertools import count
from types import TracebackType
from typing import Optional, TypeVar, Union

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs
from apluggy.stack import GenCtxMngr
from tests.utils import st_none_or

from .refs import dunder_enter, exit_stack, nested_with

T = TypeVar('T')


def take_until(condition: Callable[[T], bool], iterable: Iterable[T]) -> Iterator[T]:
    '''Iterate until after yielding the first element that satisfies the condition.'''
    for x in iterable:
        yield x
        if condition(x):
            break


@st.composite
def st_iter_until(
    draw: st.DrawFn,
    st_: st.SearchStrategy[T],
    /,
    *,
    last: T,
    max_size: Optional[int] = None,
) -> Iterator[T]:
    '''A strategy for iterators that draw from `st_` until `last` is drawn.'''
    counts = range(max_size) if max_size is not None else count()
    gen = (draw(st_) for _ in counts)
    return take_until(lambda x: x == last, gen)


@given(...)
def test_take_until(items: list[int], last: int) -> None:
    actual = list(take_until(lambda x: x == last, iter(items)))
    expected = items[: items.index(last) + 1] if last in items else items
    assert actual == expected


@given(data=st.data())
def test_iterable_until(data: st.DataObject) -> None:
    samples = data.draw(st.lists(st.text(), min_size=1))
    st_ = st.sampled_from(samples)
    last = data.draw(st_)
    max_size = data.draw(st_none_or(st.integers(min_value=0, max_value=10)))

    it = data.draw(st_iter_until(st_, last=last, max_size=max_size))
    res = list(it)

    assert last not in res[:-1]

    if max_size is None:
        assert last == res[-1]
    else:
        assert len(res) == max_size or (last == res[-1] and len(res) < max_size)


class MockException(Exception):
    pass


class MockContext:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._count = count(1).__next__
        self._created = list[int]()
        self._entered = list[int]()
        self._exiting = list[int]()
        self._raised = list[tuple[int, Exception]]()
        self._raised_expected = list[tuple[int, Exception]]()
        self._except_action = dict[int, tuple[str, Union[None, Exception]]]()
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
        self._raised_expected.clear()
        self._except_action.clear()
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
        assert self._raised == self._raised_expected

    def before_raise(self, exc: Exception) -> None:
        self._raised_expected.clear()
        self._except_action = self._draw_except_actions(reversed(self._entered))

        for id, (action, exc1) in self._except_action.items():
            if action == 'handle':
                self._raised_expected.append((id, exc))
                self._handled_expected = True
                self._raised_on_exit_expected = None
                break
            elif action == 'reraise':
                self._raised_expected.append((id, exc))
            elif action == 'raise':
                self._raised_expected.append((id, exc))
                assert exc1 is not None
                exc = exc1
                self._handled_expected = None
                self._raised_on_exit_expected = exc

    def _draw_except_actions(
        self, ids: Iterable[int]
    ) -> dict[int, tuple[str, Union[None, Exception]]]:
        # e.g., [4, 3, 2, 1]
        ids = list(ids)

        ACTIONS = ('handle', 'reraise', 'raise')
        last = 'handle'
        st_actions = st.sampled_from(ACTIONS)

        # e.g., ['reraise', 'reraise', 'raise', 'handle']
        actions = self._draw(st_iter_until(st_actions, last=last, max_size=len(ids)))

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

        self._mock_context = MockContext(data=data)
        ctxs = [self._mock_context() for _ in range(self._n_ctxs)]
        self._mock_context.assert_created(self._n_ctxs)

        self._obj = stack(iter(ctxs))

        self._raised: Exception | None = None

    @property
    def methods(self) -> list[Callable[[], None]]:
        ret = [self.raise_]
        if self._gen_enabled:
            ret.append(self.send)
        return ret

    @contextmanager
    def context(self) -> Iterator[None]:
        self._raised = None
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
        # assert exc_value is self._raised
        # ic(exc_value)
        handled: Union[bool, None] = None
        raised: Union[Exception, None] = None
        try:
            handled = self._obj.__exit__(exc_type, exc_value, traceback)
        except Exception as e:
            raised = e
        # ic(handled)
        self._mock_context.assert_exited(handled=handled, raised=raised)
        return True


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    # print()
    test = StatefulTest(data)

    methods = data.draw(st.lists(st.sampled_from(test.methods)))

    with test:
        # with test.context():
        #     # test.raise_()
        #     # raise MockException()
        for method in methods:
            with test.context():
                method()
