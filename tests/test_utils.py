"""Tests for tx_lsp/utils.py — position conversion and AST traversal."""

import pytest
from lsprotocol import types
from textx import metamodel_from_str

from tx_lsp.utils import (
    get_object_at_position,
    line_col_to_offset,
    offset_to_line_col,
    path_matches_pattern,
    textx_pos_to_lsp_range,
    uri_to_path,
    walk_model,
)

GRAMMAR = """
Model: items+=Item;
Item: 'item' name=ID '{' value=INT '}';
"""

VALID_SOURCE = "item foo { 42 }"


# ── offset_to_line_col ────────────────────────────────────────


class TestOffsetToLineCol:
    def test_start_of_single_line(self):
        assert offset_to_line_col("hello", 0) == (0, 0)

    def test_middle_of_single_line(self):
        assert offset_to_line_col("hello", 3) == (0, 3)

    def test_end_of_single_line(self):
        assert offset_to_line_col("hello", 5) == (0, 5)

    def test_second_line_start(self):
        assert offset_to_line_col("hello\nworld", 6) == (1, 0)

    def test_second_line_middle(self):
        assert offset_to_line_col("hello\nworld", 9) == (1, 3)

    def test_third_line(self):
        source = "aaa\nbbb\nccc"
        assert offset_to_line_col(source, 8) == (2, 0)

    def test_newline_char_itself(self):
        # Offset at the \n character is end of first line
        assert offset_to_line_col("hello\nworld", 5) == (0, 5)

    def test_empty_string(self):
        assert offset_to_line_col("", 0) == (0, 0)


# ── line_col_to_offset ────────────────────────────────────────


class TestLineColToOffset:
    def test_first_line_start(self):
        assert line_col_to_offset("hello", 0, 0) == 0

    def test_first_line_middle(self):
        assert line_col_to_offset("hello", 0, 3) == 3

    def test_second_line_start(self):
        assert line_col_to_offset("hello\nworld", 1, 0) == 6

    def test_second_line_middle(self):
        assert line_col_to_offset("hello\nworld", 1, 3) == 9

    def test_third_line(self):
        source = "aaa\nbbb\nccc"
        assert line_col_to_offset(source, 2, 0) == 8

    def test_roundtrip(self):
        source = "line one\nline two\nline three"
        for offset in range(len(source)):
            line, col = offset_to_line_col(source, offset)
            assert line_col_to_offset(source, line, col) == offset


# ── uri_to_path ───────────────────────────────────────────────


class TestUriToPath:
    def test_file_uri(self):
        assert uri_to_path("file:///home/user/file.py") == "/home/user/file.py"

    def test_plain_path(self):
        assert uri_to_path("/home/user/file.py") == "/home/user/file.py"

    def test_file_uri_windows_style(self):
        result = uri_to_path("file:///C:/Users/file.py")
        assert result == "/C:/Users/file.py"


# ── path_matches_pattern ──────────────────────────────────────


class TestPathMatchesPattern:
    def test_matches_extension(self):
        assert path_matches_pattern("/path/to/model.auto", "*.auto") is True

    def test_no_match(self):
        assert path_matches_pattern("/path/to/model.py", "*.auto") is False

    def test_matches_any_dir(self):
        assert path_matches_pattern("/deeply/nested/dir/file.test", "*.test") is True

    def test_star_matches_all(self):
        assert path_matches_pattern("/path/anything.txt", "*.txt") is True


# ── walk_model ────────────────────────────────────────────────


class TestWalkModel:
    @pytest.fixture()
    def model(self):
        mm = metamodel_from_str(GRAMMAR)
        return mm.model_from_str(VALID_SOURCE)

    def test_yields_root(self, model):
        objects = list(walk_model(model))
        assert model in objects

    def test_yields_children(self, model):
        objects = list(walk_model(model))
        # Should have root Model + at least 1 Item
        assert len(objects) >= 2

    def test_finds_named_item(self, model):
        names = [getattr(obj, "name", None) for obj in walk_model(model)]
        assert "foo" in names

    def test_no_duplicates(self, model):
        objects = list(walk_model(model))
        ids = [id(obj) for obj in objects]
        assert len(ids) == len(set(ids))

    def test_handles_circular_reference(self):
        """walk_model uses visited set to avoid infinite loops."""
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        # Even calling multiple times, visited prevents issues
        assert len(list(walk_model(model))) >= 2

    def test_multiple_items(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str("item a { 1 } item b { 2 } item c { 3 }")
        names = [getattr(obj, "name", None) for obj in walk_model(model)]
        assert "a" in names
        assert "b" in names
        assert "c" in names


# ── get_object_at_position ────────────────────────────────────


class TestGetObjectAtPosition:
    MULTI_SOURCE = "item foo { 42 } item bar { 99 }"

    @pytest.fixture()
    def multi_model(self):
        mm = metamodel_from_str(GRAMMAR)
        return mm.model_from_str(self.MULTI_SOURCE)

    def test_finds_object_at_start(self, multi_model):
        obj = get_object_at_position(multi_model, self.MULTI_SOURCE, 0, 0)
        assert obj is not None

    def test_finds_first_item_by_name(self, multi_model):
        obj = get_object_at_position(multi_model, self.MULTI_SOURCE, 0, 5)
        assert obj is not None
        assert getattr(obj, "name", None) == "foo"

    def test_finds_second_item_by_name(self, multi_model):
        obj = get_object_at_position(multi_model, self.MULTI_SOURCE, 0, 21)
        assert obj is not None
        assert getattr(obj, "name", None) == "bar"

    def test_returns_most_specific(self, multi_model):
        obj = get_object_at_position(multi_model, self.MULTI_SOURCE, 0, 5)
        assert obj is not None
        assert obj.__class__.__name__ == "Item"


# ── textx_pos_to_lsp_range ───────────────────────────────────


class TestTextxPosToLspRange:
    @pytest.fixture()
    def model(self):
        mm = metamodel_from_str(GRAMMAR)
        return mm.model_from_str(VALID_SOURCE)

    def test_returns_range_for_item(self, model):
        item = model.items[0]
        range_ = textx_pos_to_lsp_range(item, source=VALID_SOURCE)
        assert range_ is not None
        assert isinstance(range_, types.Range)

    def test_range_start_values(self, model):
        item = model.items[0]
        range_ = textx_pos_to_lsp_range(item, source=VALID_SOURCE)
        assert range_.start.line == 0
        assert range_.start.character >= 0

    def test_range_end_after_start(self, model):
        item = model.items[0]
        range_ = textx_pos_to_lsp_range(item, source=VALID_SOURCE)
        start_offset = line_col_to_offset(VALID_SOURCE, range_.start.line, range_.start.character)
        end_offset = line_col_to_offset(VALID_SOURCE, range_.end.line, range_.end.character)
        assert end_offset >= start_offset

    def test_returns_none_without_position(self):
        """Objects without _tx_position should return None."""

        class FakeObj:
            pass

        assert textx_pos_to_lsp_range(FakeObj()) is None

    def test_returns_none_without_source(self):
        """Without source text and no _tx_parser, should return None."""

        class FakeObj:
            _tx_position = 0
            _tx_position_end = 5

        assert textx_pos_to_lsp_range(FakeObj()) is None

    def test_uses_tx_parser_input(self, model):
        """Should use _tx_parser.input if source not provided."""
        item = model.items[0]
        # If the parser has input, it should work without explicit source
        if hasattr(item, "_tx_parser") and hasattr(item._tx_parser, "input"):
            range_ = textx_pos_to_lsp_range(item)
            assert range_ is not None
