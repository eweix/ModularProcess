"""Core data abstractions for modular file processing.

Provides base classes for representing, loading, and writing data files
with structured naming conventions. The module defines type aliases and
abstract interfaces that concrete implementations specialise.
"""

import datetime
import os
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


class FileLike:
    """Wrapper around a file that parses structured metadata from its name.

    ``FileLike`` extracts metadata fields (name, experiment ID, sample, date)
    from a file path and exposes a canonical structured filename. Subclasses
    must implement :meth:`_parse_path` and :meth:`load`.

    Attributes:
        path: Absolute or relative path to the file.
        parent: Parent directory of the file.
        stem: Basename of the file.
        struct_name: Canonical structured filename built from metadata.
    """

    def __init__(
        self,
        path: str,
        **metadata: Unpack[MetadataDict],
    ) -> None:
        """Initialise the wrapper and parse metadata from the file path.

        Args:
            path: Path to the file on disk.
            **metadata: Optional overrides for ``name``, ``expID``, ``sample``,
                ``date``.  If provided these take precedence over values parsed
                from the filename.  ``date`` accepts a ``YYYY-MM-DD`` string,
                a :class:`datetime.date`, a :class:`datetime.datetime`, or
                ``None`` (defaults to today).
        """
        self.path = path
        self.parent = os.path.dirname(path)
        self.stem = os.path.basename(path)

        m = self._parse_path(self.stem)

        name = metadata.get("name")
        if name is not None:
            m["name"] = name
        exp_id = metadata.get("expID")
        if exp_id is not None:
            m["expID"] = exp_id
        sample = metadata.get("sample")
        if sample is not None:
            m["sample"] = sample

        date = metadata.get("date")
        if isinstance(date, str):
            m["date"] = date
        elif isinstance(date, (datetime.date, datetime.datetime)):
            m["date"] = date.strftime("%Y-%m-%d")

        if not m["date"]:
            m["date"] = datetime.datetime.now().strftime("%Y-%m-%d")

        self.struct_name = self._format(m)

    def _format(self, m: MetadataDict) -> str:
        """Format structured name according to spec."""
        return "{date}_{expID}_{sample}_{name}".format(**m)

    def _parse_path(self, f: str) -> MetadataDict:
        """Extract metadata from filename."""
        raise NotImplementedError

    def load(self):
        """Load file into memory."""
        raise NotImplementedError

    def canonize(self):
        """Rename the file on disk to its canonical structured name.

        After calling this method the file at ``self.path`` will be
        moved to ``self.parent / self.struct_name`` (preserving the
        original file extension), overwriting any existing file at
        that location.
        """
        _, ext = os.path.splitext(self.path)
        os.rename(self.path, join(self.parent, f"{self.struct_name}{ext}"))


class LoaderLike:
    """Discovers files under a root directory and wraps them in ``FileLike`` objects.

    Subclasses should override :meth:`_gather` to filter relevant files and
    :meth:`_construct` to return a specialised ``FileLike`` subclass.

    Attributes:
        root: Root directory to scan for files.
        items: List of :class:`FileLike` instances found during gathering.
    """

    def __init__(
        self,
        root: Union[str, None] = None,
        **metadata: Unpack[MetadataDict],
    ):
        """Scan *root* and build a ``FileLike`` for each discovered file.

        Args:
            root: Directory to scan.
            **metadata: Default metadata overrides passed to every
                :class:`FileLike` constructed. See :class:`MetadataOverride`.
        """
        self.root = root

        if root:
            files = self._gather(root)
            self.items = [self._construct(f, **metadata) for f in files]
        else:
            self.items = []

    def _gather(self, root: str) -> list[str]:
        """Return a list of full file paths under :arg:`root` to load.

        Override in subclasses to filter by filename pattern.  Subclass
        implementations **must** return full paths (joined with :arg:`root`)
        so that :meth:`_construct` receives a usable path.
        """
        return [join(root, f) for f in os.listdir(root)]

    def _construct(self, f: str, **metadata: Unpack[MetadataDict]):
        """Build a ``FileLike`` (or subclass) for the given path.

        Override in subclasses to return a specialised ``FileLike``.
        """
        return FileLike(f, **metadata)

    def add_files(self, paths: Union[str, list[str]], **metadata: Unpack[MetadataDict]):
        """Append additional file paths to :attr:`items`."""
        if isinstance(paths, str):
            paths = [paths]
        to_add = [self._construct(f, **metadata) for f in paths]
        self.items.extend(to_add)


class ProcessLike:
    """Orchestrates processing of a :class:`LoaderLike` or a single :class:`FileLike`.

    Attributes:
        output_path: Optional directory path for writing results.
        data: The dataset (a :class:`LoaderLike`) or a single-file list.
    """

    def __init__(
        self,
        dataset: Union[LoaderLike, FileLike],
        output_path: Union[str, None] = None,
    ):
        """Initialise the processor with a dataset.

        Args:
            dataset: A :class:`LoaderLike` bundle or an individual
                :class:`FileLike` to process.
            output_path: Optional output directory for results.
        """
        self.output_path = output_path
        if isinstance(dataset, LoaderLike):
            self.data = dataset
        else:
            self.data = [dataset]

    def run(self):
        """Execute the processing pipeline.

        Subclasses must override this method.
        """
        raise NotImplementedError
