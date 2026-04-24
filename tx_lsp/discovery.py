"""Auto-discovery of textX-registered languages.

Uses textX's registration API (entry_points) to find all installed
languages, their file patterns, and metamodel factories.
"""

import logging
from fnmatch import fnmatch
from pathlib import Path

log = logging.getLogger(__name__)


class LanguageInfo:
    """Describes a discovered textX language."""

    def __init__(self, name, pattern, description, metamodel_factory):
        self.name = name
        self.pattern = pattern
        self.description = description
        self._metamodel_factory = metamodel_factory
        self._metamodel = None

    def get_metamodel(self):
        """Lazily create and cache the metamodel."""
        if self._metamodel is None:
            log.info("Creating metamodel for language '%s'", self.name)
            self._metamodel = self._metamodel_factory()
        return self._metamodel

    def matches_file(self, filepath):
        """Check if a file path matches this language's pattern."""
        name = Path(filepath).name
        # Support multiple patterns separated by space
        for pat in self.pattern.split():
            if fnmatch(name, pat):
                return True
        return False

    def __repr__(self):
        return f"LanguageInfo(name={self.name!r}, pattern={self.pattern!r})"


class LanguageRegistry:
    """Registry of all discovered textX languages.

    Discovers languages via textX's entry_points registration API.
    Also supports manual registration for custom file patterns.
    """

    def __init__(self):
        self._languages = {}  # name -> LanguageInfo
        self._extra_patterns = {}  # pattern -> language_name (for overrides)

    def discover(self):
        """Discover all installed textX languages via entry_points."""
        try:
            from textx import language_descriptions

            for name, lang_desc in language_descriptions().items():
                info = LanguageInfo(
                    name=lang_desc.name,
                    pattern=lang_desc.pattern,
                    description=lang_desc.description or "",
                    metamodel_factory=lang_desc.metamodel,
                )
                self._languages[name] = info
                log.info("Discovered language: %s (pattern: %s)", name, lang_desc.pattern)
        except Exception as e:
            log.error("Failed to discover textX languages: %s", e)

    def register_extra_pattern(self, pattern, language_name):
        """Register an additional file pattern for an existing language.

        Useful when the DSL uses a different extension than what's registered.
        E.g., SmAuto registers '*.smauto' but actual files use '*.auto'.
        """
        self._extra_patterns[pattern] = language_name
        log.info("Registered extra pattern '%s' for language '%s'", pattern, language_name)

    def language_for_file(self, filepath):
        """Find the language that handles a given file path.

        Checks both registered patterns and extra patterns.
        Returns LanguageInfo or None.
        """
        name = Path(filepath).name

        # Check extra patterns first (overrides)
        for pattern, lang_name in self._extra_patterns.items():
            if fnmatch(name, pattern):
                return self._languages.get(lang_name)

        # Check registered language patterns
        for lang in self._languages.values():
            if lang.matches_file(filepath):
                return lang

        return None

    def language_for_name(self, name):
        """Find a language by its registered name.

        Returns LanguageInfo or None.
        """
        return self._languages.get(name)

    def all_languages(self):
        """Return all discovered languages."""
        return list(self._languages.values())

    def all_patterns(self):
        """Return all file patterns (registered + extra) for file watching."""
        patterns = set()
        for lang in self._languages.values():
            for pat in lang.pattern.split():
                patterns.add(pat)
        for pat in self._extra_patterns:
            patterns.add(pat)
        return patterns
