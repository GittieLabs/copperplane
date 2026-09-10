"""
Prompt template rendering.

Handles {{variable}} interpolation in .prompt.md body text.
Uses double-brace syntax to avoid conflicts with JSON/YAML in front-matter.
"""
from __future__ import annotations

import re
from typing import Any


class PromptTemplate:
    """Renders a prompt body by substituting {{variable}} placeholders."""

    _PATTERN = re.compile(r"\{\{(\w+)\}\}")

    def __init__(self, template: str):
        self._template = template

    def render(self, variables: dict[str, Any] | None = None) -> str:
        """
        Replace {{key}} placeholders with values from the variables dict.

        Missing keys are left as-is (not removed, not errored).
        """
        if not variables:
            return self._template

        def _replace(match: re.Match) -> str:
            key = match.group(1)
            value = variables.get(key)
            return str(value) if value is not None else match.group(0)

        return self._PATTERN.sub(_replace, self._template)

    @property
    def template(self) -> str:
        return self._template

    def variables(self) -> list[str]:
        """Return list of variable names found in the template."""
        return self._PATTERN.findall(self._template)
