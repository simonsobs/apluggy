import contextlib
from typing import Any, Generator, TypeVar

from hypothesis import strategies as st

from .exc import Raised, Thrown
from .utils import Probe

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
