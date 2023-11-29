import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


def dunder_enter(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 0:
            return dunder_enter_null(ctxs)
        case 1:
            return dunder_enter_single(ctxs)
        case 2:
            return dunder_enter_double(ctxs)
        case 3:
            return dunder_enter_triple(ctxs)
        case 4:
            return dunder_enter_quadruple(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.contextmanager
def dunder_enter_null(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert not ctxs
    yield []


@contextlib.contextmanager
def dunder_enter_single(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
    y = ctx.__enter__()
    try:
        sent = yield [y]
        try:
            while True:
                sent = yield [ctx.gen.send(sent)]
        except StopIteration:
            pass
    except BaseException:
        if not ctx.__exit__(*sys.exc_info()):
            raise
    else:
        ctx.__exit__(None, None, None)


@contextlib.contextmanager
def dunder_enter_double(  # noqa: C901
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
            sent = yield [y0, y1]
            try:
                while True:
                    sent = yield [ctx1.gen.send(sent), ctx0.gen.send(sent)]
            except StopIteration:
                pass
        except BaseException:
            if not ctx1.__exit__(*sys.exc_info()):
                raise
        else:
            ctx1.__exit__(None, None, None)
    except BaseException:
        if not ctx0.__exit__(*sys.exc_info()):
            raise
    else:
        ctx0.__exit__(None, None, None)


@contextlib.contextmanager
def dunder_enter_triple(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
            y2 = ctx2.__enter__()
            try:
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

            except BaseException:
                if not ctx2.__exit__(*sys.exc_info()):
                    raise
            else:
                ctx2.__exit__(None, None, None)
        except BaseException:
            if not ctx1.__exit__(*sys.exc_info()):
                raise
        else:
            ctx1.__exit__(None, None, None)
    except BaseException:
        if not ctx0.__exit__(*sys.exc_info()):
            raise
    else:
        ctx0.__exit__(None, None, None)


@contextlib.contextmanager
def dunder_enter_quadruple(
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 4
    ctx0, ctx1, ctx2, ctx3 = ctxs
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
            y2 = ctx2.__enter__()
            try:
                y3 = ctx3.__enter__()
                try:
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

                except BaseException:
                    if not ctx3.__exit__(*sys.exc_info()):
                        raise
                else:
                    ctx3.__exit__(None, None, None)
            except BaseException:
                if not ctx2.__exit__(*sys.exc_info()):
                    raise
            else:
                ctx2.__exit__(None, None, None)
        except BaseException:
            if not ctx1.__exit__(*sys.exc_info()):
                raise
        else:
            ctx1.__exit__(None, None, None)
    except BaseException:
        if not ctx0.__exit__(*sys.exc_info()):
            raise
    else:
        ctx0.__exit__(None, None, None)
