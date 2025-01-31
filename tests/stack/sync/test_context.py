from hypothesis import given, settings
from hypothesis import strategies as st

from .context import MockContext
from .exc import MockException


@given(data=st.data())
def test_one(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created()
    with ctx:
        mock_context.assert_entered()
    mock_context.assert_exited(handled=False, raised=None)


@settings(max_examples=500)
@given(data=st.data())
def test_raise(data: st.DataObject) -> None:
    mock_context = MockContext(data=data)

    ctx = mock_context()
    mock_context.assert_created()
    exc = MockException('0')
    try:
        with ctx:
            mock_context.assert_entered()
            mock_context.before_raise(exc)
            raise exc
    except MockException as e:
        if e is exc:
            mock_context.assert_exited(handled=False, raised=None)
        else:
            mock_context.assert_exited(handled=None, raised=e)
    else:
        mock_context.assert_exited(handled=True, raised=None)
