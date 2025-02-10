import sys
import traceback
from itertools import count
from typing import Literal, Union

from hypothesis import given, note, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .context import MockContext
from .exc import MockException
from .refs import Stack, dunder_enter, exit_stack, nested_with


@settings(max_examples=500)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    n_ctxs = data.draw(st.integers(min_value=0, max_value=6), label='n_ctxs')
    gen_enabled = data.draw(st.booleans(), label='gen_enabled')

    ActionName: TypeAlias = Literal['send', 'raise', 'break']
    ACTIONS: tuple[ActionName, ...] = (
        ('send', 'raise', 'break') if gen_enabled else ('raise', 'break')
    )

    def st_action() -> st.SearchStrategy[ActionName]:
        return st.sampled_from(ACTIONS)

    stack = data.draw(_st_stack(n_ctxs, gen_enabled), label='stack')

    mock_context = MockContext(data=data)
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created(iter(ctxs))  # `iter()` to test with an iterable.

    mock_context.before_enter()
    exc: Union[Exception, None] = None
    try:
        with (stacked := stack(iter(ctxs))) as y:
            mock_context.on_entered(yields=iter(y))
            for i in count():
                action = data.draw(st_action())
                if action == 'send':
                    sent = f'sent-{i}'
                    mock_context.before_send(sent)
                    y = stacked.gen.send(sent)
                    mock_context.on_sent(iter(y))
                elif action == 'raise':
                    exc0 = MockException('0')
                    mock_context.before_raise(exc0)
                    raise exc0
                elif action == 'break':
                    break
                else:  # pragma: no cover
                    raise ValueError(f'Unknown action: {action!r}')
            mock_context.before_exit()
    except Exception as e:
        note(traceback.format_exc())
        exc = e
    mock_context.on_exited(exc=exc)


def _st_stack(n_ctxs: int, gen_enabled: bool) -> st.SearchStrategy[Stack]:
    # `stack_gen_ctxs` is the object to be tested.
    # `dunder_enter`, `nested_with`, and `exit_stack` are reference implementations.
    stacks = [stack_gen_ctxs]
    if n_ctxs <= 4:
        stacks.extend([dunder_enter, nested_with])
    if not gen_enabled:
        stacks.append(exit_stack)
    return st.sampled_from(stacks)
