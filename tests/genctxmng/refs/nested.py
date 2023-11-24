import contextlib
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return nested_with_single(ctxs)
        case 2:
            return nested_with_double(ctxs)
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


@contextlib.contextmanager
def nested_with_double(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    active = set(ctxs)
    with ctx0 as y0, ctx1 as y1:
        ys = [y0, y1]
        while active:
            sent = yield ys
            ys = []
            try:
                try:
                    if ctx1 in active:
                        y1 = ctx1.gen.send(sent)
                        ys.append(y1)
                except StopIteration:
                    active.remove(ctx1)

                if ctx0 in active:
                    y0 = ctx0.gen.send(sent)
                    ys.append(y0)
            except StopIteration:
                active.remove(ctx0)
