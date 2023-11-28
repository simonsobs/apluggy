import contextlib
from collections.abc import Generator, Sequence
import sys
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from _typeshed import OptExcInfo

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


@contextlib.contextmanager
def stack_gen_ctxs(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    '''Manage multiple context managers with the support of the `gen` attribute.

    A context manager can receive values inside the `with` block with multiple
    `yield` statements. You can send a value to the context manager with the
    `send()` method of the `gen` attribute as explained in
    https://stackoverflow.com/a/68304565/7309855.

    This function lets you stack multiple context managers each with multiple
    `yield` statements and send values to them.

    Example: Suppose you have two context managers `ctx0` and `ctx1`:

    >>> @contextlib.contextmanager
    ... def ctx0():
    ...     print('ctx0: enter')
    ...     sent = yield 'ctx0: yield 0'
    ...     print('ctx0: received', sent)
    ...     yield 'ctx0: yield 1'
    ...     print('ctx0: exit')

    >>> @contextlib.contextmanager
    ... def ctx1():
    ...     print('ctx1: enter')
    ...     sent = yield 'ctx1: yield 0'
    ...     print('ctx1: received', sent)
    ...     yield 'ctx1: yield 1'
    ...     print('ctx1: exit')

    Stack these context managers with `stack_gen_ctxs()`:

    >>> with (stack := stack_gen_ctxs([ctx0(), ctx1()])) as yields:
    ...     print('main: received', yields)
    ...     yields = stack.gen.send('send 0')
    ...     print('main: received', yields)
    ctx0: enter
    ctx1: enter
    main: received ['ctx0: yield 0', 'ctx1: yield 0']
    ctx1: received send 0
    ctx0: received send 0
    main: received ['ctx1: yield 1', 'ctx0: yield 1']
    ctx1: exit
    ctx0: exit

    As the output indicates, the context managers are called in the reverse
    order after the first `yield` statement as if they were nested with the
    `with` block. In the above example, `ctx1` is the inner context manager and
    `ctx0` is the outer context manager.

    In addition to the `send()` method, you can also use the `throw()` and `close()`
    methods of the `gen` attribute.

    An exception will be propagated from an inner context manager to an outer
    context manager. The propagation stops if a context manager handles the
    exception.
    '''

    try:
        # Append a context manager as it is entered and remove one as it is exited.
        entered = list[GenCtxMngr]()

        ys = []
        for ctx in ctxs:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)

        while True:
            sent = None
            try:
                sent = yield ys
            except BaseException:
                exc_info = sys.exc_info()
            else:
                exc_info = (None, None, None)

            ys = []

            for ctx in list(reversed(entered)):
                try:
                    match exc_info[1]:
                        case val if isinstance(val, GeneratorExit):
                            ctx.gen.close()
                        case val if isinstance(val, BaseException):
                            try:
                                ctx.gen.throw(*exc_info)
                            except StopIteration:
                                entered.remove(ctx)
                            exc_info = (None, None, None)
                        case None:
                            try:
                                y = ctx.gen.send(sent)
                                ys.append(y)
                            except StopIteration:
                                entered.remove(ctx)
                        case _:
                            raise NotImplementedError()
                except BaseException:
                    entered.remove(ctx)
                    exc_info = sys.exc_info()

            if isinstance(exc_info[1], BaseException):
                raise exc_info[1].with_traceback(exc_info[2])

            if not entered:
                break                    

        # # Yield at least once even when an empty `ctxs` is given.
        # sent = yield ys

        # while entered:
        #     exc_info_: OptExcInfo = (None, None, None)
        #     ys = []
        #     for ctx in list(reversed(entered)):  # From the innermost to outwards.
        #         if exc_info_ == (None, None, None):
        #             try:
        #                 y = ctx.gen.send(sent)
        #                 ys.append(y)
        #             except StopIteration:  # `ctx` has exited.
        #                 entered.remove(ctx)
        #             except BaseException:
        #                 entered.remove(ctx)
        #                 exc_info_ = sys.exc_info()
        #         else:  # An exception is outstanding.
        #             entered.remove(ctx)
        #             try:
        #                 if ctx.__exit__(*exc_info_):
        #                     # The exception is handled.
        #                     exc_info_ = (None, None, None)
        #             except BaseException:  # A new or the same exception is raised.
        #                 exc_info_ = sys.exc_info()

        #     if isinstance(exc_info_[1], BaseException):
        #         # An exception is still outstanding after the outermost context manager.
        #         raise exc_info_[1].with_traceback(exc_info_[2])

        #     if entered:  # Avoid yielding after all context managers have exited.
        #         sent = yield ys

    except BaseException:
        exc_info = sys.exc_info()
    else:
        exc_info = (None, None, None)
    finally:
        # Exit the remaining context managers from the innermost to the outermost.
        while entered:
            ctx = entered.pop()
            try:
                if ctx.__exit__(*exc_info):
                    # The exception is handled.
                    exc_info = (None, None, None)
            except BaseException:  # A new or the same exception is raised.
                exc_info = sys.exc_info()

        if isinstance(exc_info[1], BaseException):
            # An exception is unhandled after all context managers have exited.
            raise exc_info[1].with_traceback(exc_info[2])
