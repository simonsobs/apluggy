from collections.abc import Callable, Iterable, Iterator
from typing import TypeVar

T = TypeVar('T')


def take_until(condition: Callable[[T], bool], iterable: Iterable[T]) -> Iterator[T]:
    '''Iterate until after yielding the first element that satisfies the condition.'''
    for x in iterable:
        yield x
        if condition(x):
            break
