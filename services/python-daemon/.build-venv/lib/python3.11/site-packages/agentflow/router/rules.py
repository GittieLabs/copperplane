"""
Rule evaluator for YAML-based routing and conditional context loading.

Evaluates `if` conditions from router.prompt.md / context profiles against
a context dict. Conditions are simple expressions like:
    - intent == 'search'
    - channel == 'voice'
    - 'calendar' in message
    - intent in ['search', 'research']
    - 'blog' in message or 'article' in message
    - channel == 'voice' and 'urgent' in message

Uses safe evaluation — no exec/eval of arbitrary code.
"""
from __future__ import annotations

import re
from typing import Any

from agentflow.config.schemas import RoutingRule


class RuleConditionError(ValueError):
    """Raised when a rule condition doesn't match any supported syntax.

    Previously an unparseable condition silently evaluated to False and fell
    through to whatever came next (the next rule, or the router's fallback
    target) with no indication anything was wrong. That made a typo — or a
    double-quoted string, since only single quotes were ever supported —
    indistinguishable from a legitimate non-match.
    """


class RuleEvaluator:
    """
    Evaluates routing rule conditions against a context dict.

    Supports atomic conditions:
        - field == 'value'          (equality)
        - field != 'value'          (inequality)
        - field in ['a', 'b']       (membership)
        - 'substring' in field      (containment)
        - field == true / false     (boolean)

    Compound conditions:
        - cond1 or cond2 or ...     (any must match)
        - cond1 and cond2 and ...   (all must match)

    Note: mixing `and`/`or` in a single expression is not supported.
    Use separate rules for complex logic.
    """

    # Patterns for different condition types. String literals accept either
    # single or double quotes (but not mixed within one literal).
    _QUOTED = r"'([^']*)'|\"([^\"]*)\""
    _EQ_PATTERN = re.compile(rf"^(\w+)\s*==\s*(?:{_QUOTED})$")
    _NEQ_PATTERN = re.compile(rf"^(\w+)\s*!=\s*(?:{_QUOTED})$")
    _IN_LIST_PATTERN = re.compile(r"^(\w+)\s+in\s+\[([^\]]*)\]$")
    _CONTAINS_PATTERN = re.compile(rf"^(?:{_QUOTED})\s+in\s+(\w+)$")
    _BOOL_TRUE_PATTERN = re.compile(r"^(\w+)\s*==\s*true$")
    _BOOL_FALSE_PATTERN = re.compile(r"^(\w+)\s*==\s*false$")

    @staticmethod
    def _quoted_value(m: re.Match, first_group: int) -> str:
        """Return whichever of the two alternate quote groups matched."""
        single, double = m.group(first_group), m.group(first_group + 1)
        return single if single is not None else double

    def evaluate(self, rule: RoutingRule, context: dict[str, Any]) -> bool:
        """Evaluate a single rule's condition against a context dict."""
        condition = rule.condition.strip()
        return self.eval_expr(condition, context)

    def eval_expr(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate a condition expression (supports or/and compounds)."""
        # Check for compound 'or' (split on ' or ' outside quotes)
        if " or " in condition:
            parts = self._split_compound(condition, " or ")
            if len(parts) > 1:
                return any(self._eval_atomic(p.strip(), context) for p in parts)

        # Check for compound 'and'
        if " and " in condition:
            parts = self._split_compound(condition, " and ")
            if len(parts) > 1:
                return all(self._eval_atomic(p.strip(), context) for p in parts)

        return self._eval_atomic(condition, context)

    def match(self, rules: list[RoutingRule], context: dict[str, Any]) -> str | None:
        """
        Return the route_to of the first matching rule, or None.

        Evaluates rules in order and returns the first match.
        """
        for rule in rules:
            if self.evaluate(rule, context):
                return rule.route_to
        return None

    @staticmethod
    def _split_compound(condition: str, separator: str) -> list[str]:
        """Split a compound condition, respecting quoted strings.

        Avoids splitting on 'or'/'and' that appear inside single quotes.
        """
        parts: list[str] = []
        current: list[str] = []
        in_quote = False

        tokens = condition.split(separator)
        for i, token in enumerate(tokens):
            # Count unescaped single quotes to track quote state
            quote_count = token.count("'")
            if in_quote:
                current.append(token)
                if quote_count % 2 == 1:
                    in_quote = False
                    parts.append(separator.join(current))
                    current = []
            else:
                if quote_count % 2 == 1:
                    in_quote = True
                    current.append(token)
                else:
                    parts.append(token)

        # If still in_quote, treat remainder as one part
        if current:
            parts.append(separator.join(current))

        return parts

    def _eval_atomic(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate a single atomic condition (no or/and)."""
        # field == 'value' / field == "value"
        m = self._EQ_PATTERN.match(condition)
        if m:
            return str(context.get(m.group(1), "")) == self._quoted_value(m, 2)

        # field != 'value' / field != "value"
        m = self._NEQ_PATTERN.match(condition)
        if m:
            return str(context.get(m.group(1), "")) != self._quoted_value(m, 2)

        # field in ['a', 'b', 'c']
        m = self._IN_LIST_PATTERN.match(condition)
        if m:
            field_val = str(context.get(m.group(1), ""))
            items = [s.strip().strip("'\"") for s in m.group(2).split(",")]
            return field_val in items

        # 'substring' in field / "substring" in field
        m = self._CONTAINS_PATTERN.match(condition)
        if m:
            substring = self._quoted_value(m, 1).lower()
            field_val = str(context.get(m.group(3), "")).lower()
            return substring in field_val

        # field == true
        m = self._BOOL_TRUE_PATTERN.match(condition)
        if m:
            return bool(context.get(m.group(1)))

        # field == false
        m = self._BOOL_FALSE_PATTERN.match(condition)
        if m:
            return not bool(context.get(m.group(1)))

        # Unknown condition format — fail loudly rather than silently
        # evaluating false and letting the caller fall through to a fallback
        # target as if this were an ordinary non-match.
        raise RuleConditionError(f"Unrecognized rule condition syntax: {condition!r}")
