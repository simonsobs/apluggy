import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


def nested_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
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
def nested_with_null(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert not ctxs
    yield []


@contextlib.contextmanager
def nested_with_single(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
    with ctx as y:
        in_ctx = True
        ys = [y]
        while in_ctx:
            try:
                sent = yield ys
            except GeneratorExit:  # close() was called or garbage collected
                ctx.gen.close()
                raise  # re-raise if ctx hasn't raised any exception
            except BaseException:
                try:
                    ctx.gen.throw(*sys.exc_info())
                except StopIteration:
                    in_ctx = False
            else:
                ys = []
                try:
                    y = ctx.gen.send(sent)
                    ys.append(y)
                except StopIteration:
                    in_ctx = False


@contextlib.contextmanager
def nested_with_double(  # noqa: C901
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 2
    ctx0, ctx1 = ctxs
    with ctx0 as y0, ctx1 as y1:
        in_ctx0 = True
        in_ctx1 = True
        ys = [y0, y1]
        while in_ctx0 or in_ctx1:
            try:
                try:
                    sent = None
                    try:
                        sent = yield ys
                    finally:
                        ys = []
                except GeneratorExit:
                    if not in_ctx1:
                        raise
                    ctx1.gen.close()
                    raise
                except BaseException:
                    if not in_ctx1:
                        raise
                    try:
                        exc_info = sys.exc_info()
                        ctx1.gen.throw(*exc_info)
                    except StopIteration as e:
                        in_ctx1 = False
                        if e is exc_info[1]:
                            raise
                    except BaseException:
                        in_ctx1 = False
                        raise
                else:
                    if in_ctx1:
                        try:
                            y1 = ctx1.gen.send(sent)
                            ys.append(y1)
                        except StopIteration:
                            in_ctx1 = False
                        except BaseException:
                            in_ctx1 = False
                            raise
            except GeneratorExit:
                if not in_ctx0:
                    raise
                ctx0.gen.close()
                raise
            except BaseException:
                if not in_ctx0:
                    raise
                try:
                    exc_info = sys.exc_info()
                    ctx0.gen.throw(*exc_info)
                except StopIteration as e:
                    in_ctx0 = False
                    if e is exc_info[1]:
                        raise
                except BaseException:
                    in_ctx0 = False
                    raise
            else:
                if in_ctx0:
                    try:
                        y1 = ctx0.gen.send(sent)
                        ys.append(y1)
                    except StopIteration:
                        in_ctx0 = False
                    except BaseException:
                        in_ctx0 = False
                        raise


@contextlib.contextmanager
def nested_with_triple(  # noqa: C901
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 3
    ctx0, ctx1, ctx2 = ctxs
    with ctx0 as y0, ctx1 as y1, ctx2 as y2:
        in_ctx0 = True
        in_ctx1 = True
        in_ctx2 = True
        ys = [y0, y1, y2]
        while any([in_ctx0, in_ctx1, in_ctx2]):
            sent = yield ys
            ys = []
            try:
                try:
                    if in_ctx2:
                        try:
                            y = ctx2.gen.send(sent)
                            ys.append(y)
                        except StopIteration:
                            in_ctx2 = False
                        except BaseException:
                            in_ctx2 = False
                            raise
                except BaseException:
                    if not in_ctx1:
                        raise
                    in_ctx1 = False
                    try:
                        if not ctx1.__exit__(*sys.exc_info()):
                            raise
                    except BaseException:
                        raise
                else:
                    if in_ctx1:
                        try:
                            y = ctx1.gen.send(sent)
                            ys.append(y)
                        except StopIteration:
                            in_ctx1 = False
                        except BaseException:
                            in_ctx1 = False
                            raise
            except BaseException:
                if not in_ctx0:
                    raise
                in_ctx0 = False
                try:
                    if not ctx0.__exit__(*sys.exc_info()):
                        raise
                except BaseException:
                    raise
            else:
                if in_ctx0:
                    try:
                        y = ctx0.gen.send(sent)
                        ys.append(y)
                    except StopIteration:
                        in_ctx0 = False
                    except BaseException:
                        in_ctx0 = False
                        raise


@contextlib.contextmanager
def nested_with_quadruple(
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 4
    ctx0, ctx1, ctx2, ctx3 = ctxs
    active = list(reversed(ctxs))
    with ctx0 as y0, ctx1 as y1, ctx2 as y2, ctx3 as y3:
        ys = [y0, y1, y2, y3]
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
