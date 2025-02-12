from pathlib import Path
from typing import Union

import pytest


def _all_module_names(base_dir: Union[str, Path], base_package: str) -> list[str]:
    '''Return the names of all Python modules under a directory as import paths.

    Parameters
    ----------
    base_dir
        Directory path to search from (e.g. 'tests')
    base_package
        Base package name (e.g. 'tests')

    Returns
    -------
        List of module paths (e.g. ['tests.stack.sync.context', ...])
    '''
    base_dir = Path(base_dir)

    absolute_paths = base_dir.rglob('*.py')
    absolute_paths = (p for p in absolute_paths if p.name != '__init__.py')
    absolute_paths = (p for p in absolute_paths if not p.name.startswith('test_'))

    relative_paths = (p.relative_to(base_dir) for p in absolute_paths)

    module_parts = ([*p.parent.parts, p.stem] for p in relative_paths)

    module_paths = (f"{base_package}.{'.'.join(parts)}" for parts in module_parts)
    return list(module_paths)


_HERE = Path(__file__).resolve().parent

_module_names = _all_module_names(_HERE, __package__)
pytest.register_assert_rewrite(*_module_names)
