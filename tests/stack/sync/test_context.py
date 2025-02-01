from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

from .context import MockContext
from .exc import MockException
from .refs import dunder_enter, exit_stack, nested_with


@given(data=st.data())
def test_one(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created()
    with ctx:
        mock_context.assert_entered()
    mock_context.assert_exited(raised=None)


@given(data=st.data())
def test_raise(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created()
    try:
        with ctx:
            mock_context.assert_entered()
            with mock_context.context():
                exc = MockException('0')
                mock_context.before_raise(exc)
                raise exc
    except MockException as e:
        mock_context.assert_exited(raised=e)
    else:
        mock_context.assert_exited(raised=None)


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    n_ctxs = data.draw(st.integers(min_value=0, max_value=6))
    gen_enabled = data.draw(st.booleans())

    # `stack_gen_ctxs` is the object to be tested.
    # `dunder_enter`, `nested_with`, and `exit_stack` are reference implementations.
    stacks = [stack_gen_ctxs]
    if n_ctxs <= 4:
        stacks.extend([dunder_enter, nested_with])
    if not gen_enabled:
        stacks.append(exit_stack)
    stack = data.draw(st.sampled_from(stacks))

    mock_context = MockContext(data=data)
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created()

    try:
        # `iter()` is used to ensure `stack` works with an iterable.
        with stack(iter(ctxs)) as y:
            mock_context.assert_entered()
            if data.draw(st.booleans()):
                with mock_context.context():
                    exc = MockException('0')
                    mock_context.before_raise(exc)
                    raise exc
    except MockException as e:
        mock_context.assert_exited(raised=e)
    else:
        mock_context.assert_exited(raised=None)
