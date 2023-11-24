import contextlib
from collections.abc import Generator, MutableSequence, Sequence
from typing import Any, Generic, Protocol, TypeVar

from hypothesis import strategies as st

from .runner import run_generator_context

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
