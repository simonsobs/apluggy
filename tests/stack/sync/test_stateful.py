from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Optional, Union

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

from .context import MockContext
from .exc import MockException
from .refs import dunder_enter, exit_stack, nested_with


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
        self._mock_context.assert_created(ctxs)

        self._obj = stack(iter(ctxs))

        self._raised: Union[Exception, None] = None

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
        # y = self._obj.gen.send('send')
        pass

    def raise_(self) -> None:
        exc = MockException('0')
        self._mock_context.before_raise(exc)
        self._raised = exc
        raise exc

    def __enter__(self) -> 'StatefulTest':
        self._mock_context.before_enter()
        y = self._obj.__enter__()
        self._mock_context.assert_entered(yields=y)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        # assert exc_value is self._raised
        # ic(exc_value)
        handled, raised = self._exit_stack(exc_type, exc_value, traceback)
        exc = raised or not handled and exc_value or None
        self._mock_context.assert_exited(exc=exc)
        return True

    def _exit_stack(
        self, *args: Any, **kwargs: Any
    ) -> tuple[Union[bool, None], Union[Exception, None]]:
        try:
            handled = self._obj.__exit__(*args, **kwargs)
            return handled, None
        except Exception as e:
            return None, e


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    # print()
    test = StatefulTest(data)

    # methods = data.draw(st.lists(st.sampled_from(test.methods)))

    with test:
        # with test.context():
        #     # test.raise_()
        #     # raise MockException()
        # for method in methods:
        #     with test.context():
        #         method()
        if test.methods:
            while data.draw(st.booleans()):
                method = data.draw(st.sampled_from(test.methods))
                with test.context():
                    method()
