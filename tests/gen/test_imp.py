from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs
from apluggy.test import RecordReturns, ReplayReturns

from .refs import dunder_enter
from .runner import run


@given(st.data())
@settings(max_examples=200, deadline=1000)
def test_imp(data: st.DataObject):
    '''Compare with reference implementations.'''
    n_contexts = data.draw(st.integers(min_value=0, max_value=4), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=4), label='n_sends')
    draw = RecordReturns(data.draw)

    # ic(n_contexts, n_sends)

    # Run on reference implementations that support upto 3 contexts.
    probe0, yields0 = run(
        draw=draw, stack=dunder_enter, n_contexts=n_contexts, n_sends=n_sends
    )

    # ic(probe0.calls)

    # Run on the production implementation which supports arbitrary number of contexts.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, stack=stack_gen_ctxs, n_contexts=n_contexts, n_sends=n_sends
    )

    # ic(probe1.calls)
    # ic(probe0.calls, probe1.calls)

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
