import contextlib
from collections.abc import Generator, Sequence
from typing import Any, Generic, Protocol, TypeVar

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


class Stack(Protocol, Generic[T]):
    def __call__(self, ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
        ...


def stack_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return stack_with_single(ctxs)
        # case 2:
        #     return stack_with_double(ctxs)
        # case 3:
        #     return stack_with_triple(ctxs)
        case _:
            raise NotImplementedError()


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
