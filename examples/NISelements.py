"""``FileLike`` / ``LoaderLike`` subclasses for Nikon NIS-Elements.

Parses ``.nd2`` filenames produced by NIS-Elements and loads image data as
NumPy arrays.

Our NISelements files are stored in directories formatted as

    YYYYMMDD_<expID>

which also allows extraction of date and experiment ID from the loader.

Requires the ``nd2`` package (not included in core dependencies)::

    pip install nd2
"""

import os
import re
from os.path import join

from modularprocessing import FileLike, LoaderLike
from modularprocessing.modularprocessing import MetadataDict


class NISWellFile(FileLike):
    """``FileLike`` for NIS-Elements ``.nd2`` files named with well coordinates.

    Expects filenames matching the pattern::

        Point<sample>_Channel<...>_Seq<4-digit-seq>.nd2
    """

    def _parse_path(self, f: str) -> MetadataDict:
        pattern = re.compile(
            r"Point(?P<sample>.*)_Channel(.*)_Seq(?P<name>\d{4})\.nd2$"
        )
        match = pattern.search(f)
        if match:
            return {
                "sample": match.group("sample"),
                "name": match.group("name"),
                "date": None,
                "expID": None,
            }
        return {"name": None, "expID": None, "sample": None, "date": None}

    def load(self):
        from nd2 import imread

        return imread(self.path)


class NISWellLoopLoader(LoaderLike):
    """``LoaderLike`` that discovers well-named ``.nd2`` files in a directory.

    Filters files by the pattern ``Well<letter><digit>_Point*_Channel*_Seq*.nd2``.
    """

    def _construct(self, f: str, **metadata) -> NISWellFile:
        return NISWellFile(f, **metadata)

    def _gather(self, root: str) -> list[str]:
        contents = os.listdir(root)
        pattern = re.compile(r"^Well[A-Z]\d\d_Point.*_Channel.*_Seq\d{4}\.nd2$")
        matches = [f for f in contents if pattern.search(f)]
        return [join(root, f) for f in matches]


class NISPointFile(FileLike):
    """``FileLike`` for NIS-Elements ``.nd2`` files named with a point identifier.

    Expects filenames matching the pattern::

        Point<sample>_Channel<...>_Seq<4-digit-seq>.nd2
    """

    def _parse_path(self, f: str) -> MetadataDict:
        pattern = re.compile(
            r"^Point(?P<sample>[^_]*)_Channel.*_Seq(?P<name>\d{4})\.nd2$"
        )
        match = pattern.search(f)
        if match:
            return {
                "sample": match.group("sample"),
                "name": match.group("name"),
                "date": None,
                "expID": None,
            }
        return {"name": None, "expID": None, "sample": None, "date": None}

    def load(self):
        from nd2 import imread

        return imread(self.path)


class NISPointLoopLoader(LoaderLike):
    """``LoaderLike`` that discovers point-named ``.nd2`` files in a directory.

    Filters files by the pattern ``Point*_Channel*_Seq*.nd2``.
    """

    def _construct(self, f: str, **metadata) -> NISPointFile:
        return NISPointFile(f, **metadata)

    def _gather(self, root: str) -> list[str]:
        contents = os.listdir(root)
        pattern = re.compile(r"^Point.*_Channel.*_Seq\d{4}\.nd2$")
        matches = [f for f in contents if pattern.search(f)]
        return [join(root, f) for f in matches]
