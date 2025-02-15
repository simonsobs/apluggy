import asyncio
import contextlib
from collections.abc import AsyncGenerator, MutableSequence
from typing import Any, TypeVar

from hypothesis import strategies as st

from apluggy.stack import AGenCtxMngr
from tests.utils import Probe, st_none_or

from .exc import GenRaised, Thrown, WithRaised
from .refs import AStack

T = TypeVar('T')


async def close_gen(gen: AsyncGenerator[Any, Any], max_attempts: int = 10) -> None:
    while True:
        try:
            await gen.aclose()
        except RuntimeError:
            # 'aclose(): asynchronous generator is already running'

            max_attempts -= 1
            if max_attempts <= 0:
                raise

            await asyncio.sleep(0)
            continue
        break


async def async_skips(n: int) -> None:
    for _ in range(n):
        await asyncio.sleep(0)


async def run(
    draw: st.DrawFn, stack: AStack[T], n_contexts: int, n_sends: int
) -> tuple[Probe, list[list[T]]]:
    probe = Probe()
    contexts = [
        mock_async_context(draw=draw, probe=probe, id=f'ctx{i}', n_sends=n_sends)
        for i in range(n_contexts)
    ]
    ctx = stack(iter(contexts))
    yields = list[Any]()
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
        for c in reversed(contexts):
            await close_gen(c.gen)
        probe()

    return probe, yields


@contextlib.asynccontextmanager
async def mock_async_context(
    draw: st.DrawFn, probe: Probe, id: str, n_sends: int
) -> AsyncGenerator[Any, Any]:
    probe(id, 'init', f'n_sends={n_sends}')

    if draw(st.booleans()):
        exc = GenRaised(f'{id}-init')
        probe(id, 'raise', f'{exc!r}')
        raise exc
    probe(id)

    n_skips = draw(st.integers(min_value=0, max_value=4))
    probe(id, 'n_skips', n_skips)
    await async_skips(n_skips)

    try:
        y = f'{id}-enter'
        probe(id, 'enter', f'{y!r}')
        sent = yield y
        probe(id, 'received', f'{sent!r}')

        for i in range(n_sends):
            ii = f'{i+1}/{n_sends}'

            n_skips = draw(st.integers(min_value=0, max_value=4))
            probe(id, ii, 'n_skips', n_skips)
            await async_skips(n_skips)

            action = draw(st.one_of(st.none(), st.sampled_from(['raise', 'break'])))
            if action == 'raise':
                exc = GenRaised(f'{id}-{ii}')
                probe(id, ii, 'raise', f'{exc!r}')
                raise exc
            elif action == 'break':
                probe(id, ii, 'break')
                break

            y = f'{id}-yield-{ii}'
            probe(id, ii, 'yield', f'{y!r}')
            sent = yield y
            probe(id, ii, 'received', f'{sent!r}')

        if draw(st.booleans()):
            exc = GenRaised(f'{id}-exit')
            probe(id, 'raise', f'{exc!r}')
            raise exc

        probe(id)

    except GeneratorExit as e:
        probe(id, 'caught', e)
        raise
    except BaseException as e:
        probe(id, 'caught', e)
        action = draw(st.sampled_from(['reraise', 'raise']))
        if action == 'reraise':
            probe(id, 'reraise')
            raise
        elif action == 'raise':
            exc = GenRaised(f'{id}-except')
            probe(id, 'raise', f'{exc!r}')
            raise exc
    finally:
        probe(id, 'finally')


async def run_async_generator_context(
    ctx: AGenCtxMngr[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    probe('entering')
    async with ctx as y:
        probe('entered')
        yields.append(y)
        st_exceptions = st.sampled_from([WithRaised('entered'), KeyboardInterrupt()])
        exc = draw(st_none_or(st_exceptions))
        if exc is not None:
            probe('with', 'raise', f'{exc!r}')
            raise exc

        for i in range(n_sends):
            ii = f'{i+1}/{n_sends}'
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                # TODO: When Python 3.9 support is dropped
                # match action:
                #     case 'send':
                #         sent = f'send-{ii}'
                #         probe('with', ii, 'send', f'{sent!r}')
                #         y = await ctx.gen.asend(sent)
                #         yields.append(y)
                #     case 'throw':
                #         exc = Thrown(f'{ii}')
                #         probe('with', ii, 'throw', f'{exc!r}')
                #         await ctx.gen.athrow(exc)
                #     case 'close':
                #         probe('with', ii, 'close')
                #         await ctx.gen.aclose()
                if action == 'send':
                    sent = f'send-{ii}'
                    probe('with', ii, 'send', f'{sent!r}')
                    y = await ctx.gen.asend(sent)
                    yields.append(y)
                elif action == 'throw':
                    exc = Thrown(f'{ii}')
                    probe('with', ii, 'throw', f'{exc!r}')
                    await ctx.gen.athrow(exc)
                elif action == 'close':
                    probe('with', ii, 'close')
                    await ctx.gen.aclose()
            except GeneratorExit:
                raise
            except StopAsyncIteration as e:
                probe('with', ii, 'caught', e)
                break
            except BaseException as e:
                probe('with', ii, 'caught', e)
                raise
            st_exceptions = st.sampled_from([WithRaised(f'{ii}'), KeyboardInterrupt()])
            exc = draw(st_none_or(st_exceptions))
            if exc is not None:
                probe('with', {ii}, 'raise', f'{exc!r}')
                raise exc
        probe('exiting')
    probe('exited')
