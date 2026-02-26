"""Tests for tx_lsp/features/ — all LSP feature modules.

Tests diagnostics, hover, completion, definition, references, and symbols.
Uses a mock LanguageServer-like object to avoid pygls dependencies.
"""

import pytest
from lsprotocol import types
from textx import metamodel_from_str
from unittest.mock import MagicMock

from tx_lsp.discovery import LanguageInfo, LanguageRegistry
from tx_lsp.workspace import ModelManager, ModelState

# ── Shared test grammar and fixtures ──────────────────────────

GRAMMAR = """
Model: items+=Item;
Item: 'item' name=ID '{' value=INT '}';
"""

VALID_SOURCE = "item foo { 42 } item bar { 99 }"
MULTI_SOURCE = "item alpha { 1 } item beta { 2 }"
INVALID_SOURCE = "this is not valid at all"

SMAUTO_GRAMMAR = """
Model:
    (entities+=Entity)*
    (brokers+=Broker)*
    (automations+=Automation)*
;

Broker: 'broker' name=ID '{' host=STRING '}';

Entity:
    'entity' name=ID '{'
        (attributes+=Attribute)*
    '}'
;

Attribute: name=ID ':' type=ID;

Automation:
    'automation' name=ID '{'
        ('condition' ':' condition=Condition)?
        ('actions' ':' (actions+=Action)*)?
    '}'
;

Condition: expr=STRING;
Action: 'do' name=ID;
"""

SMAUTO_SOURCE = (
    "entity room {\n"
    "    temperature : float\n"
    "    humidity : float\n"
    "}\n"
    "\n"
    'broker mqtt_broker { "localhost" }\n'
    "\n"
    "automation climate_control {\n"
    '    condition: "temperature > 30"\n'
    "    actions: do cool_down\n"
    "}"
)


def _make_registry():
    registry = LanguageRegistry()
    lang = LanguageInfo(
        name="testlang",
        pattern="*.test",
        description="Test language",
        metamodel_factory=lambda: metamodel_from_str(GRAMMAR),
    )
    registry._languages["testlang"] = lang
    return registry


class FakeLS:
    """Minimal fake language server for feature testing."""

    def __init__(self, tmp_path):
        self.registry = _make_registry()
        self.model_manager = ModelManager(self.registry)
        self._published = []
        self._tmp_path = tmp_path

    def text_document_publish_diagnostics(self, params):
        self._published.append(params)

    @property
    def workspace(self):
        return self

    def get_text_document(self, uri):
        state = self.model_manager.get_state(uri)
        source = state.source if state else ""
        return FakeTextDocument(source)

    def parse_and_get_uri(self, source=VALID_SOURCE):
        uri = f"file://{self._tmp_path}/model.test"
        self.model_manager.parse_document(uri, source)
        return uri


class FakeTextDocument:
    def __init__(self, source):
        self.source = source
        self.lines = source.split("\n")


@pytest.fixture()
def ls(tmp_path):
    return FakeLS(tmp_path)


# ── Diagnostics ───────────────────────────────────────────────

from tx_lsp.features.diagnostics import publish_diagnostics


class TestPublishDiagnostics:
    def test_valid_source_no_diagnostics(self, ls):
        uri = f"file://{ls._tmp_path}/model.test"
        publish_diagnostics(ls, uri, VALID_SOURCE)
        assert len(ls._published) == 1
        assert ls._published[0].diagnostics == []

    def test_invalid_source_has_diagnostics(self, ls):
        uri = f"file://{ls._tmp_path}/model.test"
        publish_diagnostics(ls, uri, INVALID_SOURCE)
        assert len(ls._published) == 1
        assert len(ls._published[0].diagnostics) > 0

    def test_no_language_clears_diagnostics(self, ls):
        uri = f"file://{ls._tmp_path}/model.unknown"
        publish_diagnostics(ls, uri, VALID_SOURCE)
        assert len(ls._published) == 1
        assert ls._published[0].diagnostics == []

    def test_publishes_version(self, ls):
        uri = f"file://{ls._tmp_path}/model.test"
        publish_diagnostics(ls, uri, VALID_SOURCE, version=7)
        assert ls._published[0].version == 7


# ── Hover ─────────────────────────────────────────────────────

from tx_lsp.features.hover import get_hover_info, _build_hover_content


class TestGetHoverInfo:
    def test_hover_on_valid_model(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        result = get_hover_info(ls, uri, pos)
        assert result is not None
        assert isinstance(result, types.Hover)
        assert "Item" in result.contents.value

    def test_hover_returns_none_no_state(self, ls):
        result = get_hover_info(
            ls, "file:///nonexistent.test", types.Position(line=0, character=0)
        )
        assert result is None

    def test_hover_returns_none_invalid_model(self, ls):
        uri = ls.parse_and_get_uri(INVALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = get_hover_info(ls, uri, pos)
        assert result is None

    def test_hover_returns_markdown(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        result = get_hover_info(ls, uri, pos)
        assert result.contents.kind == types.MarkupKind.Markdown

    def test_hover_shows_item_name(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        result = get_hover_info(ls, uri, pos)
        assert "`foo`" in result.contents.value

    def test_hover_returns_none_position_beyond_content(self, ls):
        source = "item a { 1 }\n\n\n"
        uri = f"file://{ls._tmp_path}/model.test"
        ls.model_manager.parse_document(uri, source)
        pos = types.Position(line=2, character=0)
        result = get_hover_info(ls, uri, pos)
        assert result is None


class TestBuildHoverContent:
    def test_class_name_in_content(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        content = _build_hover_content(item)
        assert "**Item**" in content

    def test_name_shown(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        content = _build_hover_content(item)
        assert "`foo`" in content

    def test_attributes_listed(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        content = _build_hover_content(item)
        assert "Attributes" in content
        assert "`name`" in content
        assert "`value`" in content

    def test_object_without_name(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        content = _build_hover_content(model)
        assert "**Model**" in content

    def test_object_without_attrs(self):
        class FakeObj:
            __name__ = "FakeObj"

        obj = FakeObj()
        content = _build_hover_content(obj)
        assert "FakeObj" in content

    def test_list_attribute_shows_count(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        content = _build_hover_content(model)
        assert "[" in content

    def test_scalar_attribute_shows_value(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        content = _build_hover_content(item)
        assert "`42`" in content or "42" in content


from tx_lsp.features.hover import _get_attr_type_name


class TestGetAttrTypeName:
    def test_with_cls_name(self):
        class FakeAttrDesc:
            cls = int

        assert _get_attr_type_name(FakeAttrDesc()) == "int"

    def test_without_cls(self):
        class FakeAttrDesc:
            cls = None

        assert _get_attr_type_name(FakeAttrDesc()) == "unknown"

    def test_cls_without_name(self):
        class FakeAttrDesc:
            cls = "some_string"

        result = _get_attr_type_name(FakeAttrDesc())
        assert isinstance(result, str)

    def test_no_cls_attr(self):
        class FakeAttrDesc:
            pass

        assert _get_attr_type_name(FakeAttrDesc()) == "unknown"


# ── Completion ────────────────────────────────────────────────

from tx_lsp.features.completion import (
    _extract_keywords,
    _get_keyword_completions,
    _get_reference_completions,
    get_completions,
)


class TestExtractKeywords:
    def test_extracts_item_keyword(self):
        mm = metamodel_from_str(GRAMMAR)
        keywords = _extract_keywords(mm)
        assert "item" in keywords

    def test_excludes_punctuation(self):
        mm = metamodel_from_str(GRAMMAR)
        keywords = _extract_keywords(mm)
        assert "{" not in keywords
        assert "}" not in keywords

    def test_returns_set(self):
        mm = metamodel_from_str(GRAMMAR)
        keywords = _extract_keywords(mm)
        assert isinstance(keywords, set)


class TestGetKeywordCompletions:
    def test_returns_completion_items(self):
        lang = _make_registry().all_languages()[0]
        items = _get_keyword_completions(lang, "")
        assert len(items) > 0
        assert all(isinstance(i, types.CompletionItem) for i in items)

    def test_filters_by_prefix(self):
        lang = _make_registry().all_languages()[0]
        items = _get_keyword_completions(lang, "it")
        labels = [i.label for i in items]
        assert "item" in labels

    def test_filters_out_non_matching(self):
        lang = _make_registry().all_languages()[0]
        items = _get_keyword_completions(lang, "zzz")
        assert items == []

    def test_keyword_kind(self):
        lang = _make_registry().all_languages()[0]
        items = _get_keyword_completions(lang, "")
        for item in items:
            assert item.kind == types.CompletionItemKind.Keyword


class TestGetReferenceCompletions:
    def test_empty_for_test_grammar(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        items = _get_reference_completions(model, "")
        assert items == []

    def test_finds_named_smauto_objects(self):
        mm = metamodel_from_str(SMAUTO_GRAMMAR)
        model = mm.model_from_str(SMAUTO_SOURCE)
        items = _get_reference_completions(model, "")
        labels = [i.label for i in items]
        assert "room" in labels
        assert "mqtt_broker" in labels
        assert "climate_control" in labels

    def test_reference_completion_kind(self):
        mm = metamodel_from_str(SMAUTO_GRAMMAR)
        model = mm.model_from_str(SMAUTO_SOURCE)
        items = _get_reference_completions(model, "")
        for item in items:
            assert item.kind == types.CompletionItemKind.Reference


class TestCollectKeywordsFromParser:
    def test_from_metamodel(self):
        from tx_lsp.features.completion import _collect_keywords_from_parser

        mm = metamodel_from_str(GRAMMAR)
        blueprint = getattr(mm, "_parser_blueprint", None)
        if blueprint:
            keywords = set()
            _collect_keywords_from_parser(blueprint, keywords)
            assert "item" in keywords

    def test_no_parser_model(self):
        from tx_lsp.features.completion import _collect_keywords_from_parser

        class FakeParser:
            parser_model = None

        keywords = set()
        _collect_keywords_from_parser(FakeParser(), keywords)
        assert len(keywords) == 0


class TestGetCompletions:
    def test_returns_completion_list(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = get_completions(ls, uri, pos)
        assert isinstance(result, types.CompletionList)

    def test_includes_keywords(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = get_completions(ls, uri, pos)
        labels = [i.label for i in result.items]
        assert "item" in labels

    def test_includes_named_objects(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = get_completions(ls, uri, pos)
        labels = [i.label for i in result.items]
        assert "item" in labels

    def test_no_language_returns_empty(self, ls):
        uri = f"file://{ls._tmp_path}/model.unknown"
        ls.model_manager.parse_document(uri, VALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = get_completions(ls, uri, pos)
        assert result.items == []

    def test_completions_with_prefix_filter(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=2)
        result = get_completions(ls, uri, pos)
        assert isinstance(result, types.CompletionList)

    def test_smauto_completions_include_entities(self):
        mm = metamodel_from_str(SMAUTO_GRAMMAR)
        model = mm.model_from_str(SMAUTO_SOURCE)
        items = _get_reference_completions(model, "")
        labels = [i.label for i in items]
        assert "room" in labels

    def test_keyword_extraction_error_handling(self):
        lang = _make_registry().all_languages()[0]
        items = _get_keyword_completions(lang, "")
        assert isinstance(items, list)


# ── Definition ────────────────────────────────────────────────

from tx_lsp.features.definition import goto_definition, _resolve_reference, _get_model_uri


class TestGotoDefinition:
    def test_definition_on_named_object(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        result = goto_definition(ls, uri, pos)
        assert result is not None
        assert isinstance(result, types.Location)
        assert result.uri is not None

    def test_definition_returns_none_no_state(self, ls):
        pos = types.Position(line=0, character=0)
        result = goto_definition(ls, "file:///nonexistent.test", pos)
        assert result is None

    def test_definition_returns_none_invalid_model(self, ls):
        uri = ls.parse_and_get_uri(INVALID_SOURCE)
        pos = types.Position(line=0, character=0)
        result = goto_definition(ls, uri, pos)
        assert result is None


class TestResolveReference:
    def test_named_object_resolves_to_self(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        result = _resolve_reference(item, model)
        assert result is item

    def test_unnamed_object_returns_none(self):
        class FakeObj:
            pass

        result = _resolve_reference(FakeObj(), None)
        assert result is None

    def test_unnamed_with_parent_no_ref(self):
        class FakeParent:
            _tx_attrs = {}

        class FakeObj:
            name = None
            parent = FakeParent()

        result = _resolve_reference(FakeObj(), None)
        assert result is None

    def test_unnamed_with_parent_ref_attr(self):
        class FakeAttrDesc:
            ref = True

        obj = MagicMock()
        obj.name = None
        obj.__class__.__name__ = "FakeObj"
        parent = MagicMock()
        parent._tx_attrs = {"ref_field": FakeAttrDesc()}
        setattr(parent, "ref_field", obj)
        obj.parent = parent
        delattr(obj, "name")

        result = _resolve_reference(obj, None)
        assert result is obj


class TestGetModelUri:
    def test_fallback_uri(self):
        class FakeObj:
            pass

        assert _get_model_uri(FakeObj(), "file:///fallback.test") == "file:///fallback.test"

    def test_parser_file_name(self):
        class FakeParser:
            file_name = "/path/to/other.test"

        class FakeObj:
            _tx_parser = FakeParser()

        result = _get_model_uri(FakeObj(), "file:///fallback.test")
        assert result == "file:///path/to/other.test"


# ── References ────────────────────────────────────────────────

from tx_lsp.features.references import find_references


class TestFindReferences:
    def test_find_refs_on_named_item(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        results = find_references(ls, uri, pos, include_declaration=True)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_find_refs_returns_empty_no_state(self, ls):
        pos = types.Position(line=0, character=0)
        results = find_references(ls, "file:///nonexistent.test", pos, include_declaration=True)
        assert results == []

    def test_find_refs_returns_empty_invalid_model(self, ls):
        uri = ls.parse_and_get_uri(INVALID_SOURCE)
        pos = types.Position(line=0, character=0)
        results = find_references(ls, uri, pos, include_declaration=True)
        assert results == []

    def test_find_refs_exclude_declaration(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        results_incl = find_references(ls, uri, pos, include_declaration=True)
        results_excl = find_references(ls, uri, pos, include_declaration=False)
        assert len(results_excl) <= len(results_incl)

    def test_find_refs_multiple_items(self, ls):
        uri = ls.parse_and_get_uri(MULTI_SOURCE)
        pos = types.Position(line=0, character=5)
        results = find_references(ls, uri, pos, include_declaration=True)
        assert len(results) >= 1

    def test_ref_locations_have_range(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        pos = types.Position(line=0, character=5)
        results = find_references(ls, uri, pos, include_declaration=True)
        for loc in results:
            assert isinstance(loc, types.Location)
            assert loc.range is not None


from tx_lsp.features.references import _get_ref_uri


class TestGetRefUri:
    def test_fallback_uri_no_parser(self):
        class FakeObj:
            pass

        assert _get_ref_uri(FakeObj(), "file:///fallback") == "file:///fallback"

    def test_with_parser_file_name(self):
        class FakeParser:
            file_name = "/other/file.test"

        class FakeObj:
            _tx_parser = FakeParser()

        assert _get_ref_uri(FakeObj(), "file:///fallback") == "file:///other/file.test"

    def test_with_parser_no_file_name(self):
        class FakeParser:
            file_name = None

        class FakeObj:
            _tx_parser = FakeParser()

        assert _get_ref_uri(FakeObj(), "file:///fallback") == "file:///fallback"


# ── Symbols ───────────────────────────────────────────────────

from tx_lsp.features.symbols import (
    get_document_symbols,
    _get_symbol_kind,
    _get_symbol_name,
    _make_symbol,
)


def _make_smauto_registry():
    registry = LanguageRegistry()
    lang = LanguageInfo(
        name="smauto",
        pattern="*.auto",
        description="SmAuto test",
        metamodel_factory=lambda: metamodel_from_str(SMAUTO_GRAMMAR),
    )
    registry._languages["smauto"] = lang
    return registry


class FakeSmautoLS:
    def __init__(self, tmp_path):
        self.registry = _make_smauto_registry()
        self.model_manager = ModelManager(self.registry)
        self._published = []
        self._tmp_path = tmp_path

    def text_document_publish_diagnostics(self, params):
        self._published.append(params)

    @property
    def workspace(self):
        return self

    def get_text_document(self, uri):
        state = self.model_manager.get_state(uri)
        source = state.source if state else ""
        return FakeTextDocument(source)

    def parse_and_get_uri(self, source):
        uri = f"file://{self._tmp_path}/model.auto"
        self.model_manager.parse_document(uri, source)
        return uri


class TestGetDocumentSymbolsSmauto:
    @pytest.fixture()
    def smauto_ls(self, tmp_path):
        return FakeSmautoLS(tmp_path)

    def test_finds_entities(self, smauto_ls):
        uri = smauto_ls.parse_and_get_uri(SMAUTO_SOURCE)
        result = get_document_symbols(smauto_ls, uri)
        names = [s.name for s in result]
        assert "room" in names

    def test_finds_brokers(self, smauto_ls):
        uri = smauto_ls.parse_and_get_uri(SMAUTO_SOURCE)
        result = get_document_symbols(smauto_ls, uri)
        names = [s.name for s in result]
        assert "mqtt_broker" in names

    def test_finds_automations(self, smauto_ls):
        uri = smauto_ls.parse_and_get_uri(SMAUTO_SOURCE)
        result = get_document_symbols(smauto_ls, uri)
        names = [s.name for s in result]
        assert "climate_control" in names

    def test_entity_has_children(self, smauto_ls):
        uri = smauto_ls.parse_and_get_uri(SMAUTO_SOURCE)
        result = get_document_symbols(smauto_ls, uri)
        entity = [s for s in result if s.name == "room"][0]
        child_names = [c.name for c in entity.children]
        assert "temperature" in child_names
        assert "humidity" in child_names

    def test_automation_has_children(self, smauto_ls):
        uri = smauto_ls.parse_and_get_uri(SMAUTO_SOURCE)
        result = get_document_symbols(smauto_ls, uri)
        auto = [s for s in result if s.name == "climate_control"][0]
        assert len(auto.children) > 0


class TestGetDocumentSymbols:
    def test_returns_empty_no_state(self, ls):
        result = get_document_symbols(ls, "file:///nonexistent.test")
        assert result == []

    def test_returns_empty_invalid_model(self, ls):
        uri = ls.parse_and_get_uri(INVALID_SOURCE)
        result = get_document_symbols(ls, uri)
        assert result == []

    def test_returns_list(self, ls):
        uri = ls.parse_and_get_uri(VALID_SOURCE)
        result = get_document_symbols(ls, uri)
        assert isinstance(result, list)


class TestSymbolHelpers:
    def test_get_symbol_kind_known(self):
        class FakeEntity:
            __name__ = "Entity"

        class Entity:
            pass

        obj = Entity()
        kind = _get_symbol_kind(obj)
        assert kind == types.SymbolKind.Class

    def test_get_symbol_kind_unknown(self):
        class Unknown:
            pass

        obj = Unknown()
        kind = _get_symbol_kind(obj)
        assert kind == types.SymbolKind.Variable

    def test_get_symbol_name_with_name(self):
        class FakeObj:
            name = "my_entity"

        assert _get_symbol_name(FakeObj()) == "my_entity"

    def test_get_symbol_name_without_name(self):
        class FakeObj:
            pass

        assert _get_symbol_name(FakeObj()) == "FakeObj"

    def test_make_symbol_returns_none_without_position(self):
        class FakeObj:
            name = "test"

        result = _make_symbol(FakeObj(), source="test")
        assert result is None

    def test_make_symbol_returns_document_symbol(self):
        mm = metamodel_from_str(GRAMMAR)
        model = mm.model_from_str(VALID_SOURCE)
        item = model.items[0]
        result = _make_symbol(item, source=VALID_SOURCE)
        assert result is not None
        assert isinstance(result, types.DocumentSymbol)
        assert result.name == "foo"
        assert result.detail == "Item"
