import contextlib
import sys
from collections.abc import Iterable, MutableSequence, Sequence
from typing import Any, Generic, Protocol, TypeVar

from hypothesis import given, settings
from hypothesis import strategies as st

from .utils import Probe, RecordReturns, ReplayReturns

T = TypeVar('T')

GenCtxManager = contextlib._GeneratorContextManager


class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `contextmanager.gen.throw()`.
    '''

    pass


class Raised(Exception):
    pass


@contextlib.contextmanager
def context(draw: st.DrawFn, probe: Probe, id: int, n_sends: int = 0):
    probe(id)

    if draw(st.booleans()):
        probe(id)
        raise Raised()

    for i in range(n_sends, draw(st.integers(min_value=0, max_value=n_sends)), -1):
        try:
            sent = yield f'yield {id} ({i})'
            probe(id, i, sent)
        except (Raised, Thrown, GeneratorExit) as e:
            probe(id, i, e)
            raise  # otherwise RuntimeError('generator didn't stop') by contextlib
        probe(id, i)
        if draw(st.booleans()):
            probe(id, i)
            raise Raised()
        probe(id, i)

    try:
        yield f'yield {id}'
        probe(id)
    except (Raised, Thrown) as e:
        probe(id, e)
        raise  # So that the outer generator context managers stop.

    probe(id)
    if draw(st.booleans()):
        probe(id)
        raise Raised()
    probe(id)


def with_single_context(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 1
    ctx = contexts[0]
    with ctx as y:
        yields.append([y])
        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                match action:
                    case 'send':
                        y = ctx.gen.send(f'send({i})')
                        ys.append(y)
                    case 'throw':
                        ctx.gen.throw(Thrown())
                    case 'close':
                        ctx.gen.close()
            except StopIteration:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()


def with_double_contexts(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 2
    ctx1, ctx2 = contexts
    active = [ctx2, ctx1]
    with ctx1 as y1, ctx2 as y2:
        yields.append([y1, y2])
        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            for ctx in list(active):
                try:
                    match action:
                        case 'send':
                            y = ctx.gen.send(f'send({i})')
                            ys.append(y)
                        case 'throw':
                            ctx.gen.throw(Thrown())
                        case 'close':
                            ctx.gen.close()
                except StopIteration:
                    active.remove(ctx)

            if not active:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()


def with_triple_contexts(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 3
    ctx1, ctx2, ctx3 = contexts
    active = [ctx3, ctx2, ctx1]
    with ctx1 as y1, ctx2 as y2, ctx3 as y3:
        yields.append([y1, y2, y3])
        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            for ctx in list(active):
                try:
                    match action:
                        case 'send':
                            y = ctx.gen.send(f'send({i})')
                            ys.append(y)
                        case 'throw':
                            ctx.gen.throw(Thrown())
                        case 'close':
                            ctx.gen.close()
                except StopIteration:
                    active.remove(ctx)

            if not active:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()


def nested_with(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    match len(contexts):
        case 1:
            imp = with_single_context
        case 2:
            imp = with_double_contexts
        case 3:
            imp = with_triple_contexts
        case _:
            raise NotImplementedError()
    imp(contexts=contexts, draw=draw, yields=yields, n_sends=n_sends)


def enter_single_context(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 1
    ctx = contexts[0]

    y = ctx.__enter__()
    try:
        yields.append([y])
        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                match action:
                    case 'send':
                        y = ctx.gen.send(f'send({i})')
                        ys.append(y)
                    case 'throw':
                        ctx.gen.throw(Thrown())
                    case 'close':
                        ctx.gen.close()
            except StopIteration:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()

    except Exception:
        if not ctx.__exit__(*sys.exc_info()):
            raise
    else:
        ctx.__exit__(None, None, None)


def enter_double_contexts(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    assert len(contexts) == 2
    ctx1, ctx2 = contexts
    active = [ctx2, ctx1]

    y1 = ctx1.__enter__()
    try:
        y2 = ctx2.__enter__()
        try:
            yields.append([y1, y2])
            if draw(st.booleans()):
                raise Raised()
            for i in range(n_sends, 0, -1):
                ys = []
                action = draw(st.sampled_from(['send', 'throw', 'close']))
                for ctx in list(active):
                    try:
                        match action:
                            case 'send':
                                y = ctx.gen.send(f'send({i})')
                                ys.append(y)
                            case 'throw':
                                ctx.gen.throw(Thrown())
                            case 'close':
                                ctx.gen.close()
                    except StopIteration:
                        active.remove(ctx)

                if not active:
                    break

                yields.append(ys)

                if draw(st.booleans()):
                    raise Raised()

        except Exception:
            if not ctx2.__exit__(*sys.exc_info()):
                raise
        else:
            ctx2.__exit__(None, None, None)
    except Exception:
        if not ctx1.__exit__(*sys.exc_info()):
            raise
    else:
        ctx1.__exit__(None, None, None)


def enter_multiple_contexts(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    entered = list[GenCtxManager]()
    try:
        ys = []
        for ctx in contexts:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)
        yields.append(ys)

        active = list(reversed(contexts))

        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            for ctx in list(active):
                try:
                    match action:
                        case 'send':
                            y = ctx.gen.send(f'send({i})')
                            ys.append(y)
                        case 'throw':
                            ctx.gen.throw(Thrown())
                        case 'close':
                            ctx.gen.close()
                except StopIteration:
                    active.remove(ctx)

            if not active:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()

    except Exception:
        exc_info = sys.exc_info()
        while entered:
            ctx = entered.pop()
            if ctx.__exit__(*exc_info):
                break
        else:
            raise
    finally:
        exc_info = (None, None, None)
        while entered:
            ctx = entered.pop()
            try:
                if ctx.__exit__(*exc_info):
                    exc_info = (None, None, None)
            except Exception:
                exc_info = sys.exc_info()

        if exc_info != (None, None, None):
            assert isinstance(exc_info[1], BaseException)
            raise exc_info[1].with_traceback(exc_info[2])


def call_enter(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    match len(contexts):
        case 1:
            imp = enter_single_context
        case 2:
            imp = enter_double_contexts
        case _:
            raise NotImplementedError()
    imp(contexts=contexts, draw=draw, yields=yields, n_sends=n_sends)


def with_exit_stack(
    contexts: Iterable[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
):
    assert n_sends == 0
    with contextlib.ExitStack() as stack:
        ys = [stack.enter_context(ctx) for ctx in contexts]
        yields.append(ys)
        if draw(st.booleans()):
            raise Raised()


class Impl(Protocol, Generic[T]):
    def __call__(
        self,
        contexts: Sequence[GenCtxManager[T]],
        draw: st.DrawFn,
        yields: MutableSequence[list[T]],
        n_sends: int,
    ) -> None:
        ...


def run(
    draw: st.DrawFn, impl: Impl[T], n_contexts, n_sends: int
) -> tuple[Probe, list[list[T]]]:
    probe = Probe()
    contexts = [
        context(draw=draw, probe=probe, id=i, n_sends=n_sends)
        for i in range(n_contexts)
    ]
    yields = list[Any]()
    try:
        impl(contexts=contexts, draw=draw, yields=yields, n_sends=n_sends)
        probe()
    except (Raised, Thrown) as e:
        probe(e)

    return probe, yields


def dev(
    contexts: Sequence[GenCtxManager[T]],
    draw: st.DrawFn,
    yields: MutableSequence[list[T]],
    n_sends: int,
) -> None:
    entered = list[GenCtxManager]()
    try:
        ys = []
        for ctx in contexts:
            y = ctx.__enter__()
            entered.append(ctx)
            ys.append(y)
        yields.append(ys)

        active = list(reversed(contexts))

        if draw(st.booleans()):
            raise Raised()
        for i in range(n_sends, 0, -1):
            ys = []
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            match action:
                case 'send':
                    for ctx in list(active):
                        try:
                            y = ctx.gen.send(f'send({i})')
                            ys.append(y)
                        except StopIteration:
                            active.remove(ctx)
                case 'throw':
                    for ctx in list(active):
                        try:
                            ctx.gen.throw(Thrown())
                        except StopIteration:
                            active.remove(ctx)
                case 'close':
                    for ctx in list(active):
                        try:
                            ctx.gen.close()
                        except StopIteration:
                            active.remove(ctx)

            if not active:
                break

            yields.append(ys)

            if draw(st.booleans()):
                raise Raised()

    except Exception:
        exc_info = sys.exc_info()
        while entered:
            ctx = entered.pop()
            if ctx.__exit__(*exc_info):
                break
        else:
            raise
    finally:
        exc_info = (None, None, None)
        while entered:
            ctx = entered.pop()
            try:
                if ctx.__exit__(*exc_info):
                    exc_info = (None, None, None)
            except Exception:
                exc_info = sys.exc_info()

        if exc_info != (None, None, None):
            assert isinstance(exc_info[1], BaseException)
            raise exc_info[1].with_traceback(exc_info[2])


@given(st.data())
# @settings(max_examples=1000)
def test_context(data: st.DataObject):
    n_contexts = data.draw(st.integers(min_value=1, max_value=3), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    # n_sends = 1
    draw = RecordReturns(data.draw)

    ref_imp = nested_with

    # Run on a reference implementation.
    probe0, yields0 = run(
        draw=draw, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    # Verify the replay draw by running on the same implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    assert probe0.calls == probe1.calls
    assert yields0 == yields1

    if n_contexts <= 2:
        # Compare with manual enter/exit.
        replay = ReplayReturns(draw)
        probe1, yields1 = run(
            draw=replay, impl=call_enter, n_contexts=n_contexts, n_sends=n_sends
        )
        assert probe0.calls == probe1.calls
        assert yields0 == yields1

    if n_sends == 0:
        # Compare with ExitStack, which doesn't support send/throw/close.
        replay = ReplayReturns(draw)
        probe1, yields1 = run(
            draw=replay, impl=with_exit_stack, n_contexts=n_contexts, n_sends=n_sends
        )
        assert probe0.calls == probe1.calls
        assert yields0 == yields1

    # Test the target implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay,
        impl=enter_multiple_contexts,
        n_contexts=n_contexts,
        n_sends=n_sends,
    )
    assert probe0.calls == probe1.calls
    assert yields0 == yields1


@given(st.data())
# @settings(max_examples=1000)
def test_dev(data: st.DataObject):
    n_contexts = data.draw(st.integers(min_value=0, max_value=5), label='n_contexts')

    n_sends = data.draw(st.integers(min_value=0, max_value=5), label='n_sends')
    # n_sends = 1
    draw = RecordReturns(data.draw)

    ref_imp = enter_multiple_contexts

    # Run on a reference implementation.
    probe0, yields0 = run(
        draw=draw, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    # Verify the replay draw by running on the same implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay, impl=ref_imp, n_contexts=n_contexts, n_sends=n_sends
    )

    assert probe0.calls == probe1.calls
    assert yields0 == yields1

    # Test the target implementation.
    replay = ReplayReturns(draw)
    probe1, yields1 = run(
        draw=replay,
        impl=dev,
        n_contexts=n_contexts,
        n_sends=n_sends,
    )
    assert probe0.calls == probe1.calls
    assert yields0 == yields1
