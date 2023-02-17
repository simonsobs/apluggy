# apluggy

[![PyPI - Version](https://img.shields.io/pypi/v/apluggy.svg)](https://pypi.org/project/apluggy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/apluggy.svg)](https://pypi.org/project/apluggy)
[![Test Status](https://github.com/simonsobs/apluggy/actions/workflows/unit-test.yml/badge.svg)](https://github.com/simonsobs/apluggy/actions/workflows/unit-test.yml)
[![Test Status](https://github.com/simonsobs/apluggy/actions/workflows/type-check.yml/badge.svg)](https://github.com/simonsobs/apluggy/actions/workflows/type-check.yml)
[![codecov](https://codecov.io/gh/simonsobs/apluggy/branch/main/graph/badge.svg)](https://codecov.io/gh/simonsobs/apluggy)

A wrapper of [pluggy](https://pluggy.readthedocs.io/) to support asyncio and context managers.

This package provides a subclass of
[`pluggy.PluginManager`](https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluginManager)
that

- allows async functions, context managers, and async context managers to be hooks
- and accepts plugin factories in addition to plugin instances for registration.

The package also provides `asynccontextmanager` decorator, which is a wrapper
of
[`contextlib.asynccontextmanager`](https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager)
to preserve the signature of the decorated function. This decorator is
implemented in the same way as
[`contextmanager`](https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager)
from the [decorator package](https://pypi.org/project/decorator/) is
implemented.

---

**Table of Contents**

- [apluggy](#apluggy)
  - [Installation](#installation)
  - [How to use](#how-to-use)
    - [Import packages](#import-packages)
    - [Create hook specification and implementation decorators](#create-hook-specification-and-implementation-decorators)
    - [Define hook specifications](#define-hook-specifications)
    - [Define plugins](#define-plugins)
    - [Create a plugin manager and register plugins](#create-a-plugin-manager-and-register-plugins)
    - [Call hooks](#call-hooks)
  - [Links](#links)
  - [License](#license)
  - [Contact](#contact)

## Installation

```console
pip install apluggy
```

## How to use

### Import packages

```python
>>> import asyncio
>>> import apluggy as pluggy
>>> from apluggy import asynccontextmanager, contextmanager

```

(`contextmanager` is imported from the [decorator package](https://pypi.org/project/decorator/).)

### Create hook specification and implementation decorators

```python
>>> hookspec = pluggy.HookspecMarker('project')
>>> hookimpl = pluggy.HookimplMarker('project')

```

(These makers are imported from the [pluggy package](https://pypi.org/project/pluggy/).)

### Define hook specifications

In this example, we define three hooks: async function, context manager, and
async context manager.

```python
>>> class Spec:
...     """A hook specification namespace."""
...
...     @hookspec
...     async def afunc(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @contextmanager
...     def context(self, arg1, arg2):
...         pass
...
...     @hookspec
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         pass

```

### Define plugins

We define two plugins as classes. Each plugin implements the three hooks
defined above.

```python
>>> class Plugin_1:
...     """A hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_1.afunc()')
...         return arg1 + arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_1.context()')
...         yield arg1 + arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_1.acontext()')
...         yield arg1 + arg2

>>> class Plugin_2:
...     """A 2nd hook implementation namespace."""
...
...     @hookimpl
...     async def afunc(self, arg1, arg2):
...         print('inside Plugin_2.afunc()')
...         return arg1 - arg2
...
...     @hookimpl
...     @contextmanager
...     def context(self, arg1, arg2):
...         print('inside Plugin_2.context()')
...         yield arg1 - arg2
...
...     @hookimpl
...     @asynccontextmanager
...     async def acontext(self, arg1, arg2):
...         print('inside Plugin_2.acontext()')
...         yield arg1 - arg2

```

### Create a plugin manager and register plugins

Plugins can be registered as instances or factories. In the following
example, we register two plugins: `Plugin_1` as an instance, and `Plugin_2`
as a factory.

```python
>>> pm = pluggy.PluginManager('project')
>>> pm.add_hookspecs(Spec)
>>> _ = pm.register(Plugin_1())  # instantiation is optional.
>>> _ = pm.register(Plugin_2)  # callable is considered a plugin factory.

```

### Call hooks

The following example shows how to call hooks.

```python
>>> async def call_afunc():
...     results = await pm.ahook.afunc(arg1=1, arg2=2)  # ahook instead of hook
...     print(results)

>>> asyncio.run(call_afunc())
inside Plugin_2.afunc()
inside Plugin_1.afunc()
[-1, 3]

```

```python
>>> with pm.with_.context(arg1=1, arg2=2) as y:  # with_ instead of hook
...     print(y)
inside Plugin_2.context()
inside Plugin_1.context()
[-1, 3]

```

```python
>>> async def call_acontext():
...     async with pm.awith.acontext(arg1=1, arg2=2) as y:  # awith instead of hook
...         print(y)

>>> asyncio.run(call_acontext())
inside Plugin_2.acontext()
inside Plugin_1.acontext()
[-1, 3]

```

## Links

- [pluggy](https://pluggy.readthedocs.io/)
- [decorator](https://pypi.org/project/decorator/)

## License

- _apluggy_ is licensed under the [MIT](https://spdx.org/licenses/MIT.html) license.

## Contact

- [Tai Sakuma](https://github.com/TaiSakuma) <span itemscope
  itemtype="https://schema.org/Person"><a itemprop="sameAs"
  content="https://orcid.org/0000-0003-3225-9861"
  href="https://orcid.org/0000-0003-3225-9861" target="orcid.widget" rel="me
  noopener noreferrer" style="vertical-align:text-top;"><img
  src="https://orcid.org/sites/default/files/images/orcid_16x16.png"
  style="width:1em;margin-right:.5em;" alt="ORCID iD icon"></a></span>
