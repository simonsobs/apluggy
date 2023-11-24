import contextlib
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return nested_with_single(ctxs)
        # case 2:
        #     return stack_with_double(ctxs)
        # case 3:
        #     return stack_with_triple(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.contextmanager
def nested_with_single(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
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
