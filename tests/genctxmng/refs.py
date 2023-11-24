import contextlib
from collections.abc import Generator, MutableSequence, Sequence
from typing import Any, Generic, Protocol, TypeVar

from hypothesis import strategies as st

from .runner import run_generator_context

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


class Impl(Protocol, Generic[T]):
    def __call__(
        self,
        contexts: Sequence[GenCtxMngr[T]],
        draw: st.DrawFn,
        yields: MutableSequence[list[T]],
        n_sends: int,
    ) -> None:
        ...


class Stack(Protocol, Generic[T]):
    def __call__(self, ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
        ...


@contextlib.contextmanager
def stack_with_single(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
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
    contexts: Sequence[GenCtxMngr[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    stack: Stack = stack_with_single
    ctx = stack(ctxs=contexts)
    run_generator_context(ctx=ctx, draw=draw, yields=yields, n_sends=n_sends)
