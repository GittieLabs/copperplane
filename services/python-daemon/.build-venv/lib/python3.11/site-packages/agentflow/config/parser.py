"""
Markdown + YAML front-matter parser.

Reads .prompt.md, .workflow.md, .context.md, .memory.md files and returns
structured (metadata, body) tuples.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import frontmatter


def parse_prompt_file(path: str | Path) -> tuple[dict[str, Any], str]:
    """
    Parse a markdown file with YAML front-matter.

    Returns (metadata_dict, markdown_body).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    post = frontmatter.load(str(path))
    return dict(post.metadata), post.content


def parse_prompt_string(text: str) -> tuple[dict[str, Any], str]:
    """Parse a string containing YAML front-matter + markdown body."""
    post = frontmatter.loads(text)
    return dict(post.metadata), post.content
