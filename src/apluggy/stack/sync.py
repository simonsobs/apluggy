import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, TypeVar

from .types import GenCtxMngr

T = TypeVar('T')


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
    `ctx0` is the outer context manager.  The above example is equivalent to
    the following:

    >>> with (c0 := ctx0()) as y0, (c1 := ctx1()) as y1:
    ...     ys = [y0, y1]
    ...     print('main: received', ys)
    ...     sent = 'send 0'
    ...     ys = [c1.gen.send(sent), c0.gen.send(sent)]
    ...     print('main: received', ys)
    ctx0: enter
    ctx1: enter
    main: received ['ctx0: yield 0', 'ctx1: yield 0']
    ctx1: received send 0
    ctx0: received send 0
    main: received ['ctx1: yield 1', 'ctx0: yield 1']
    ctx1: exit
    ctx0: exit

    In addition to the `send()` method, you can also use the `throw()` and `close()`
    methods of the `gen` attribute.

    The context managers can yield any number of times. The first time any of
    the context managers exits, the stack exists after calling the `__exit__()`
    method of the remaining context managers in the reverse order.

    If the argument `ctxs` is empty, the stack yields an empty list and exits.

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

        # Yield at least once even if an empty `ctxs` is given.
        # Receive a value from the `with` block sent by `gen.send()`.
        sent = yield ys

        if ctxs:
            try:
                # Send the received value to the context managers
                # until at least one of them exits.
                while True:
                    sent = yield [ctx.gen.send(sent) for ctx in reversed(ctxs)]
            except StopIteration:
                # A context manager exited.
                pass

    except BaseException:
        exc_info = sys.exc_info()
    else:
        exc_info = (None, None, None)
    finally:
        # Exit the entered context managers from the innermost to the outermost.
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
