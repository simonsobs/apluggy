from collections.abc import MutableSequence
from typing import Any, TypeVar

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy.stack import AGenCtxMngr
from apluggy.test import Probe, RecordReturns, ReplayReturns

from .exc import GenRaised, Thrown, WithRaised
from .refs.dunder import dunder_enter_single
from .runner import mock_async_context, run_async_generator_context

T = TypeVar('T')


async def run(
    ctx: AGenCtxMngr[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    try:
        await run_async_generator_context(
            ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends
        )
        probe()
    except (GenRaised, Thrown, WithRaised) as e:
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


async def run_direct(draw: st.DrawFn, n_sends: int):
    probe = Probe()
    ctx = mock_async_context(draw=draw, probe=probe, id='ctx', n_sends=n_sends)
    yields = list[Any]()
    await run(ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends)
    yields = [[y] for y in yields]
    return probe, yields


async def run_dunder_enter_single(draw: st.DrawFn, n_sends: int):
    probe = Probe()
    ctx0 = mock_async_context(draw=draw, probe=probe, id='ctx', n_sends=n_sends)
    ctx = dunder_enter_single([ctx0], fix_reraise=True)  # type: ignore
    yields = list[Any]()
    await run(ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends)
    return probe, yields


@given(st.data())
@settings(max_examples=200, deadline=1000)
async def test_single(data: st.DataObject):
    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    draw = RecordReturns(data.draw)

    #
    probe0, yields0 = await run_direct(draw=draw, n_sends=n_sends)

    # ic(probe0.calls)
    # ic(yields0)

    #
    replay = ReplayReturns(draw)
    probe1, yields1 = await run_dunder_enter_single(draw=replay, n_sends=n_sends)

    # ic(probe1.calls)
    # ic(yields1)

    assert probe0.calls == probe1.calls
    assert yields0 == yields1
