import contextlib
from collections.abc import Callable, Iterable, MutableSequence
from typing import Any, TypeVar

from hypothesis import given
from hypothesis import strategies as st

from .utils import Probe, RecordReturns, ReplayReturns

T = TypeVar('T')

GenCtxManager = contextlib._GeneratorContextManager


def test_probe():
    def f(probe: Probe):
        probe()
        probe()

    probe1 = Probe()
    probe2 = Probe()
    assert probe1.calls == probe2.calls


class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `contextmanager.gen.throw()`.
    '''

    pass


class Raised(Exception):
    pass


@contextlib.contextmanager
def context(draw: st.DrawFn, probe: Probe, id: int, n_sends: int = 0):
    probe(id)

    if draw(st.booleans()):
        probe(id)
        raise Raised()

    for i in range(n_sends, 0, -1):
        try:
            sent = yield f'yield {id} ({i})'
            probe(id, i, sent)
        except (Raised, Thrown) as e:
            probe(id, i, e)
            raise  # or RuntimeError("generator didn't stop after throw()")
        probe(id, i)
        if draw(st.booleans()):
            probe(id, i)
            raise Raised()
        probe(id, i)

    try:
        yield f'yield {id}'
        probe(id)
    except (Raised, Thrown) as e:
        probe(id, e)
        if draw(st.booleans()):
            probe(id)
            raise
    probe(id)
    if draw(st.booleans()):
        probe(id)
        raise Raised()
    probe(id)


def with_single_context(
    context: GenCtxManager[T],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int = 0,
) -> None:
    with context as y:
        yields.append([y])
        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            if draw(st.booleans()):
                context.gen.throw(Thrown())
            y = context.gen.send(f'send({i})')
            yields.append([y])


def with_exit_stack(
    context: Iterable[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int = 0,
):
    assert n_sends == 0
    with contextlib.ExitStack() as stack:
        ys = [stack.enter_context(ctx) for ctx in context]
        yields.append(ys)
        if draw(st.booleans()):
            raise Raised()


def run(probe: Probe, f: Callable[[], T]) -> T | None:
    ret = None
    try:
        ret = f()
        probe()
    except (Raised, Thrown) as e:
        probe(e)
    return ret


@given(st.data())
def test_context(data: st.DataObject):
    n_sends = data.draw(st.integers(min_value=0, max_value=5))
    draw = RecordReturns(data.draw)
    probe1 = Probe()
    ctx = context(draw=draw, probe=probe1, id=1, n_sends=n_sends)
    yields1 = list[Any]()
    run(
        probe1,
        lambda: with_single_context(
            context=ctx, draw=draw, yields=yields1, n_sends=n_sends
        ),
    )

    replay = ReplayReturns(draw)
    probe2 = Probe()
    ctx = context(draw=replay, probe=probe2, id=1, n_sends=n_sends)
    yields2 = list[Any]()
    run(
        probe2,
        lambda: with_single_context(
            context=ctx, draw=replay, yields=yields2, n_sends=n_sends
        ),
    )

    assert probe1.calls == probe2.calls
    assert yields1 == yields2
    # ic(probe1.calls)
    # ic(yields1)

    if n_sends == 0:
        replay = ReplayReturns(draw)
        probe3 = Probe()
        ctx = context(draw=replay, probe=probe3, id=1, n_sends=n_sends)
        yields3 = list[Any]()
        run(
            probe3,
            lambda: with_exit_stack(
                context=[ctx], draw=replay, yields=yields3, n_sends=n_sends
            ),
        )
        assert probe1.calls == probe3.calls
        assert yields1 == yields3
        # ic(probe1.calls)
        # ic(yields1)
