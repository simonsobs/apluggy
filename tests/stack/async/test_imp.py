from functools import partial

from hypothesis import Phase, given, settings
from hypothesis import strategies as st

from apluggy import async_stack_gen_ctxs
from tests.utils import RecordReturns, ReplayReturns

from .refs import dunder_enter
from .runner import run


@given(st.data())
@settings(max_examples=200, phases=(Phase.generate,))  # Avoid shrinking
async def test_imp(data: st.DataObject):
    n_contexts = data.draw(st.integers(min_value=0, max_value=3), label='n_contexts')
    n_sends = data.draw(st.integers(min_value=0, max_value=4), label='n_sends')
    fix_reraise = data.draw(st.booleans(), label='fix_reraise')
    sequential = data.draw(st.booleans(), label='sequential')

    #
    draw = RecordReturns(data.draw)
    probe0, yields0 = await run(  # type: ignore
        draw=draw,
        stack=partial(dunder_enter, fix_reraise=fix_reraise, sequential=sequential),
        n_contexts=n_contexts,
        n_sends=n_sends,
    )

    # ic(probe0.calls)
    # ic(yields0)

    #
    replay = ReplayReturns(draw)
    probe1, yields1 = await run(  # type: ignore
        draw=replay,
        stack=partial(
            async_stack_gen_ctxs, fix_reraise=fix_reraise, sequential=sequential
        ),
        n_contexts=n_contexts,
        n_sends=n_sends,
    )

    # ic(probe1.calls)
    # ic(yields1)

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
