"""modularprocessing — core data abstractions for modular file processing.

Exports the three primary building blocks of the library:

* :class:`FileLike` — wraps a single file with structured name parsing.
* :class:`LoaderLike` — discovers and bundles files from a directory.
* :class:`ProcessLike` — orchestrates processing over a dataset.

Typical usage::

    from modularprocessing import FileLike, LoaderLike

    loader = LoaderLike("/path/to/data")
    for item in loader.items:
        data = item.load()
"""

from .modularprocessing import FileLike, LoaderLike, ProcessLike

__all__ = [
    "FileLike",
    "LoaderLike",
    "ProcessLike",
]
