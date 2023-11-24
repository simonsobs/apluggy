import contextlib
from collections.abc import Generator, Sequence
import sys
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return nested_with_single(ctxs)
        case 2:
            return nested_with_double(ctxs)
        case 3:
            return nested_with_triple(ctxs)
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
            exc_info = sys.exc_info()
            assert exc_info == (None, None, None)
            ys = []

            if ctx1 in active:
                try:
                    y1 = ctx1.gen.send(sent)
                    ys.append(y1)
                except StopIteration:
                    active.remove(ctx1)
                except Exception:
                    active.remove(ctx1)
                    exc_info = sys.exc_info()

            if ctx0 in active:
                if exc_info == (None, None, None):
                    try:
                        y0 = ctx0.gen.send(sent)
                        ys.append(y0)
                    except StopIteration:
                        active.remove(ctx0)
                    except Exception:
                        active.remove(ctx0)
                        exc_info = sys.exc_info()
                else:
                    active.remove(ctx0)
                    try:
                        if ctx0.__exit__(*exc_info):
                            exc_info = (None, None, None)
                    except Exception:
                        exc_info = sys.exc_info()

            if exc_info != (None, None, None):
                assert isinstance(exc_info[1], BaseException)
                raise exc_info[1].with_traceback(exc_info[2])


@contextlib.contextmanager
def nested_with_triple(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    active = list(reversed(ctxs))
    with ctx0 as y0, ctx1 as y1, ctx2 as y2:
        ys = [y0, y1, y2]
        while active:
            sent = yield ys
            exc_info = sys.exc_info()
            assert exc_info == (None, None, None)
            ys = []

            for ctx in list(active):
                if exc_info == (None, None, None):
                    try:
                        y = ctx.gen.send(sent)
                        ys.append(y)
                    except StopIteration:
                        active.remove(ctx)
                    except Exception:
                        active.remove(ctx)
                        exc_info = sys.exc_info()
                else:
                    active.remove(ctx)
                    try:
                        if ctx.__exit__(*exc_info):
                            exc_info = (None, None, None)
                    except Exception:
                        exc_info = sys.exc_info()

            if exc_info != (None, None, None):
                assert isinstance(exc_info[1], BaseException)
                raise exc_info[1].with_traceback(exc_info[2])
