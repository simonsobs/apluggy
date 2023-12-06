import contextlib
from collections.abc import Generator, Iterable
from typing import Any, TypeVar

from apluggy.stack import GenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Iterable[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    ctxs = list(ctxs)
    match len(ctxs):
        case 0:
            return nested_with_null(ctxs)
        case 1:
            return nested_with_single(ctxs)
        case 2:
            return nested_with_double(ctxs)
        case 3:
            return nested_with_triple(ctxs)
        case 4:
            return nested_with_quadruple(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.contextmanager
def nested_with_null(ctxs: Iterable[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert not ctxs
    yield []


@contextlib.contextmanager
def nested_with_single(ctxs: Iterable[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 1
    ctx = ctxs[0]
    with ctx as y:
        sent = yield [y]
        try:
            while True:
                sent = yield [ctx.gen.send(sent)]
        except StopIteration:
            pass


@contextlib.contextmanager
def nested_with_double(ctxs: Iterable[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    with ctx0 as y0, ctx1 as y1:
        sent = yield [y0, y1]
        try:
            while True:
                sent = yield [ctx1.gen.send(sent), ctx0.gen.send(sent)]
        except StopIteration:
            pass


@contextlib.contextmanager
def nested_with_triple(ctxs: Iterable[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    with ctx0 as y0, ctx1 as y1, ctx2 as y2:
        sent = yield [y0, y1, y2]
        try:
            while True:
                sent = yield [
                    ctx2.gen.send(sent),
                    ctx1.gen.send(sent),
                    ctx0.gen.send(sent),
                ]
        except StopIteration:
            pass


@contextlib.contextmanager
def nested_with_quadruple(
    ctxs: Iterable[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    ctxs = list(ctxs)
    assert len(ctxs) == 4
    ctx0, ctx1, ctx2, ctx3 = ctxs
    with ctx0 as y0, ctx1 as y1, ctx2 as y2, ctx3 as y3:
        sent = yield [y0, y1, y2, y3]
        try:
            while True:
                sent = yield [
                    ctx3.gen.send(sent),
                    ctx2.gen.send(sent),
                    ctx1.gen.send(sent),
                    ctx0.gen.send(sent),
                ]
        except StopIteration:
            pass
