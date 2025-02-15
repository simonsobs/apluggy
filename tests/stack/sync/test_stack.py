import sys
import traceback
from collections.abc import Sequence
from typing import Literal

from hypothesis import given, note, settings
from hypothesis import strategies as st

from apluggy import stack_gen_ctxs

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .context import CTX_ACTIONS, EXCEPT_ACTIONS, MockContext
from .exc import MockException
from .refs import Stack, dunder_enter, exit_stack, nested_with

ExitActionName: TypeAlias = Literal['exit', 'raise']
EXIT_ACTIONS: Sequence[ExitActionName] = ('exit', 'raise')


@settings(max_examples=2000)
@given(data=st.data())
def test_property(data: st.DataObject) -> None:
    MAX_N_CTXS = 5
    GEN_ENABLED = True
    # MAX_N_CTXS = 1
    # GEN_ENABLED = False

    MAX_N_SENDS = 4
    # MAX_N_SENDS = 0

    ENABLED_CTX_ACTIONS_ON_ENTER = CTX_ACTIONS
    ENABLED_EXCEPT_ACTIONS_ON_ENTER = EXCEPT_ACTIONS
    # ENABLED_CTX_ACTIONS_ON_ENTER = ('yield', 'exit',)
    # ENABLED_EXCEPT_ACTIONS_ON_ENTER = ('reraise',)

    ENABLED_CTX_ACTIONS_ON_SENT = CTX_ACTIONS
    ENABLED_EXCEPT_ACTIONS_ON_SENT = EXCEPT_ACTIONS

    ENABLED_EXIT_ACTIONS = EXIT_ACTIONS
    ENABLED_EXCEPT_ACTIONS_ON_RAISED = EXCEPT_ACTIONS
    # ENABLED_EXIT_ACTIONS = ('exit',)
    # ENABLED_EXCEPT_ACTIONS_ON_RAISED = ('reraise',)

    #
    n_ctxs = data.draw(st.integers(min_value=0, max_value=MAX_N_CTXS), label='n_ctxs')
    gen_enabled = data.draw(
        st.booleans() if GEN_ENABLED else st.just(False),
        label='gen_enabled',
    )
    n_sends = data.draw(
        st.integers(min_value=0, max_value=MAX_N_SENDS) if gen_enabled else st.just(0),
        label='n_sends',
    )

    def st_exit_action() -> st.SearchStrategy[ExitActionName]:
        return st.sampled_from(ENABLED_EXIT_ACTIONS)

    stack = data.draw(_st_stack(n_ctxs, gen_enabled), label='stack')

    mock_context = MockContext(
        data=data,
        enabled_ctx_actions_on_enter=ENABLED_CTX_ACTIONS_ON_ENTER,
        enabled_except_actions_on_enter=ENABLED_EXCEPT_ACTIONS_ON_ENTER,
        enabled_ctx_actions_on_sent=ENABLED_CTX_ACTIONS_ON_SENT,
        enabled_except_actions_on_sent=ENABLED_EXCEPT_ACTIONS_ON_SENT,
        enabled_except_actions_on_raised=ENABLED_EXCEPT_ACTIONS_ON_RAISED,
    )
    ctxs = [mock_context() for _ in range(n_ctxs)]

    mock_context.assert_created(iter(ctxs))  # `iter()` to test with an iterable.

    mock_context.before_enter()
    try:
        with (stacked := stack(iter(ctxs))) as y:
            mock_context.on_entered(yields=iter(y))

            #
            for i in range(n_sends):
                sent = f'sent-{i}'
                mock_context.before_send(sent)
                y = stacked.gen.send(sent)
                mock_context.on_sent(iter(y))

            #
            exit_action = data.draw(st_exit_action())
            if exit_action == 'raise':
                exc_raised = MockException('raised')
                mock_context.before_raise(exc_raised)
                raise exc_raised
            elif exit_action == 'exit':
                mock_context.before_exit()
            else:  # pragma: no cover
                raise ValueError(f'Unknown exit action: {exit_action!r}')
    except Exception as e:
        note(traceback.format_exc())
        mock_context.on_exited(exc=e)
    else:
        mock_context.on_exited()


def _st_stack(n_ctxs: int, gen_enabled: bool) -> st.SearchStrategy[Stack]:
    # `stack_gen_ctxs` is the object to be tested.
    # `dunder_enter`, `nested_with`, and `exit_stack` are reference implementations.
    stacks = [stack_gen_ctxs]
    if n_ctxs <= 4:
        stacks.extend([dunder_enter, nested_with])
    if not gen_enabled:
        stacks.append(exit_stack)
    return st.sampled_from(stacks)
