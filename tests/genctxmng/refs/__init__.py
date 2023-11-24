import contextlib
import sys
from collections.abc import Generator, Sequence
from typing import Any, Generic, Protocol, TypeVar

T = TypeVar('T')

GenCtxMngr = contextlib._GeneratorContextManager


class Stack(Protocol, Generic[T]):
    def __call__(self, ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
        ...


@contextlib.contextmanager
def exit_stack(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    with contextlib.ExitStack() as stack:
        yield [stack.enter_context(ctx) for ctx in ctxs]


def nested_with(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return nested_with_single(ctxs)
        # case 2:
        #     return stack_with_double(ctxs)
        # case 3:
        #     return stack_with_triple(ctxs)
        case _:
            raise NotImplementedError()


@contextlib.contextmanager
def nested_with_single(ctxs: Sequence[GenCtxMngr[T]]) -> Generator[list[T], Any, Any]:
    assert len(ctxs) == 1
    ctx = ctxs[0]
    with ctx as y:
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


def dunder_enter(ctxs: Sequence[GenCtxMngr[T]]) -> GenCtxMngr[list[T]]:
    match len(ctxs):
        case 1:
            return dunder_enter_single(ctxs)
        # case 2:
        #     return stack_with_double(ctxs)
        # case 3:
        #     return stack_with_triple(ctxs)
        case _:
            raise NotImplementedError()


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
