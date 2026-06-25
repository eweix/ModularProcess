"""Core data abstractions for modular file processing.

Provides base classes for representing, loading, and writing data files
with structured naming conventions. The module defines type aliases and
abstract interfaces that concrete implementations specialise.
"""

import datetime
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, MutableSequence
from os.path import basename, dirname, join, splitext
from typing import Union

Date = Union[str, datetime.date, datetime.datetime]


class FileLike(dict):
    """Wrapping around a file that parses structured metadata from its name.

    ``FileLike`` extracts metadata fields (name, ID, sample, date) from a file and
    exposes a canonical structured filename. Subclasses must implement
    :meth:`_parse_path` and :meth:`load`.

    Keys:
        name: Custom name for the file or sample. Defaults to the same value as stem.
        sample_id: Sample identification number or key.
        path: Absolute or relative path to the file.
        parent: Parent directory of the file.
        stem: Basename of the file.
    """

    def __init__(self, path: str, *args, **kwargs):
        # instantiate dictionary on self
        super().__init__(*args, **kwargs)
        self["path"] = path
        self["parent"] = dirname(path)
        self["stem"], self["ext"] = splitext(basename(path))
        name = kwargs.get("name", None)
        if name is None:
            self["name"] = self["stem"]
        else:
            self["name"] = name
        sample_id = kwargs.get("sample_id", None)
        self["sample_id"] = sample_id
        date = kwargs.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))
        if isinstance(date, datetime.datetime) or isinstance(date, datetime.date):
            date = date.strftime("%Y-%m-%d")
        self["date"] = date

    @property
    def path(self):
        return self["path"]

    @property
    def stem(self):
        return self["stem"]

    @property
    def parent(self):
        return self["parent"]

    @abstractmethod
    def load(self):
        """Load data from the file."""
        raise NotImplementedError

    # @abstractmethod
    # def _parse_path(self):
    #     raise NotImplementedError


class LoaderLike(ABC, MutableSequence):
    """Discovers files under a root directory and wraps them in ``FileLike`` objects.

    Subclasses should override :meth:`_gather` to filter relevant files and
    :meth:`_construct` to return a specialised ``FileLike`` subclass.

    Attributes:
        root: Root directory to scan for files.
        items: List of :class:`FileLike` instances found during gathering.
    """

    def __init__(self, data=None, isdir=False, **kwargs):
        """Scan *root* and build a ``FileLike`` for each discovered file.

        Args:
            root: Directory to scan.
            **metadata: Default metadata overrides passed to every
                :class:`FileLike` constructed. See :class:`MetadataOverride`.
        """
        if not data:
            self.items = list()
        elif isdir:
            self.items = [self._construct(f, **kwargs) for f in self._gather(data)]
        elif isinstance(data, Iterable):
            self.items = [self._construct(f, **kwargs) for f in data]

    def __iter__(self):
        """Return an iterator for the data"""
        return iter(self.items)

    def __getitem__(self, key):
        """Get a value from a key."""
        return self.items[key]

    def __setitem__(self, key, value):
        """Set a value at a key."""
        self.items[key] = value

    def __delitem__(self, key):
        """Delete a value at a key."""
        del self.items[key]

    def __len__(self):
        """Get number of items."""
        return len(self.items)

    def insert(self, key, value):
        """Insert an item at a key."""
        self.items.insert(key, value)

    def extend(self, iterable, **kwargs):
        """Extend contents by an iterable."""
        super().extend([self._construct(f, **kwargs) for f in iterable])

    def _gather(self, root) -> Iterable:
        """Return a list of full file paths under :arg:`root` to load.

        Override in subclasses to filter by filename pattern.  Subclass
        implementations **must** return full paths (joined with :arg:`root`)
        so that :meth:`_construct` receives a usable path.
        """
        return [join(root, f) for f in os.listdir(root)]

    @abstractmethod
    def _construct(self, f, **kwargs):
        """Build a ``FileLike`` (or subclass) for the given path.

        Override in subclasses to return a specialised ``FileLike``.
        """
        raise NotImplementedError


class ProcessLike(ABC):
    """Orchestrates processing of a :class:`LoaderLike` or :class:`FileLike`.

    Attributes:
        output_path: Optional directory path for writing results.
        inputs: A :class:`LoaderLike` or a list of :class:`FileLike`.
    """

    def __init__(
        self,
        data: Union[LoaderLike, FileLike, Iterable[FileLike]],
        output_path: Union[str, None] = None,
    ):
        """Initialise the processor with a dataset.

        Args:
            dataset: A :class:`LoaderLike` bundle or an individual
                :class:`FileLike` to process.
            output_path: Optional output directory for results.
        """
        self.output_path = output_path
        if isinstance(data, LoaderLike) or (
            isinstance(data, list) and all(isinstance(i, FileLike) for i in data)
        ):
            self._inputs = data
        else:
            self._inputs = [data]
        self._outputs = None  # prevents parsing errors, but fails silently if called

    @property
    def inputs(self):
        return self._inputs

    @property
    def outputs(self):
        return self._outputs

    @abstractmethod
    def run(self):
        """Execute the processing pipeline. MUST update self.outputs."""
        raise NotImplementedError
