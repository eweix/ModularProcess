"""Contract tests for the modularprocessing core.

These tests verify that the base classes (FileLike, LoaderLike, ProcessLike)
and their extension points behave as specified.
"""

import datetime
import os

import pytest
from typing_extensions import Unpack

from modularprocessing import FileLike, LoaderLike, ProcessLike
from modularprocessing.modularprocessing import MetadataDict

# ---------------------------------------------------------------------------
# FileLike
# ---------------------------------------------------------------------------


class MinimalFile(FileLike):
    """Dummy FileLike used for testing."""

    def _parse_path(self) -> MetadataDict:
        return {
            "name": "test",
            "expID": "ABC-01-001",
            "sample": "S1",
            "date": "2025-01-15",
        }

    def load(self):
        return "data"


def test_parseless_raises_typeerror():
    """No _parse_path method raises typeerror."""

    class ParselessFile(FileLike):
        """FileLike that lacks a _parse_path implementation."""

        def load(self):
            return "data"

    with pytest.raises(TypeError):
        ParselessFile("/some/path/file.csv")


def test_loadless_raises_typeerror():
    """No load method raises typeerror."""

    class LoadlessFile(FileLike):
        """Filelike without load implementation."""

        def _parse_path(self) -> MetadataDict:
            return {
                "name": "test",
                "expID": "ABC-01-001",
                "sample": "S1",
                "date": "2025-01-15",
            }

    with pytest.raises(TypeError):
        LoadlessFile("/some/path/file.csv")


def test_minimal_file_constructs():
    """Overriding :meth:``load`` and :meth:``_parse_path`` works."""
    f = MinimalFile("/data/2025-01-15_ABC-01-001_S1_test.csv")
    assert f.path == "/data/2025-01-15_ABC-01-001_S1_test.csv"
    assert f.stem == "2025-01-15_ABC-01-001_S1_test.csv"
    assert f.parent == "/data"
    assert f.canonical == "2025-01-15_ABC-01-001_S1_test"
    assert f.load() == "data"


def test_metadata_override_takes_precedence():
    """Keyword overrides replace parsed values."""
    f = MinimalFile(
        "/data/2025-01-15_ABC-01-001_S1_test.csv",
        name="override_name",
        expID="OVR-99-888",
    )
    print(f.canonical)
    assert "override_name" in f.canonical
    assert "OVR-99-888" in f.canonical


def test_date_override_str():
    f = MinimalFile("/data/file.csv", date="2024-12-01")
    print(f.canonical)
    assert f.canonical.startswith("2024-12-01")


def test_date_override_datetime():
    f = MinimalFile("/data/file.csv", date=datetime.date(2024, 6, 15))  # type: ignore - date can take datetime.date
    assert f.canonical.startswith("2024-06-15")


def test_date_defaults_to_today():
    """When no date is parsed or provided, fall back to today."""

    class NoDateFile(FileLike):
        """FileLike that never provides a date (tests fallback to today)."""

        def _parse_path(self) -> MetadataDict:
            return {"name": "x", "expID": "x", "sample": "x", "date": None}

        def load(self):
            pass

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    f = NoDateFile("/data/file.csv")
    assert f.canonical.startswith(today)


def test_canonical_contains_none_when_missing():
    """Unparsed fields produce literal 'None' in the canonical name."""

    class NameOnlyFile(FileLike):
        """FileLike that only provides a name, leaving other fields None."""

        def _parse_path(self) -> MetadataDict:
            return {"name": "only_name", "expID": None, "sample": None, "date": None}

        def load(self):
            pass

    f = NameOnlyFile("/data/file.csv")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    assert f.canonical == f"{today}_None_None_only_name"


def test_canonize_renames_file(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    src = d / "old_name.csv"
    src.write_text("a,b\n1,2")

    f = MinimalFile(str(src))

    target = d / f"{f.canonical}.csv"

    f.canonize()
    assert target.exists()
    assert not src.exists()
    assert target.read_text() == "a,b\n1,2"


# ---------------------------------------------------------------------------
# LoaderLike
# ---------------------------------------------------------------------------


class MinimalLoader(LoaderLike):
    def _construct(self, f: str, **metadata: Unpack[MetadataDict]):
        return MinimalFile(f)


def test_constructless_raises_typeerror():
    """A LoaderLike without _construct method raises TypeError."""

    class ConstructlessLoader(LoaderLike):
        pass

    with pytest.raises(TypeError):
        ConstructlessLoader()


def test_loaderlike_empty_root():
    """Passing root=None results in empty items."""

    loader = MinimalLoader()
    assert loader.items == []


def test_loaderlike_extend(tmp_path):
    """extend adds items with new FileLike objects."""

    class CustomLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return MinimalFile(f, **metadata)

    loader = CustomLoader()
    assert len(loader) == 0

    (tmp_path / "extra.csv").write_text("")
    loader.extend([str(tmp_path / "extra.csv")])
    # assert len(loader.items) == 1  # this assertion is redundant to the next one
    print(loader[0])
    assert loader[0].stem == "extra.csv"


def test_loaderlike_gather_returns_full_paths(tmp_path):
    """Default _gather joins root with each entry."""

    class CustomLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return MinimalFile(f, **metadata)

    (tmp_path / "a.csv").write_text("")
    (tmp_path / "b.csv").write_text("")
    loader = CustomLoader(str(tmp_path), isdir=True)
    for item in loader.items:
        assert os.path.isabs(item.path) or item.path.startswith(str(tmp_path))
        assert item.parent == str(tmp_path)


def test_loaderlike_custom_gather(tmp_path):
    """Subclass _gather can filter and still returns full paths."""

    class CSVLoader(LoaderLike):
        def _gather(self, root):
            return [
                os.path.join(root, f) for f in os.listdir(root) if f.endswith(".csv")
            ]

        def _construct(self, f, **metadata):
            print(f)
            return MinimalFile(f, **metadata)

    (tmp_path / "keep.csv").write_text("")
    (tmp_path / "ignore.txt").write_text("")
    loader = CSVLoader(str(tmp_path), isdir=True)
    assert len(loader.items) == 1
    assert loader.items[0].stem == "keep.csv"


def test_loaderlike_custom_construct(tmp_path):
    """Subclass _construct returns a custom FileLike."""

    class CustomFile(FileLike):
        def _parse_path(self) -> MetadataDict:
            return {"name": "c", "expID": "c", "sample": "c", "date": None}

        def load(self):
            pass

    class CustomLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return CustomFile(f, **metadata)

    (tmp_path / "data.csv").write_text("")
    loader = CustomLoader(str(tmp_path), isdir=True)
    assert isinstance(loader.items[0], CustomFile)


def test_loaderlike_metadata_propagates_to_files(tmp_path):
    """Default metadata kwargs are passed to _construct and thus to FileLike."""

    class InspectLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return MinimalFile(f, **metadata)

    (tmp_path / "file.csv").write_text("")
    loader = InspectLoader(str(tmp_path), expID="OVERRIDDEN", isdir=True)
    assert "OVERRIDDEN" in loader.items[0].canonical


# ---------------------------------------------------------------------------
# ProcessLike
# ---------------------------------------------------------------------------


class MinimalProcess(ProcessLike):
    def run(self):
        return None


def test_runless_process_raises_typeerror(tmp_path):

    class RunlessProcess(ProcessLike):
        pass

    f = MinimalFile(str(tmp_path / "x.csv"))

    with pytest.raises(TypeError):
        process = RunlessProcess(f)  # noqa


def test_processlike_wraps_loaderlike(tmp_path):
    """ProcessLike accepts a LoaderLike and stores it as .inputs."""

    class CustomLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return MinimalFile(f, **metadata)

    (tmp_path / "a.csv").write_text("")
    loader = CustomLoader(str(tmp_path))
    p = MinimalProcess(loader)
    assert p.inputs is loader


def test_processlike_wraps_single_file(tmp_path):
    """ProcessLike accepts a single FileLike and wraps it in a list."""
    f = MinimalFile(str(tmp_path / "x.csv"))
    p = MinimalProcess(f)
    assert isinstance(p.inputs, list)
    assert len(p.inputs) == 1
    assert p.inputs[0] is f


def test_processlike_with_subclass_loader(tmp_path):
    """isinstance check ensures subclassed loaders are recognised."""

    class SubLoader(LoaderLike):
        def _construct(self, f, **metadata):
            return MinimalFile(f, **metadata)

    (tmp_path / "a.csv").write_text("")
    loader = SubLoader(str(tmp_path))
    p = MinimalProcess(loader)
    assert p.inputs is loader


def test_processlike_output_path(tmp_path):
    p = MinimalProcess(MinimalFile("/x.csv"), output_path=str(tmp_path))
    assert p.output_path == str(tmp_path)
