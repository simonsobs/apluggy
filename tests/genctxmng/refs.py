import contextlib
from collections.abc import Generator, MutableSequence, Sequence
from typing import Any, Generic, Protocol, TypeVar

from hypothesis import strategies as st

from .exc import Raised, Thrown

T = TypeVar('T')

GenCtxManager = contextlib._GeneratorContextManager


class Impl(Protocol, Generic[T]):
    def __call__(
        self,
        contexts: Sequence[GenCtxManager[T]],
        draw: st.DrawFn,
        yields: MutableSequence[list[T]],
        n_sends: int,
    ) -> None:
        ...


@contextlib.contextmanager
def stack_with_single(
    contexts: Sequence[GenCtxManager[T]],
) -> Generator[list[T], Any, Any]:
    assert len(contexts) == 1
    ctx = contexts[0]
    with ctx as y:
        ys = [y]
        sent = yield ys
        while True:
            ys = []
            try:
                y = ctx.gen.send(sent)
                ys.append(y)
            except StopIteration:
                break
            sent = yield ys


def with_single_context(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    ctx = stack_with_single(contexts=contexts)
    run_generator_context(ctx=ctx, draw=draw, yields=yields, n_sends=n_sends)


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
