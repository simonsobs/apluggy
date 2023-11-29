from collections.abc import MutableSequence
from typing import Any, TypeVar

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy.test import Probe, RecordReturns, ReplayReturns

from .exc import Raised, Thrown
from .refs.nested import nested_with_single
from .runner import GenCtxManager, mock_context, run_generator_context

T = TypeVar('T')


def run(
    ctx: GenCtxManager[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    try:
        run_generator_context(
            ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends
        )
        probe()
    except (Raised, Thrown) as e:
        probe(e)
    except RuntimeError as e:
        # generator didn't stop
        probe(e)
    except KeyboardInterrupt as e:
        probe(e)
    else:
        probe()
    finally:
        probe()


def run_direct(draw: st.DrawFn, n_sends: int):
    probe = Probe()
    ctx = mock_context(draw=draw, probe=probe, id='ctx', n_sends=n_sends)
    yields = list[Any]()
    run(ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends)
    yields = [[y] for y in yields]
    return probe, yields


def run_nested_with_single(draw: st.DrawFn, n_sends: int):
    probe = Probe()
    ctx0 = mock_context(draw=draw, probe=probe, id='ctx', n_sends=n_sends)
    ctx = nested_with_single([ctx0])
    yields = list[Any]()
    run(ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends)
    return probe, yields


@given(st.data())
@settings(max_examples=200, deadline=1000)
def test_single(data: st.DataObject):
    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    draw = RecordReturns(data.draw)

    #
    probe0, yields0 = run_direct(draw=draw, n_sends=n_sends)

    #
    replay = ReplayReturns(draw)
    probe1, yields1 = run_nested_with_single(draw=replay, n_sends=n_sends)

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
