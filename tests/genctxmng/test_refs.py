from hypothesis import given, settings
from hypothesis import strategies as st

from .refs import stack_with
from .runner import run
from .utils import RecordReturns, ReplayReturns


@given(st.data())
# @settings(max_examples=1000)
def test_refs(data: st.DataObject):
    n_contexts = data.draw(st.integers(min_value=1, max_value=1), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    # n_sends = 1
    draw = RecordReturns(data.draw)

    ref_imp = stack_with

    # Run on a reference implementation.
    probe0, yields0 = run(
        draw=draw, stack=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    # Verify the replay draw by running on the same implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, stack=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
    # ic(probe0.calls)
