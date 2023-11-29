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
            sent = yield ys
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
            sent = yield ys
            ys = list[T]()
            try:
                try:
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
                    try:
                        ctx0.gen.throw(*sys.exc_info())
                    except StopIteration:
                        in_ctx0 = False
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
            ys = list[T]()
            try:
                try:
                    if any([in_ctx1, in_ctx2]):
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
                                try:
                                    exc_info = sys.exc_info()
                                    ctx1.gen.throw(*exc_info)
                                except StopIteration:
                                    in_ctx1 = False
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
                    try:
                        exc_info = sys.exc_info()
                        ctx0.gen.throw(*exc_info)
                    except StopIteration:
                        in_ctx0 = False
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
