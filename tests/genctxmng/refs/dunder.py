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
    active = set(ctxs)
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
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
                    except BaseException:
                        active.remove(ctx1)
                        exc_info = sys.exc_info()

                if ctx0 in active:
                    if exc_info == (None, None, None):
                        try:
                            y0 = ctx0.gen.send(sent)
                            ys.append(y0)
                        except StopIteration:
                            active.remove(ctx0)
                        except BaseException:
                            active.remove(ctx0)
                            exc_info = sys.exc_info()
                    else:
                        active.remove(ctx0)
                        try:
                            if ctx0.__exit__(*exc_info):
                                exc_info = (None, None, None)
                        except BaseException:
                            exc_info = sys.exc_info()

                if exc_info != (None, None, None):
                    assert isinstance(exc_info[1], BaseException)
                    raise exc_info[1].with_traceback(exc_info[2])
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
    active = list(reversed(ctxs))
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
            y2 = ctx2.__enter__()
            try:
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
                            except BaseException:
                                active.remove(ctx)
                                exc_info = sys.exc_info()
                        else:
                            active.remove(ctx)
                            try:
                                if ctx.__exit__(*exc_info):
                                    exc_info = (None, None, None)
                            except BaseException:
                                exc_info = sys.exc_info()

                    if exc_info != (None, None, None):
                        assert isinstance(exc_info[1], BaseException)
                        raise exc_info[1].with_traceback(exc_info[2])
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
