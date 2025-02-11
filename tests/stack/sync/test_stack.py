import sys
import traceback
from collections.abc import Sequence
from typing import Literal, Union

from hypothesis import given, note, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .context import CTX_ACTIONS, EXCEPT_ACTIONS, MockContext, MockException
from .refs import Stack, dunder_enter, exit_stack, nested_with


@settings(max_examples=2000)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    MAX_N_CTXS = 5
    GEN_ENABLED = True

    MAX_N_SENDS = 4

    ENABLED_CTX_ACTIONS_ON_ENTER = CTX_ACTIONS
    ENABLED_EXCEPT_ACTIONS_ON_ENTER = EXCEPT_ACTIONS

    ENABLED_CTX_ACTIONS_ON_SENT = CTX_ACTIONS
    ENABLED_EXCEPT_ACTIONS_ON_SENT = EXCEPT_ACTIONS

    ENABLED_EXCEPT_ACTIONS_ON_RAISED = EXCEPT_ACTIONS

    n_ctxs = data.draw(st.integers(min_value=0, max_value=MAX_N_CTXS), label='n_ctxs')
    gen_enabled = data.draw(
        st.booleans() if GEN_ENABLED else st.just(False), label='gen_enabled'
    )

    ActionName: TypeAlias = Literal['send', 'raise', 'break']
    ACTIONS: Sequence[ActionName] = ('send', 'raise', 'break')
    if not gen_enabled:
        ACTIONS = tuple(a for a in ACTIONS if a != 'send')

    def st_action() -> st.SearchStrategy[ActionName]:
        return st.sampled_from(ACTIONS)

    stack = data.draw(_st_stack(n_ctxs, gen_enabled), label='stack')

    mock_context = MockContext(data=data)
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created(iter(ctxs))  # `iter()` to test with an iterable.

    mock_context.before_enter(
        enabled_actions=ENABLED_CTX_ACTIONS_ON_ENTER,
        enabled_except_actions=ENABLED_EXCEPT_ACTIONS_ON_ENTER,
    )
    exc: Union[Exception, None] = None
    try:
        with (stacked := stack(iter(ctxs))) as y:
            mock_context.on_entered(yields=iter(y))
            for i in range(MAX_N_SENDS):
                action = data.draw(st_action())
                if action == 'send':
                    sent = f'sent-{i}'
                    mock_context.before_send(
                        sent,
                        enabled_actions=ENABLED_CTX_ACTIONS_ON_SENT,
                        enabled_except_actions=ENABLED_EXCEPT_ACTIONS_ON_SENT,
                    )
                    y = stacked.gen.send(sent)
                    mock_context.on_sent(iter(y))
                elif action == 'raise':
                    exc0 = MockException('0')
                    mock_context.before_raise(
                        exc0, enabled_except_actions=ENABLED_EXCEPT_ACTIONS_ON_RAISED
                    )
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
