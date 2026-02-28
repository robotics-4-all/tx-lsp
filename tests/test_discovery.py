"""Tests for tx_lsp/discovery.py — language registry and discovery."""

import pytest
from textx import metamodel_from_str

from tx_lsp.discovery import LanguageInfo, LanguageRegistry

GRAMMAR = """
Model: items+=Item;
Item: 'item' name=ID '{' value=INT '}';
"""


def _make_lang(name="testlang", pattern="*.test"):
    return LanguageInfo(
        name=name,
        pattern=pattern,
        description=f"Test {name}",
        metamodel_factory=lambda: metamodel_from_str(GRAMMAR),
    )


# ── LanguageInfo ──────────────────────────────────────────────


class TestLanguageInfo:
    def test_attributes(self):
        lang = _make_lang()
        assert lang.name == "testlang"
        assert lang.pattern == "*.test"
        assert lang.description == "Test testlang"

    def test_repr(self):
        lang = _make_lang()
        r = repr(lang)
        assert "testlang" in r
        assert "*.test" in r

    def test_get_metamodel_lazily_creates(self):
        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return metamodel_from_str(GRAMMAR)

        lang = LanguageInfo(
            name="lazy", pattern="*.lazy", description="", metamodel_factory=factory
        )
        assert lang._metamodel is None
        mm = lang.get_metamodel()
        assert mm is not None
        assert call_count["n"] == 1

    def test_get_metamodel_caches(self):
        call_count = {"n": 0}

        def factory():
            call_count["n"] += 1
            return metamodel_from_str(GRAMMAR)

        lang = LanguageInfo(
            name="cached", pattern="*.cached", description="", metamodel_factory=factory
        )
        mm1 = lang.get_metamodel()
        mm2 = lang.get_metamodel()
        assert mm1 is mm2
        assert call_count["n"] == 1

    def test_matches_file_positive(self):
        lang = _make_lang(pattern="*.test")
        assert lang.matches_file("/path/to/model.test") is True

    def test_matches_file_negative(self):
        lang = _make_lang(pattern="*.test")
        assert lang.matches_file("/path/to/model.py") is False

    def test_matches_file_multiple_patterns(self):
        lang = _make_lang(pattern="*.test *.tst")
        assert lang.matches_file("model.test") is True
        assert lang.matches_file("model.tst") is True
        assert lang.matches_file("model.py") is False

    def test_matches_file_just_filename(self):
        lang = _make_lang(pattern="*.test")
        assert lang.matches_file("model.test") is True


# ── LanguageRegistry ──────────────────────────────────────────


class TestLanguageRegistry:
    def test_empty_registry(self):
        registry = LanguageRegistry()
        assert registry.all_languages() == []
        assert registry.all_patterns() == set()

    def test_language_for_file_no_match(self):
        registry = LanguageRegistry()
        assert registry.language_for_file("model.py") is None

    def test_manual_registration(self):
        registry = LanguageRegistry()
        lang = _make_lang()
        registry._languages["testlang"] = lang
        assert len(registry.all_languages()) == 1
        assert registry.all_languages()[0].name == "testlang"

    def test_language_for_file_registered(self):
        registry = LanguageRegistry()
        lang = _make_lang()
        registry._languages["testlang"] = lang
        found = registry.language_for_file("model.test")
        assert found is lang

    def test_language_for_file_no_registered_match(self):
        registry = LanguageRegistry()
        lang = _make_lang()
        registry._languages["testlang"] = lang
        assert registry.language_for_file("model.py") is None

    def test_extra_pattern_override(self):
        registry = LanguageRegistry()
        lang = _make_lang()
        registry._languages["testlang"] = lang
        registry.register_extra_pattern("*.custom", "testlang")

        found = registry.language_for_file("model.custom")
        assert found is lang

    def test_extra_pattern_takes_precedence(self):
        registry = LanguageRegistry()
        lang1 = _make_lang(name="lang1", pattern="*.ext")
        lang2 = _make_lang(name="lang2", pattern="*.other")
        registry._languages["lang1"] = lang1
        registry._languages["lang2"] = lang2
        # Override *.ext to point to lang2
        registry.register_extra_pattern("*.ext", "lang2")

        found = registry.language_for_file("model.ext")
        assert found is lang2

    def test_all_patterns_includes_registered_and_extra(self):
        registry = LanguageRegistry()
        lang = _make_lang(pattern="*.test *.tst")
        registry._languages["testlang"] = lang
        registry.register_extra_pattern("*.custom", "testlang")

        patterns = registry.all_patterns()
        assert "*.test" in patterns
        assert "*.tst" in patterns
        assert "*.custom" in patterns

    def test_discover_populates_languages(self):
        """discover() should not crash even if no textX languages are installed."""
        registry = LanguageRegistry()
        # This may or may not find languages depending on the environment,
        # but it should not raise.
        registry.discover()
        # At minimum textX itself is usually installed
        assert isinstance(registry.all_languages(), list)

    def test_extra_pattern_for_missing_language(self):
        registry = LanguageRegistry()
        registry.register_extra_pattern("*.custom", "nonexistent")
        assert registry.language_for_file("model.custom") is None
