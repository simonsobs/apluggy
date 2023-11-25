from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy.test import RecordReturns, ReplayReturns

from .refs import dunder_enter, exit_stack, nested_with
from .runner import run


@given(st.data())
@settings(max_examples=200)
def test_refs(data: st.DataObject):
    '''Assert reference implementations run in exactly the same way.'''
    n_contexts = data.draw(st.integers(min_value=0, max_value=4), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    draw = RecordReturns(data.draw)

    # Run on nested-with implementation.
    probe0, yields0 = run(
        draw=draw, stack=nested_with, n_contexts=n_contexts, n_sends=n_sends
    )

    # Verify the replay draw by running on the same implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, stack=nested_with, n_contexts=n_contexts, n_sends=n_sends
    )

    assert probe0.calls == probe1.calls
    assert yields0 == yields1

    # Compare with manual enter/exit implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, stack=dunder_enter, n_contexts=n_contexts, n_sends=n_sends
    )
    assert probe0.calls == probe1.calls
    assert yields0 == yields1

    # Compare with ExitStack, which doesn't support send.
    if n_sends == 0:
        replay = ReplayReturns(draw)
        probe1, yields1 = run(
            draw=replay, stack=exit_stack, n_contexts=n_contexts, n_sends=n_sends
        )
        assert probe0.calls == probe1.calls
        assert yields0 == yields1
