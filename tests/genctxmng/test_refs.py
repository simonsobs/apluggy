import contextlib
from collections.abc import MutableSequence, Sequence
from typing import Any, Generator, TypeVar

from hypothesis import given, settings
from hypothesis import strategies as st

from .exc import Raised, Thrown
from .refs import GenCtxManager, Impl, with_single_context
from .utils import Probe, RecordReturns, ReplayReturns

T = TypeVar('T')


@contextlib.contextmanager
def mock_context(
    draw: st.DrawFn, probe: Probe, id: int, n_sends: int = 0
) -> Generator[Any, Any, Any]:
    probe(id)

    if draw(st.booleans()):
        probe(id)
        raise Raised(f'c-{id}-s')

    for i in range(n_sends, draw(st.integers(min_value=0, max_value=n_sends)), -1):
        try:
            sent = yield f'yield {id} ({i})'
            probe(id, i, sent)
        except (Raised, Thrown, GeneratorExit) as e:
            probe(id, i, e)
            raise  # otherwise RuntimeError('generator didn't stop') by contextlib
        probe(id, i)
        if draw(st.booleans()):
            probe(id, i)
            raise Raised(f'c-{id}-{i}')
        probe(id, i)

    try:
        yield f'yield {id}'
        probe(id)
    except (Raised, Thrown) as e:
        probe(id, e)
        raise  # So that the outer generator context managers stop.

    probe(id)
    if draw(st.booleans()):
        probe(id)
        raise Raised(f'c-{id}-e')
    probe(id)


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
    contexts: Sequence[GenCtxManager[T]],
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
