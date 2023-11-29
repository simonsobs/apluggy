import asyncio
import contextlib
from collections.abc import AsyncGenerator, MutableSequence
from typing import Any, TypeVar

from hypothesis import strategies as st

from apluggy.test import Probe

from .exc import Raised, Thrown

T = TypeVar('T')

AsyncGenCtxManager = contextlib._AsyncGeneratorContextManager


async def async_skips(n: int) -> None:
    for _ in range(n):
        await asyncio.sleep(0)


@contextlib.asynccontextmanager
async def mock_async_context(
    draw: st.DrawFn, probe: Probe, id: str, n_sends: int
) -> AsyncGenerator[Any, Any]:
    probe(id, 'init', f'n_sends={n_sends}')

    if draw(st.booleans()):
        exc = Raised(f'{id}-init')
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
                exc = Raised(f'{id}-{ii}')
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
            exc = Raised(f'{id}-exit')
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
            exc = Raised(f'{id}-except')
            probe(id, 'raise', f'{exc!r}')
            raise exc
    finally:
        probe(id, 'finally')


async def run_async_generator_context(
    ctx: AsyncGenCtxManager[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    probe('entering')
    async with ctx as y:
        probe('entered')
        yields.append(y)
        exc = draw(
            st.one_of(
                st.none(),
                st.sampled_from([Raised('with-entered'), KeyboardInterrupt()]),
            )
        )
        if exc is not None:
            probe('with', 'raise', f'{exc!r}')
            raise exc

        for i in range(n_sends):
            ii = f'{i+1}/{n_sends}'
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                match action:
                    case 'send':
                        sent = f'send-{ii}'
                        probe('with', ii, 'send', f'{sent!r}')
                        y = await ctx.gen.asend(sent)
                        yields.append(y)
                    case 'throw':
                        exc = Thrown(f'{ii}')
                        probe('with', ii, 'throw', f'{exc!r}')
                        ctx.gen.athrow(exc)
                    case 'close':
                        probe('with', ii, 'close')
                        ctx.gen.aclose()
            except GeneratorExit:
                raise
            except StopAsyncIteration as e:
                probe('with', ii, 'caught', e)
                break
            except BaseException as e:
                probe('with', ii, 'caught', e)
                raise
            exc = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([Raised(f'with-{ii}'), KeyboardInterrupt()]),
                )
            )
            if exc is not None:
                probe('with', {ii}, 'raise', f'{exc!r}')
                raise exc
        probe('exiting')
    probe('exited')
