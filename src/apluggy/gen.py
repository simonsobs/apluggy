import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from _typeshed import OptExcInfo

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


@contextlib.contextmanager
def stack_gen_ctxs(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    '''Manage multiple context managers with the support of the `gen` attribute.'''

    try:
        entered = list[GenCtxMngr]()
        ys = []
        for ctx in ctxs:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)

        sent = yield ys

        while entered:
            exc_info_: OptExcInfo = (None, None, None)

            ys = []
            for ctx in list(reversed(entered)):
                if exc_info_ == (None, None, None):
                    try:
                        y = ctx.gen.send(sent)
                        ys.append(y)
                    except StopIteration:
                        entered.remove(ctx)
                    except BaseException:
                        entered.remove(ctx)
                        exc_info_ = sys.exc_info()
                else:
                    entered.remove(ctx)
                    try:
                        if ctx.__exit__(*exc_info_):
                            exc_info_ = (None, None, None)
                    except BaseException:
                        exc_info_ = sys.exc_info()

            if isinstance(exc_info_[1], BaseException):
                raise exc_info_[1].with_traceback(exc_info_[2])

            if entered:
                sent = yield ys

    except BaseException:
        exc_info = sys.exc_info()
    else:
        exc_info = (None, None, None)
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
