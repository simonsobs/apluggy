import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


@contextlib.contextmanager
def stack_gen_ctxs(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    '''Manage multiple context managers with the support of the `gen` attribute.'''

    exc_info = sys.exc_info()  # for type hint. should be (None, None, None)
    exc_info = (None, None, None)  # set explicitly to ensure
    try:
        entered = list[GenCtxMngr]()
        ys = []
        for ctx in ctxs:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)

        sent = yield ys

        while entered:
            exc_info = (None, None, None)

            ys = []
            for ctx in list(reversed(entered)):
                if exc_info == (None, None, None):
                    try:
                        y = ctx.gen.send(sent)
                        ys.append(y)
                    except StopIteration:
                        entered.remove(ctx)
                    except BaseException:
                        entered.remove(ctx)
                        exc_info = sys.exc_info()
                else:
                    entered.remove(ctx)
                    try:
                        if ctx.__exit__(*exc_info):
                            exc_info = (None, None, None)
                    except BaseException:
                        exc_info = sys.exc_info()

            if isinstance(exc_info[1], BaseException):
                raise exc_info[1].with_traceback(exc_info[2])

            if entered:
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

        if isinstance(exc_info[1], BaseException):
            raise exc_info[1].with_traceback(exc_info[2])
