import contextlib
from collections.abc import MutableSequence, Sequence
from typing import Generic, Protocol, TypeVar

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


def with_single_context(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 1
    ctx = contexts[0]
    with ctx as y:
        yields.append([y])
        if draw(st.booleans()):
            raise Raised('w-s')
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                match action:
                    case 'send':
                        y = ctx.gen.send(f'send({i})')
                        ys.append(y)
                    case 'throw':
                        ctx.gen.throw(Thrown(f'{i}'))
                    case 'close':
                        ctx.gen.close()
            except StopIteration:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised(f'w-{i}')
