import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from .types import GenCtxMngr

if TYPE_CHECKING:
    from _typeshed import OptExcInfo

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
    in_ctx = True
    try:
        ys = [y]
        while in_ctx:
            sent = yield ys
            ys = []
            try:
                y = ctx.gen.send(sent)
                ys.append(y)
            except StopIteration:
                in_ctx = False
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
            ys = [y0, y1]
            active = set(ctxs)
            while active:
                sent = yield ys
                ys = list[T]()

                exc_info: OptExcInfo = (None, None, None)

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
                    try:
                        if isinstance(exc_info[1], BaseException):
                            try:
                                ctx0.gen.throw(*exc_info)
                            except StopIteration:
                                active.remove(ctx0)
                            exc_info = (None, None, None)
                        else:
                            try:
                                y0 = ctx0.gen.send(sent)
                                ys.append(y0)
                            except StopIteration:
                                active.remove(ctx0)
                    except BaseException:
                        active.remove(ctx0)
                        exc_info = sys.exc_info()
                    else:
                        exc_info = (None, None, None)

                if isinstance(exc_info[1], BaseException):
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
    y0 = ctx0.__enter__()
    try:
        y1 = ctx1.__enter__()
        try:
            y2 = ctx2.__enter__()
            try:
                ys = [y0, y1, y2]
                active = list(reversed(ctxs))
                while active:
                    sent = yield ys
                    ys = list[T]()
                    exc_info: OptExcInfo = (None, None, None)

                    for ctx in list(active):
                        try:
                            if isinstance(exc_info[1], BaseException):
                                try:
                                    ctx.gen.throw(*exc_info)
                                except StopIteration:
                                    active.remove(ctx)
                                exc_info = (None, None, None)
                            else:
                                try:
                                    y = ctx.gen.send(sent)
                                    ys.append(y)
                                except StopIteration:
                                    active.remove(ctx)
                        except BaseException:
                            active.remove(ctx)
                            exc_info = sys.exc_info()
                        else:
                            exc_info = (None, None, None)

                    if isinstance(exc_info[1], BaseException):
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


@contextlib.contextmanager
def dunder_enter_quadruple(  # noqa: C901
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
                    ys = [y0, y1, y2, y3]
                    active = list(reversed(ctxs))
                    while active:
                        sent = yield ys
                        ys = list[T]()
                        exc_info: OptExcInfo = (None, None, None)

                        for ctx in list(active):
                            try:
                                if isinstance(exc_info[1], BaseException):
                                    try:
                                        ctx.gen.throw(*exc_info)
                                    except StopIteration:
                                        active.remove(ctx)
                                    exc_info = (None, None, None)
                                else:
                                    try:
                                        y = ctx.gen.send(sent)
                                        ys.append(y)
                                    except StopIteration:
                                        active.remove(ctx)
                            except BaseException:
                                active.remove(ctx)
                                exc_info = sys.exc_info()
                            else:
                                exc_info = (None, None, None)

                        if isinstance(exc_info[1], BaseException):
                            raise exc_info[1].with_traceback(exc_info[2])

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
