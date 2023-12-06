from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from apluggy.test import Probe, RecordReturns

from .exc import GenRaised, Thrown, WithRaised
from .runner import mock_async_context, run_async_generator_context


async def run_mock_async_context(
    draw: st.DrawFn, n_sends: int
) -> tuple[Probe, list[Any]]:
    probe = Probe()
    yields = list[Any]()
    ctx = mock_async_context(draw=draw, probe=probe, id='ctx', n_sends=n_sends)

    probe()
    try:
        await run_async_generator_context(
            ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends
        )
        probe()
    except (WithRaised, Thrown, GenRaised) as e:
        probe(e)
    except RuntimeError as e:
        # generator didn't stop
        probe(e)
    except KeyboardInterrupt as e:
        probe(e)
    finally:
        probe()

    return probe, yields


@given(st.data())
@settings(max_examples=100, deadline=300)
async def test_mock_context(data: st.DataObject) -> None:
    n_sends = data.draw(st.integers(min_value=0, max_value=4), label='n_sends')

    draw = RecordReturns(data.draw)

    probe, yields = await run_mock_async_context(draw=draw, n_sends=n_sends)

    # ic(probe.calls)
    # ic(yields)
