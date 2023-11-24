from collections.abc import MutableSequence, Sequence
from typing import Any, TypeVar

from hypothesis import given, settings
from hypothesis import strategies as st

from .exc import Raised, Thrown
from .refs import GenCtxMngr, Impl, with_single_context
from .runner import mock_context
from .utils import Probe, RecordReturns, ReplayReturns

T = TypeVar('T')


def run(
    draw: st.DrawFn, impl: Impl[T], n_contexts, n_sends: int
) -> tuple[Probe, list[list[T]]]:
    probe = Probe()
    contexts = [
        mock_context(draw=draw, probe=probe, id=i, n_sends=n_sends)
        for i in range(n_contexts)
    ]
    yields = list[Any]()
    try:
        impl(contexts=contexts, draw=draw, yields=yields, n_sends=n_sends)
        probe()
    except (Raised, Thrown) as e:
        probe(e)

    return probe, yields


def nested_with(
    contexts: Sequence[GenCtxMngr[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    match len(contexts):
        case 1:
            imp = with_single_context
        # case 2:
        #     imp = with_double_contexts
        # case 3:
        #     imp = with_triple_contexts
        case _:
            raise NotImplementedError()
    imp(contexts=contexts, draw=draw, yields=yields, n_sends=n_sends)


@given(st.data())
# @settings(max_examples=1000)
def test_refs(data: st.DataObject):
    n_contexts = data.draw(st.integers(min_value=1, max_value=1), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    # n_sends = 1
    draw = RecordReturns(data.draw)

    ref_imp = with_single_context

    # Run on a reference implementation.
    probe0, yields0 = run(
        draw=draw, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    # Verify the replay draw by running on the same implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
    # ic(probe0.calls)
