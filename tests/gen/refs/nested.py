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
            sent = None
            raised = False
            ys_next = list[T]()
            try:
                try:
                    if not in_ctx1:
                        sent = yield ys
                    else:
                        try:
                            try:
                                try:
                                    sent = yield ys
                                except BaseException:
                                    raised = True
                                    raise
                            except GeneratorExit:
                                ctx1.gen.close()
                                raise
                            except BaseException:
                                try:
                                    exc_info = sys.exc_info()
                                    ctx1.gen.throw(*exc_info)
                                except StopIteration:
                                    in_ctx1 = False
                            else:
                                assert not raised
                                try:
                                    y = ctx1.gen.send(sent)
                                    ys_next.append(y)
                                except StopIteration:
                                    in_ctx1 = False
                        except BaseException:
                            in_ctx1 = False
                            raise
                except BaseException:
                    if not in_ctx0:
                        raise
                    try:
                        raise
                    except GeneratorExit:
                        ctx0.gen.close()
                        raise
                    except BaseException:
                        try:
                            exc_info = sys.exc_info()
                            ctx0.gen.throw(*exc_info)
                        except StopIteration:
                            in_ctx0 = False
                else:
                    if in_ctx0:
                        if raised:  # The exception was handled by ctx1.
                            break  # To match the exit stack implementation.
                        try:
                            y = ctx0.gen.send(sent)
                            ys_next.append(y)
                        except StopIteration:
                            in_ctx0 = False
            except BaseException:
                in_ctx0 = False
                raise

            ys = ys_next


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
            sent = None
            ys_next = list[T]()
            try:
                try:
                    if not any([in_ctx1, in_ctx2]):
                        sent = yield ys
                    else:
                        try:
                            try:
                                if not in_ctx2:
                                    sent = yield ys
                                else:
                                    try:
                                        try:
                                            sent = yield ys
                                        except GeneratorExit:
                                            ctx2.gen.close()
                                            raise
                                        except BaseException:
                                            try:
                                                exc_info = sys.exc_info()
                                                ctx2.gen.throw(*exc_info)
                                            except StopIteration:
                                                in_ctx2 = False
                                        else:
                                            try:
                                                y = ctx2.gen.send(sent)
                                                ys_next.append(y)
                                            except StopIteration:
                                                in_ctx2 = False
                                    except BaseException:
                                        in_ctx2 = False
                                        raise
                            except GeneratorExit:
                                ctx1.gen.close()
                                raise
                            except BaseException:
                                try:
                                    exc_info = sys.exc_info()
                                    ctx1.gen.throw(*exc_info)
                                except StopIteration:
                                    in_ctx1 = False
                            else:
                                try:
                                    y = ctx1.gen.send(sent)
                                    ys_next.append(y)
                                except StopIteration:
                                    in_ctx1 = False
                        except BaseException:
                            in_ctx1 = False
                            raise
                except GeneratorExit:
                    ctx0.gen.close()
                    raise
                except BaseException:
                    try:
                        exc_info = sys.exc_info()
                        ctx0.gen.throw(*exc_info)
                    except StopIteration:
                        in_ctx0 = False
                else:
                    try:
                        y = ctx0.gen.send(sent)
                        ys_next.append(y)
                    except StopIteration:
                        in_ctx0 = False
            except BaseException:
                in_ctx0 = False
                raise

            ys = ys_next


@contextlib.contextmanager
def nested_with_quadruple(  # noqa: C901
    ctxs: Sequence[GenCtxMngr[T]],
) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 4
    ctx0, ctx1, ctx2, ctx3 = ctxs
    with ctx0 as y0, ctx1 as y1, ctx2 as y2, ctx3 as y3:
        in_ctx0 = True
        in_ctx1 = True
        in_ctx2 = True
        in_ctx3 = True
        ys = [y0, y1, y2, y3]
        while any([in_ctx0, in_ctx1, in_ctx2, in_ctx3]):
            sent = None
            ys_next = list[T]()
            try:
                try:
                    if not any([in_ctx1, in_ctx2, in_ctx3]):
                        sent = yield ys
                    else:
                        try:
                            try:
                                if not any([in_ctx2, in_ctx3]):
                                    sent = yield ys
                                else:
                                    try:
                                        try:
                                            if not in_ctx3:
                                                sent = yield ys
                                            else:
                                                try:
                                                    try:
                                                        sent = yield ys
                                                    except GeneratorExit:
                                                        ctx3.gen.close()
                                                        raise
                                                    except BaseException:
                                                        try:
                                                            exc_info = sys.exc_info()
                                                            ctx3.gen.throw(*exc_info)
                                                        except StopIteration:
                                                            in_ctx3 = False
                                                    else:
                                                        try:
                                                            y = ctx3.gen.send(sent)
                                                            ys_next.append(y)
                                                        except StopIteration:
                                                            in_ctx3 = False
                                                except BaseException:
                                                    in_ctx3 = False
                                                    raise
                                        except GeneratorExit:
                                            ctx2.gen.close()
                                            raise
                                        except BaseException:
                                            try:
                                                exc_info = sys.exc_info()
                                                ctx2.gen.throw(*exc_info)
                                            except StopIteration:
                                                in_ctx2 = False
                                        else:
                                            try:
                                                y = ctx2.gen.send(sent)
                                                ys_next.append(y)
                                            except StopIteration:
                                                in_ctx2 = False
                                    except BaseException:
                                        in_ctx2 = False
                                        raise
                            except GeneratorExit:
                                ctx1.gen.close()
                                raise
                            except BaseException:
                                try:
                                    exc_info = sys.exc_info()
                                    ctx1.gen.throw(*exc_info)
                                except StopIteration:
                                    in_ctx1 = False
                            else:
                                try:
                                    y = ctx1.gen.send(sent)
                                    ys_next.append(y)
                                except StopIteration:
                                    in_ctx1 = False
                        except BaseException:
                            in_ctx1 = False
                            raise
                except GeneratorExit:
                    ctx0.gen.close()
                    raise
                except BaseException:
                    try:
                        exc_info = sys.exc_info()
                        ctx0.gen.throw(*exc_info)
                    except StopIteration:
                        in_ctx0 = False
                else:
                    try:
                        y = ctx0.gen.send(sent)
                        ys_next.append(y)
                    except StopIteration:
                        in_ctx0 = False
            except BaseException:
                in_ctx0 = False
                raise

            ys = ys_next
