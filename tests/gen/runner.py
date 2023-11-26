import contextlib
from collections.abc import MutableSequence
from typing import Any, Generator, TypeVar

from hypothesis import strategies as st

from apluggy.test import Probe

from .exc import Raised, Thrown
from .refs import Stack

T = TypeVar('T')

GenCtxManager = contextlib._GeneratorContextManager


def run(
    draw: st.DrawFn, stack: Stack[T], n_contexts, n_sends: int
) -> tuple[Probe, list[list[T]]]:
    probe = Probe()
    contexts = [
        mock_context(draw=draw, probe=probe, id=i, n_sends=n_sends)
        for i in range(n_contexts)
    ]
    ctx = stack(contexts)
    yields = list[Any]()
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

    return probe, yields


@contextlib.contextmanager
def mock_context(
    draw: st.DrawFn, probe: Probe, id: int, n_sends: int
) -> Generator[Any, Any, Any]:
    probe(id)

    if draw(st.booleans()):
        probe(id)
        raise Raised(f'c-{id}-s')

    for i in range(n_sends, draw(st.integers(min_value=0, max_value=n_sends)), -1):
        probe(id, i)
        try:
            sent = yield f'yield {id} ({i})'
            probe(id, i, sent)
        except GeneratorExit:
            # close() was called or garbage collected
            # Don't probe here because this can happen after the test has finished.
            # probe(id, i)
            raise  # otherwise RuntimeError: generator ignored GeneratorExit
        except (Raised, Thrown) as e:
            probe(id, i, e)
            if draw(st.booleans()):
                probe(id, i)
                raise
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
        if draw(st.booleans()):
            probe(id, e)
            raise

    probe(id)
    if draw(st.booleans()):
        probe(id)
        raise Raised(f'c-{id}-e')
    probe(id)


def run_generator_context(
    ctx: GenCtxManager[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    probe()
    with ctx as y:
        probe()
        yields.append(y)
        if draw(st.booleans()):
            probe()
            raise Raised('w-s')
        if draw(st.booleans()):
            probe()
            raise KeyboardInterrupt()
        for i in range(n_sends, 0, -1):
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            probe(i, action)
            try:
                match action:
                    case 'send':
                        y = ctx.gen.send(f'send({i})')
                        yields.append(y)
                    case 'throw':
                        ctx.gen.throw(Thrown(f'{i}'))
                    case 'close':
                        ctx.gen.close()
            except StopIteration:
                probe()
                break
            except RuntimeError:
                # generator didn't stop
                probe()
                break
            if draw(st.booleans()):
                probe()
                raise Raised(f'w-{i}')
            if draw(st.booleans()):
                probe()
                raise KeyboardInterrupt()
            probe()
        probe()
    probe()
