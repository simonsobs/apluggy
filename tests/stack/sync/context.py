import sys
from collections.abc import Generator, Iterable, Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Literal, Union

from hypothesis import note
from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import ContextIdGenerator, CtxId
from .exc import ExceptionExpectation, GeneratorDidNotYield, MockException, wrap_exc
from .handle import ExceptionHandler, ExceptionHandlerNull, st_exception_handler

_ActionName = Literal['yield', 'raise', 'break']
_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['break'], None],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]
_ACTIONS: tuple[_ActionName, ...] = ('yield', 'raise', 'break')


class MockContext:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._generate_ctx_id = ContextIdGenerator()
        self._ctxs_map: dict[CtxId, GenCtxMngr] = {}
        self._created_ctx_ids: list[CtxId] = []
        self._entered_ctx_ids: list[CtxId] = []
        self._exiting_ctx_ids: list[CtxId] = []
        self._clear()

    def _clear(self) -> None:
        self._exc_handler: ExceptionHandler = ExceptionHandlerNull()
        self._action_map: Union[_ActionMap, None] = None
        self._exc_expected = ExceptionExpectation(None)
        self._sent_expected: list[str] = []
        self._sent_actual: list[str] = []
        self._yields_expected: list[str] = []
        self._to_be_exited = False
        self._exiting_ctx_ids_expected: list[CtxId] = []

    def __call__(self) -> GenCtxMngr[str]:
        id = self._generate_ctx_id()
        self._created_ctx_ids.append(id)

        @contextmanager
        def _ctx() -> Generator[str, str, None]:
            self._entered_ctx_ids.append(id)
            try:
                while True:
                    assert self._action_map is not None, f'{id=}'
                    action_item = self._action_map.pop(id, ('break', None))
                    note(f'ctx {id=} {action_item=}')
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'break':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                            self._sent_actual.append(sent)
                        except Exception as e:
                            note(f'ctx {id=} except: {e=}')
                            assert self._exc_handler is not None
                            self._exc_handler.handle(id, e)
                            break
                    else:  # pragma: no cover
                        raise ValueError(f'Unknown action: {action_item[0]!r}')
            finally:
                self._exiting_ctx_ids.append(id)

        ctx = _ctx()
        self._ctxs_map[id] = ctx
        return ctx

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == [self._ctxs_map[id] for id in self._created_ctx_ids]

    def before_enter(self) -> None:
        _name = f'{self.__class__.__name__}.{self.before_enter.__name__}'
        note(f'{_name}()')
        self._clear()

        if not self._created_ctx_ids:
            self._yields_expected = []
            return

        self._action_map = self._draw(
            _st_action_map(self._created_ctx_ids), label=f'{_name}: _action_map'
        )

        last_action_item = list(self._action_map.values())[-1]
        if last_action_item[0] == 'yield':
            # All actions are `yield` when the last action is `yield`.
            # `e[0] == 'yield'` is to reduce the type of `e[1]` to `str`.
            self._yields_expected = [
                e[1] for e in self._action_map.values() if e[0] == 'yield'
            ]
            note(f'{_name}: {self._yields_expected=}')
            return

        assert last_action_item[0] in {'raise', 'break'}
        self._to_be_exited = True
        self._exiting_ctx_ids_expected = list(reversed(list(self._action_map.keys())))
        note(f'{_name}: {self._exiting_ctx_ids_expected=}')

        exc = (
            last_action_item[1]
            if last_action_item[0] == 'raise'
            else GeneratorDidNotYield  # last_action_item[0] == 'break'
        )
        exp = wrap_exc(exc)

        suspended_ctx_ids = list(self._action_map.keys())[:-1]

        self._exc_handler = self._draw(
            st_exception_handler(exp=exp, ids=reversed(suspended_ctx_ids))
        )
        note(f'{_name}: {self._exc_handler=}')

        exp_on_handle = wrap_exc(GeneratorDidNotYield)
        self._exc_expected = self._exc_handler.expect_outermost_exc(
            exp_on_handle=exp_on_handle
        )
        note(f'{_name}: {self._exc_expected=}')

    def on_entered(self, yields: Iterable[str]) -> None:
        yields = list(yields)
        _name = f'{self.__class__.__name__}.{self.on_entered.__name__}'
        note(f'{_name}({yields=!r})')
        assert not self._to_be_exited
        assert self._entered_ctx_ids == self._created_ctx_ids
        assert not self._action_map
        assert yields == self._yields_expected

    def before_send(self, sent: str) -> None:
        _name = f'{self.__class__.__name__}.{self.before_send.__name__}'
        note(f'{_name}({sent=})')
        self._clear()

        if not self._created_ctx_ids:
            self._to_be_exited = True
            self._exc_handler = ExceptionHandlerNull()
            self._exc_expected = wrap_exc(StopIteration())
            self._exiting_ctx_ids_expected = []
            return

        self._action_map = self._draw(
            _st_action_map(reversed(self._created_ctx_ids)),
            label=f'{_name}: _action_map',
        )
        id, last_action_item = list(self._action_map.items())[-1]
        if last_action_item[0] == 'yield':
            self._sent_expected = [sent] * len(self._created_ctx_ids)
            # All actions are `yield` when the last action is `yield`.
            # `e[0] == 'yield'` is to reduce the type of `e[1]` to `str`.
            self._yields_expected = [
                e[1] for e in self._action_map.values() if e[0] == 'yield'
            ]
            note(f'{_name}: {self._yields_expected=}')
            return

        assert last_action_item[0] in {'raise', 'break'}
        self._to_be_exited = True
        suspended_ctx_ids = [i for i in self._created_ctx_ids if i != id]
        self._exiting_ctx_ids_expected = [id, *list(reversed(suspended_ctx_ids))]

        if last_action_item[0] == 'break':
            self._exc_handler = ExceptionHandlerNull()
            self._exc_expected = wrap_exc(StopIteration())
        elif last_action_item[0] == 'raise':
            if not suspended_ctx_ids:
                self._exc_handler = ExceptionHandlerNull()
                self._exc_expected = wrap_exc(last_action_item[1])
            else:
                exp = wrap_exc(last_action_item[1])
                self._exc_handler = self._draw(
                    st_exception_handler(exp=exp, ids=reversed(suspended_ctx_ids))
                )
                self._exc_expected = self._exc_handler.expect_outermost_exc(
                    exp_on_handle=wrap_exc(StopIteration())
                )
        else:  # pragma: no cover
            raise ValueError(f'Unknown action: {last_action_item[0]!r}')
        note(f'{_name}: {self._exc_handler=}')
        note(f'{_name}: {self._exc_expected=}')

    def on_sent(self, yields: Iterable[str]) -> None:
        yields = list(yields)
        _name = f'{self.__class__.__name__}.{self.on_sent.__name__}'
        note(f'{_name}({yields=!r})')
        assert not self._to_be_exited
        assert not self._action_map
        assert self._sent_actual == self._sent_expected
        assert yields == self._yields_expected

    def before_raise(self, exc: Exception) -> None:
        _name = f'{self.__class__.__name__}.{self.before_raise.__name__}'
        note(f'{_name}({exc=!r})')
        self._clear()
        self._to_be_exited = True
        exp = wrap_exc(exc)
        self._action_map = {}
        self._exc_handler = self._draw(
            st_exception_handler(exp=exp, ids=reversed(self._entered_ctx_ids))
        )

        note(f'{_name}: {self._action_map=}')
        note(f'{_name}: {self._exc_handler._action_map=}')
        self._exc_expected = self._exc_handler.expect_outermost_exc()
        note(f'{_name}: {self._exc_expected=}')

        self._exiting_ctx_ids_expected = list(reversed(self._created_ctx_ids))

    def before_exit(self) -> None:
        _name = f'{self.__class__.__name__}.{self.before_exit.__name__}'
        note(f'{_name}()')
        self._clear()
        self._action_map = {id: ('break', None) for id in self._created_ctx_ids}
        self._to_be_exited = True
        self._exiting_ctx_ids_expected = list(reversed(self._created_ctx_ids))

    def on_exited(self, exc: Union[BaseException, None]) -> None:
        _name = f'{self.__class__.__name__}.{self.on_exited.__name__}'
        assert self._to_be_exited
        note(f'{_name}({exc=!r})')
        assert self._exiting_ctx_ids == self._exiting_ctx_ids_expected, (
            f'{self._exiting_ctx_ids=}',
            f'{self._exiting_ctx_ids_expected=}',
        )
        assert not self._action_map, f'{self._action_map=}'
        self._exc_handler.assert_on_exited(exc)
        assert self._exc_expected == exc


@st.composite
def _st_action_map(draw: st.DrawFn, ids: Iterable[CtxId]) -> _ActionMap:
    ids = list(ids)
    st_actions = st.sampled_from(_ACTIONS)
    actions: list[_ActionName] = draw(
        st_list_until(st_actions, last={'raise', 'break'}, max_size=len(ids))
    )

    def _action_item(id: CtxId, action: _ActionName) -> _ActionItem:
        if action == 'raise':
            return ('raise', MockException(f'{id}'))
        if action == 'yield':
            return ('yield', f'{id}')
        if action == 'break':
            return ('break', None)
        raise ValueError(f'Unknown action: {action!r}')  # pragma: no cover

    return {id: _action_item(id, a) for id, a in zip(ids, actions)}
