import contextlib
from collections.abc import Generator, MutableSequence
from typing import Any, TypeVar

from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from apluggy.test import Probe, st_none_or

from .exc import Raised, Thrown
from .refs import Stack

T = TypeVar('T')


def run(
    draw: st.DrawFn, stack: Stack[T], n_contexts, n_sends: int
) -> tuple[Probe, list[list[T]]]:
    probe = Probe()
    contexts = [
        mock_context(draw=draw, probe=probe, id=f'ctx{i}', n_sends=n_sends)
        for i in range(n_contexts)
    ]
    ctx = stack(iter(contexts))
    yields = list[Any]()
    try:
        run_generator_context(
            ctx=ctx, draw=draw, probe=probe, yields=yields, n_sends=n_sends
        )
        probe()
    except (Raised, Thrown) as e:
        probe(e)
    except RuntimeError as e:
        # generator didn't stop
        probe(e)
    except KeyboardInterrupt as e:
        probe(e)
    else:
        probe()
    finally:
        # Ensure to close all contexts, otherwise the test will fail because
        # they might be closed at the garbage collection and probe() will be
        # unpredictable.
        for c in reversed(contexts):
            c.gen.close()
        probe()

    return probe, yields


@contextlib.contextmanager
def mock_context(
    draw: st.DrawFn, probe: Probe, id: str, n_sends: int
) -> Generator[Any, Any, Any]:
    probe(id, 'init', f'n_sends={n_sends}')

    if draw(st.booleans()):
        exc = Raised(f'{id}-init')
        probe(id, 'raise', f'{exc!r}')
        raise exc
    probe(id)

    try:
        y = f'{id}-enter'
        probe(id, 'enter', f'{y!r}')
        sent = yield y
        probe(id, 'received', f'{sent!r}')

        for i in range(n_sends):
            ii = f'{i+1}/{n_sends}'

            action = draw(st.one_of(st.none(), st.sampled_from(['raise', 'break'])))
            if action == 'raise':
                exc = Raised(f'{id}-{ii}')
                probe(id, ii, 'raise', f'{exc!r}')
                raise exc
            elif action == 'break':
                probe(id, ii, 'break')
                break

            y = f'{id}-yield-{ii}'
            probe(id, ii, 'yield', f'{y!r}')
            sent = yield y
            probe(id, ii, 'received', f'{sent!r}')

    except GeneratorExit as e:  # close() was called or garbage collected
        # This can happen after the test has finished unless close() is called
        # in the test.
        probe(id, 'caught', e)
        raise
    except BaseException as e:  # throw() was called or exception raised
        # throws() might be called by __exit__(). If so, an exception must be
        # raised here, otherwise __exit__() will raise
        # RuntimeError("generator didn't stop after throw()")
        probe(id, 'caught', e)
        # action = draw(st.one_of(st.none(), st.sampled_from(['reraise', 'raise'])))
        action = draw(st.sampled_from(['reraise', 'raise']))
        if action == 'reraise':
            probe(id, 'reraise')
            raise
        elif action == 'raise':
            exc = Raised(f'{id}-except')
            probe(id, 'raise', f'{exc!r}')
            raise exc
    finally:
        probe(id, 'finally')


def run_generator_context(
    ctx: GenCtxMngr[T],
    draw: st.DrawFn,
    probe: Probe,
    yields: MutableSequence[T],
    n_sends: int,
) -> None:
    probe('entering')
    with ctx as y:
        probe('entered')
        yields.append(y)
        st_exceptions = st.sampled_from([Raised('entering'), KeyboardInterrupt()])
        exc = draw(st_none_or(st_exceptions))
        if exc is not None:
            probe('with', 'raise', f'{exc!r}')
            raise exc
        for i in range(n_sends):
            ii = f'{i+1}/{n_sends}'
            action = draw(st.sampled_from(['send', 'throw', 'close']))
            try:
                match action:
                    case 'send':
                        sent = f'send-{ii}'
                        probe('with', ii, 'send', f'{sent!r}')
                        y = ctx.gen.send(sent)
                        yields.append(y)
                    case 'throw':
                        exc = Thrown(f'{ii}')
                        probe('with', ii, 'throw', f'{exc!r}')
                        ctx.gen.throw(exc)
                    case 'close':
                        probe('with', ii, 'close')
                        ctx.gen.close()
            except GeneratorExit:
                raise
            except StopIteration as e:
                probe('with', ii, 'caught', e)
                break
            except BaseException as e:
                probe('with', ii, 'caught', e)
                raise
            st_exceptions = st.sampled_from([Raised(f'with-{ii}'), KeyboardInterrupt()])
            exc = draw(st_none_or(st_exceptions))
            if exc is not None:
                probe('with', {ii}, 'raise', f'{exc!r}')
                raise exc
        probe('exiting')
    probe('exited')
