"""Error messages a person reads must not be written for a developer.

Every one of these was found the same way: the maintainer clicked something in
the built app and photographed the red text.

    Package 'QFN-32' is not in the known reference table -- ...
        Add it to PACKAGE_REFERENCE or provide package data manually.
    Part is missing provenance for required field(s): ...
        SPEC-300 §2.2: every inferred field must record its source ...
    ... Parts saved before CTX-308.5 don't have these; re-run generate + save.

A maker reading those is told to edit a Python constant they cannot see and to
consult two documents that live in this repository. The messages are accurate.
They are also, to their reader, useless.

`CLAUDE.md` already carries the norm this belongs to -- a spec for a user-facing
surface has to say what the *user* is doing -- and `SPEC-302` is the example of
what happens when it is skipped. Nothing enforced it for error strings, which is
why three of them shipped.

This walks the AST rather than grepping, so a spec number in a comment or a
docstring is left alone. Only text that can reach a person is checked.
"""
import ast
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_DAEMON = os.path.dirname(_HERE)

#: Modules whose exceptions surface in the app. daemon.py is the JSON-RPC
#: boundary itself; the others raise through it.
_USER_FACING_MODULES = (
    "daemon.py", "library_store.py", "component_pipeline.py",
    "datasheet_guidance.py", "kicad_board.py", "kicad_cli.py",
    "freecad_bridge.py", "footprint_detail.py",
)

#: Things that mean something to whoever wrote the code and nothing to whoever
#: is using the app.
_DEVELOPER_ARTIFACTS = (
    (re.compile(r"\bSPEC-\d+"), "a spec number"),
    (re.compile(r"\bCTX-[\d.]+"), "a context number"),
    (re.compile(r"§"), "a section mark"),
    (re.compile(r"\b[A-Z][A-Z0-9]{3,}_[A-Z0-9_]{3,}\b"), "a source-code constant"),
    (re.compile(r"\bTODO\b|\bFIXME\b"), "a code marker"),
)


def _message_strings(tree):
    """Every string literal that is part of a raised exception's message."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        for sub in ast.walk(node.exc):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                found.append((sub.lineno, sub.value))
    return found


class UserFacingErrorsTests(unittest.TestCase):
    def test_001_no_raised_message_cites_a_spec_or_a_source_identifier(self):
        offenders = []
        for name in _USER_FACING_MODULES:
            path = os.path.join(_DAEMON, name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=name)
            for lineno, text in _message_strings(tree):
                for pattern, description in _DEVELOPER_ARTIFACTS:
                    if pattern.search(text):
                        offenders.append(f"{name}:{lineno} names {description}: {text.strip()[:90]!r}")

        self.assertEqual(
            offenders, [],
            "these messages reach a person in the app:\n  " + "\n  ".join(offenders),
        )

    def test_002_the_scan_would_notice_one(self):
        """A check that cannot fail is not evidence. This is the exact shape
        of the three real messages, run through the same parser."""
        tree = ast.parse(
            'def f():\n'
            '    raise ValueError("Part is missing provenance. SPEC-300 §2.2: every field.")\n'
        )
        messages = _message_strings(tree)

        self.assertEqual(len(messages), 1)
        hits = [d for pattern, d in _DEVELOPER_ARTIFACTS if pattern.search(messages[0][1])]
        self.assertIn("a spec number", hits)
        self.assertIn("a section mark", hits)

    def test_003_ordinary_messages_are_not_flagged(self):
        """The guard has to leave real, plain sentences alone, or it will be
        worked around instead of obeyed."""
        tree = ast.parse(
            'def f():\n'
            '    raise ValueError("Copperplane could not read that board file.")\n'
        )
        text = _message_strings(tree)[0][1]

        self.assertEqual([d for p, d in _DEVELOPER_ARTIFACTS if p.search(text)], [])


if __name__ == "__main__":
    unittest.main()
