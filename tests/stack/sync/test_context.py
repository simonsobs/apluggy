from typing import Union

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

from .context import MockContext
from .exc import MockException
from .refs import Stack, dunder_enter, exit_stack, nested_with


@given(data=st.data())
def test_one(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created([ctx])
    mock_context.before_enter()
    exc: Union[Exception, None] = None
    try:
        with ctx as y:
            mock_context.on_entered(yields=y)
    except Exception as e:
        exc = e
    mock_context.on_exited(exc=exc)


@given(data=st.data())
def test_raise(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created([ctx])
    mock_context.before_enter()
    exc: Union[Exception, None] = None
    try:
        with ctx as y:
            mock_context.on_entered(yields=y)
            with mock_context.context():
                exc0 = MockException('0')
                mock_context.before_raise(exc0)
                raise exc0
    except Exception as e:
        exc = e
    mock_context.on_exited(exc=exc)


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    n_ctxs = data.draw(st.integers(min_value=0, max_value=6), label='n_ctxs')
    gen_enabled = data.draw(st.booleans(), label='gen_enabled')

    stack = data.draw(_st_stack(n_ctxs, gen_enabled))

    mock_context = MockContext(data=data)
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created(iter(ctxs))  # `iter()` to test with an iterable.

    mock_context.before_enter()
    exc: Union[Exception, None] = None
    try:
        with stack(iter(ctxs)) as y:
            mock_context.on_entered(yields=iter(y))
            if data.draw(st.booleans()):
                with mock_context.context():
                    exc0 = MockException('0')
                    mock_context.before_raise(exc0)
                    raise exc0
    except Exception as e:
        exc = e
    mock_context.on_exited(exc=exc)


def _st_stack(n_ctxs: int, gen_enabled: bool) -> st.SearchStrategy[Stack]:
    # `stack_gen_ctxs` is the object to be tested.
    # `dunder_enter`, `nested_with`, and `exit_stack` are reference implementations.
    stacks = [stack_gen_ctxs]
    if n_ctxs <= 4:
        stacks.extend([dunder_enter, nested_with])
    if not gen_enabled:
        stacks.append(exit_stack)
    return st.sampled_from(stacks)


@pytest.mark.skip
def test_scratch() -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    @contextmanager
    def _ctx() -> Iterator[None]:
        raise MockException('0')
        if False:
            yield

    with _ctx():
        pass
