import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, TypeVar


T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


@contextlib.contextmanager
def stack_gen_ctxs(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    exc_info = sys.exc_info()
    assert exc_info == (None, None, None)
    entered = list[GenCtxMngr]()
    try:
        ys = []
        for ctx in ctxs:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)

        sent = yield ys

        active = list(reversed(ctxs))
        while active:
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

            if active:
                sent = yield ys

    except BaseException:
        exc_info = sys.exc_info()
    finally:
        while entered:
            ctx = entered.pop()
            try:
                if ctx.__exit__(*exc_info):
                    exc_info = (None, None, None)
            except BaseException:
                exc_info = sys.exc_info()

        if exc_info != (None, None, None):
            assert isinstance(exc_info[1], BaseException)
            raise exc_info[1].with_traceback(exc_info[2])
