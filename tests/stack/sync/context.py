import sys
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable, MutableMapping, Sequence
from contextlib import contextmanager
from typing import Literal, Optional, Union

from hypothesis import note
from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import CtxId
from .exc import MockException, wrap_exc
from .except_ import EXCEPT_ACTIONS, ExceptActionName
from .exit_ import ExitHandler
from .states import Created, Entered, Sent, SentNull

CtxActionName = Literal['yield', 'raise', 'exit']
CTX_ACTIONS: Sequence[CtxActionName] = ('yield', 'raise', 'exit')


_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['exit'], None],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]


class ActionMap(ABC):
    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def pop(self, ctx_id: CtxId) -> _ActionItem:
        pass


class ActionMapNull(ActionMap):
    def __init__(self) -> None:
        pass

    def __len__(self) -> int:
        return 0

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        assert False


class ActionMapExit(ActionMap):
    def __init__(self) -> None:
        pass

    def __len__(self) -> int:
        return 0

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        return ('exit', None)


@st.composite
def st_action_map(
    draw: st.DrawFn, ids: Iterable[CtxId], enabled_actions: Sequence[CtxActionName]
) -> 'ActionMapDraw':
    action_map = draw(_st_ctx_action_map(ids, enabled_actions))
    return ActionMapDraw(action_map)


class ActionMapDraw(ActionMap):
    def __init__(self, action_map: _ActionMap) -> None:
        self._map = action_map

    def __len__(self) -> int:
        return len(self._map)

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        return self._map.pop(ctx_id, ('exit', None))

    @property
    def last_ctx_id(self) -> CtxId:
        return list(self._map.keys())[-1]

    @property
    def last_action_item(self) -> _ActionItem:
        return list(self._map.values())[-1]

    @property
    def yields(self) -> tuple[str, ...]:
        return tuple(e[1] for e in self._map.values() if e[0] == 'yield')

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._map.keys())


class MockContext:
    def __init__(
        self,
        data: st.DataObject,
        enabled_ctx_actions_on_enter: Sequence[CtxActionName] = CTX_ACTIONS,
        enabled_except_actions_on_enter: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
        enabled_ctx_actions_on_sent: Sequence[CtxActionName] = CTX_ACTIONS,
        enabled_except_actions_on_sent: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
        enabled_except_actions_on_raised: Sequence[ExceptActionName] = EXCEPT_ACTIONS,
    ) -> None:
        self._data = data
        self._draw = data.draw
        self._enabled_ctx_actions_on_enter = enabled_ctx_actions_on_enter
        self._enabled_except_actions_on_enter = enabled_except_actions_on_enter
        self._enabled_ctx_actions_on_sent = enabled_ctx_actions_on_sent
        self._enabled_except_actions_on_sent = enabled_except_actions_on_sent
        self._enabled_except_actions_on_raised = enabled_except_actions_on_raised

        self._created = Created()
        self._clear()

    def _clear(self) -> None:
        self._action_map: ActionMap = ActionMapNull()
        self._sent: Sent = SentNull()
        self._exit_handler = ExitHandler(
            self._data,
            enabled_except_actions_on_enter=self._enabled_except_actions_on_enter,
            enabled_except_actions_on_sent=self._enabled_except_actions_on_sent,
            enabled_except_actions_on_raised=self._enabled_except_actions_on_raised,
        )

    def __call__(self) -> GenCtxMngr[str]:
        @contextmanager
        def _ctx() -> Generator[str, str, None]:
            self._entered.add(ctx_id)
            try:
                while True:
                    action_item = self._action_map.pop(ctx_id)
                    note(f'{ctx_id=} {action_item=}')
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'exit':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                            self._sent.add(sent)
                        except Exception as e:
                            note(f'{ctx_id=} except: {e=}')
                            self._exit_handler.on_error(ctx_id, e)
                            break
                    else:  # pragma: no cover
                        raise ValueError(f'Unknown action: {action_item[0]!r}')
            finally:
                self._exit_handler.on_exiting(ctx_id)

        ctx = _ctx()
        ctx_id = self._created.add(ctx)
        return ctx

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        self._created.assert_on_created(ctxs)

    def before_enter(self) -> None:
        self._clear()

        if not self._created.ctx_ids:
            self._entered = Entered()
            return

        self._action_map = self._draw(
            st_action_map(
                self._created.ctx_ids,
                enabled_actions=self._enabled_ctx_actions_on_enter,
            )
        )

        last_action_item = self._action_map.last_action_item
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            yields_expected = self._action_map.yields
            self._entered = Entered(
                ctx_ids_expected=self._created.ctx_ids,
                yields_expected=yields_expected,
            )
            return

        entered_ctx_ids = self._action_map.ctx_ids
        if last_action_item[0] == 'exit':
            self._entered = Entered()
            self._exit_handler.expect_exit_on_enter(entered_ctx_ids)
            return

        if last_action_item[0] == 'raise':
            self._entered = Entered()
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_enter(entered_ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')

    def on_entered(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_entered()
        assert not self._action_map
        self._entered.assert_on_entered(yields)

    def before_send(self, sent: str) -> None:
        self._clear()

        if not self._created.ctx_ids:
            self._exit_handler.expect_send_without_ctx()
            return

        self._action_map = self._draw(
            st_action_map(
                reversed(self._created.ctx_ids),
                enabled_actions=self._enabled_ctx_actions_on_sent,
            )
        )
        id = self._action_map.last_ctx_id
        last_action_item = self._action_map.last_action_item
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            yields_expected = self._action_map.yields
            self._sent = Sent(sent_expected=sent, yields_expected=yields_expected)
            return

        if last_action_item[0] == 'exit':
            self._exit_handler.expect_exit_on_sent(id, self._entered.ctx_ids)
            return

        if last_action_item[0] == 'raise':
            exp_exc = wrap_exc(last_action_item[1])
            self._exit_handler.expect_raise_on_sent(id, self._entered.ctx_ids, exp_exc)
            return

        raise ValueError(f'Unknown action: {last_action_item[0]!r}')  # pragma: no cover

    def on_sent(self, yields: Iterable[str]) -> None:
        self._exit_handler.assert_on_sent()
        assert not self._action_map
        self._sent.assert_on_sent(yields)

    def before_raise(self, exc: Exception) -> None:
        self._clear()
        self._action_map = ActionMapExit()
        entered_ctx_ids = self._entered.ctx_ids
        exp_exc = wrap_exc(exc)
        self._exit_handler.expect_raise_in_with_block(entered_ctx_ids, exp_exc)

    def before_exit(self) -> None:
        self._clear()
        self._action_map = ActionMapExit()
        self._exit_handler.expect_to_exit(reversed(self._created.ctx_ids))

    def on_exited(self, exc: Optional[BaseException] = None) -> None:
        assert not self._action_map
        self._exit_handler.assert_on_exited(exc)


@st.composite
def _st_ctx_action_map(
    draw: st.DrawFn, ids: Iterable[CtxId], enabled_actions: Sequence[CtxActionName]
) -> _ActionMap:
    ids = list(ids)
    st_actions = st.sampled_from(enabled_actions)
    actions: list[CtxActionName] = draw(
        st_list_until(st_actions, last={'raise', 'exit'}, max_size=len(ids))
    )

    def _action_item(id: CtxId, action: CtxActionName) -> _ActionItem:
        if action == 'raise':
            return ('raise', MockException(f'{id}'))
        if action == 'yield':
            return ('yield', f'yield-{id}')
        if action == 'exit':
            return ('exit', None)
        raise ValueError(f'Unknown action: {action!r}')  # pragma: no cover

    return {id: _action_item(id, a) for id, a in zip(ids, actions)}
