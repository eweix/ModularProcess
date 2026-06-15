"""Core data abstractions for modular file processing.

Provides base classes for representing, loading, and writing data files
with structured naming conventions. The module defines type aliases and
abstract interfaces that concrete implementations specialise.
"""

import datetime
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable, MutableSequence
from os.path import join
from typing import Union

from typing_extensions import TypedDict, Unpack

Date = Union[str, datetime.date, datetime.datetime]


class MetadataDict(TypedDict, total=False):
    """Dictionary holding optional metadata overrides.

    ``total=False`` means that not all fields are required.

    Attributes:
        name: Experiment or sequence name.
        expID: Experiment identifier.
        sample: Sample identifier.
        date: Date string in ``YYYY-MM-DD`` format.
    """

    name: Union[str, None]
    expID: Union[str, None]
    sample: Union[str, None]
    date: Union[str, None]


class FileLike(ABC):
    """Wrapper around a file that parses structured metadata from its name.

    ``FileLike`` extracts metadata fields (name, experiment ID, sample, date)
    from a file path and exposes a canonical structured filename. Subclasses
    must implement :meth:`_parse_path` and :meth:`load`.

    Attributes:
        path: Absolute or relative path to the file.
        parent: Parent directory of the file.
        stem: Basename of the file.
        canonical: Canonical structured filename built from metadata.
    """

    def __init__(self, path: str, **metadata: Unpack[MetadataDict]):
        """Initialise the wrapper and parse metadata from the file path.

        Args:
            path: Path to the file on disk.
            **metadata: Optional overrides for ``name``, ``expID``, ``sample``,
                ``date``.  If provided these take precedence over values parsed
                from the filename.  ``date`` accepts a ``YYYY-MM-DD`` string,
                a :class:`datetime.date`, a :class:`datetime.datetime`, or
                ``None`` (defaults to today).
        """
        self._path = path
        self._parent = os.path.dirname(path)
        self._stem = os.path.basename(path)
        self._canonical = self._get_canonical_name(**metadata)

    def _get_canonical_name(self, **metadata: Unpack[MetadataDict]) -> str:
        m = self._parse_path()

        try:
            if metadata["name"] is not None:
                m["name"] = metadata["name"]
        except KeyError:
            pass
        try:
            if metadata["expID"] is not None:
                m["expID"] = metadata["expID"]
        except KeyError:
            pass
        try:
            if metadata["sample"] is not None:
                print(metadata["sample"])
                m["sample"] = metadata["sample"]
        except KeyError:
            pass
        try:
            date = metadata["date"]
            if isinstance(date, str):
                m["date"] = date
            elif isinstance(date, (datetime.date, datetime.datetime)):
                m["date"] = date.strftime("%Y-%m-%d")
        except KeyError:
            pass

        if not m["date"]:
            m["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        formatted_name = "{date}_{expID}_{sample}_{name}".format(**m)

        return formatted_name

    @property
    def path(self) -> str:
        """Path to the file."""
        return self._path

    @property
    def canonical(self):
        """Canonical file name from parsing."""
        return self._canonical

    @property
    def parent(self):
        """Return parent directory of file."""
        return self._parent

    @property
    def stem(self):
        """Return basename of file."""
        return self._stem

    @abstractmethod
    def load(self):
        """Load data from the file."""
        pass

    @abstractmethod
    def _parse_path(self):
        pass

    def canonize(self):
        """Rename the file using the canonical name."""
        _, ext = os.path.splitext(self.path)
        new_path = join(self.parent, f"{self.canonical}{ext}")
        os.rename(self.path, join(self.parent, f"{self.canonical}{ext}"))
        self._path = new_path


class LoaderLike(MutableSequence):
    """Discovers files under a root directory and wraps them in ``FileLike`` objects.

    Subclasses should override :meth:`_gather` to filter relevant files and
    :meth:`_construct` to return a specialised ``FileLike`` subclass.

    Attributes:
        root: Root directory to scan for files.
        items: List of :class:`FileLike` instances found during gathering.
    """

    def __init__(self, data=None, isdir=False, **metadata: Unpack[MetadataDict]):
        """Scan *root* and build a ``FileLike`` for each discovered file.

        Args:
            root: Directory to scan.
            **metadata: Default metadata overrides passed to every
                :class:`FileLike` constructed. See :class:`MetadataOverride`.
        """
        if not data:
            self.items = []
        elif isdir:
            self.items = [self._construct(f, **metadata) for f in self._gather(data)]
        elif isinstance(data, Iterable):
            self.items = [self._construct(f, **metadata) for f in data]

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

    def extend(self, iterable, **metadata: Unpack[MetadataDict]):
        """Extend contents by an iterable."""
        super().extend([self._construct(f, **metadata) for f in iterable])

    def _gather(self, root) -> list:
        """Return a list of full file paths under :arg:`root` to load.

        Override in subclasses to filter by filename pattern.  Subclass
        implementations **must** return full paths (joined with :arg:`root`)
        so that :meth:`_construct` receives a usable path.
        """
        return [join(root, f) for f in os.listdir(root)]

    @abstractmethod
    def _construct(self, f, **metadata: Unpack[MetadataDict]):
        """Build a ``FileLike`` (or subclass) for the given path.

        Override in subclasses to return a specialised ``FileLike``.
        """
        pass


class ProcessLike(ABC):
    """Orchestrates processing of a :class:`LoaderLike` or :class:`FileLike`.

    Attributes:
        output_path: Optional directory path for writing results.
        inputs: A :class:`LoaderLike` or a list of :class:`FileLike`.
    """

    def __init__(
        self,
        data: Union[LoaderLike, FileLike],
        output_path: Union[str, None] = None,
    ):
        """Initialise the processor with a dataset.

        Args:
            dataset: A :class:`LoaderLike` bundle or an individual
                :class:`FileLike` to process.
            output_path: Optional output directory for results.
        """
        self.output_path = output_path
        if isinstance(data, LoaderLike):
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
        pass
