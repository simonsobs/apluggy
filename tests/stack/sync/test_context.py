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
    with ctx as y:
        mock_context.assert_entered(yields=y)
    mock_context.assert_exited(exc=None)


@given(data=st.data())
def test_raise(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created([ctx])
    mock_context.before_enter()
    try:
        with ctx as y:
            mock_context.assert_entered(yields=y)
            with mock_context.context():
                exc = MockException('0')
                mock_context.before_raise(exc)
                raise exc
    except MockException as e:
        mock_context.assert_exited(exc=e)
    else:
        mock_context.assert_exited(exc=None)


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    n_ctxs = data.draw(st.integers(min_value=0, max_value=6))
    gen_enabled = data.draw(st.booleans())

    stack = _draw_stack(data, n_ctxs, gen_enabled)

    mock_context = MockContext(data=data)
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created(iter(ctxs))  # `iter()` to test with an iterable.

    mock_context.before_enter()
    try:
        with stack(iter(ctxs)) as y:
            mock_context.assert_entered(yields=iter(y))
            if data.draw(st.booleans()):
                with mock_context.context():
                    exc = MockException('0')
                    mock_context.before_raise(exc)
                    raise exc
    except MockException as e:
        mock_context.assert_exited(exc=e)
    else:
        mock_context.assert_exited(exc=None)


def _draw_stack(data, n_ctxs: int, gen_enabled: bool) -> Stack:
    # `stack_gen_ctxs` is the object to be tested.
    # `dunder_enter`, `nested_with`, and `exit_stack` are reference implementations.
    stacks = [stack_gen_ctxs]
    if n_ctxs <= 4:
        stacks.extend([dunder_enter, nested_with])
    if not gen_enabled:
        stacks.append(exit_stack)
    stack = data.draw(st.sampled_from(stacks))
    return stack


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
