import contextlib
from collections.abc import MutableSequence
from typing import Any, Generator, TypeVar

from hypothesis import strategies as st

from .exc import Raised, Thrown
from .utils import Probe

T = TypeVar('T')

GenCtxManager = contextlib._GeneratorContextManager


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


def run_generator_context(
    ctx: GenCtxManager[T], draw: st.DrawFn, yields: MutableSequence[T], n_sends: int
) -> None:
    with ctx as y:
        yields.append(y)
        if draw(st.booleans()):
            raise Raised('w-s')
        for i in range(n_sends, 0, -1):
            action = draw(st.sampled_from(['send', 'throw', 'close']))
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
                break

            if draw(st.booleans()):
                raise Raised(f'w-{i}')
