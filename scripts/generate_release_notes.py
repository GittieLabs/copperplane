"""
Generates real release notes from every CTX-*.md file that changed between
two git refs (SPEC-402, CTX-402.1) -- reads each context file's own
"Implementation Log & Commit History" table verbatim, rather than
hand-writing prose that duplicates what's already recorded there. This is
the real, currently-unread asset ROADMAP.md itself names: every CTX file
already carries this table, and nothing until now has ever assembled it
into release notes.

Usage (from the repo root, matching validate_spec_context.py's own
invocation convention):
    python scripts/generate_release_notes.py --from-ref v0.1.0 --to-ref HEAD
    python scripts/generate_release_notes.py  # from-ref defaults to the
                                                # most recent tag, or this
                                                # repo's first commit if
                                                # none exists yet
"""
import argparse
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

_CTX_PATH_RE = re.compile(r'(^|/)context/CTX-[^/]+\.md$')


def _run_git(*args: str) -> str:
    result = subprocess.run(['git', *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def latest_tag() -> str:
    """The most recent real git tag, or None if this repo has never been
    tagged -- a real, expected state for this pipeline's first-ever
    release, not an error."""
    result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def first_commit() -> str:
    return _run_git('rev-list', '--max-parents=0', 'HEAD').strip().splitlines()[0]


def changed_ctx_files(from_ref: str, to_ref: str) -> list:
    """Every CTX-*.md path added or modified in (from_ref, to_ref], at any
    depth -- no pathspec glob relied on (git pathspec globbing isn't
    portable across configs), filtered in Python instead against every
    real context/ directory convention this repo actually uses (root
    context/, apps/tauri-ui/context/, services/python-daemon/context/)."""
    diff_output = _run_git('diff', '--name-only', '--diff-filter=AM', f'{from_ref}..{to_ref}')
    return sorted(
        line.strip() for line in diff_output.splitlines()
        if line.strip() and _CTX_PATH_RE.search(line.strip())
    )


def parse_frontmatter(text: str) -> dict:
    """A minimal, hand-rolled parser for exactly the two real scalar
    fields this script needs (`id`, `title`) -- deliberately not a real
    YAML parser. PyYAML isn't installed on a bare CI runner by default
    (confirmed for real: this repo's own release.yml failed with
    ModuleNotFoundError on its first actual run), and every CTX/SPEC
    frontmatter's `id`/`title` are always simple top-level scalars, never
    something that needs real YAML semantics to parse correctly."""
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not match:
        return {}
    frontmatter = {}
    for line in match.group(1).splitlines():
        key_match = re.match(r'^([a-zA-Z_]+):\s*(.*)$', line.strip())
        if not key_match:
            continue
        key, value = key_match.group(1), key_match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if value:
            frontmatter[key] = value
    return frontmatter


def extract_implementation_log_table(text: str) -> str:
    """Returns the real Markdown table under a CTX file's own '## 3.
    Implementation Log & Commit History' section, verbatim -- the section
    number is fixed by CONTEXT-TEMPLATE.md's own real structure, not
    guessed at."""
    match = re.search(
        r'##\s*3\.\s*Implementation Log\s*&\s*Commit History\s*\n+(.*?)(?:\n---|\n##\s|\Z)',
        text, re.DOTALL,
    )
    return match.group(1).strip() if match else ''


def generate_release_notes(from_ref: str, to_ref: str = 'HEAD') -> str:
    """Reads each changed CTX file's real, current on-disk content (the
    working tree at whatever commit is actually checked out -- CI always
    checks out to_ref before running this, so no separate `git show` per
    file is needed) rather than a second historical read at to_ref."""
    ctx_paths = changed_ctx_files(from_ref, to_ref)
    if not ctx_paths:
        return f"No CTX-*.md changes between {from_ref} and {to_ref}."

    sections = []
    for path in ctx_paths:
        if not os.path.exists(path):
            continue  # deleted in this range -- nothing real left to report
        with open(path, encoding='utf-8') as f:
            text = f.read()
        frontmatter = parse_frontmatter(text)
        ctx_id = frontmatter.get('id', path)
        title = frontmatter.get('title', path)
        table = extract_implementation_log_table(text)
        section = f"### {ctx_id}: {title}"
        if table:
            section += f"\n\n{table}"
        sections.append(section)

    return "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--from-ref', default=None,
        help="Git ref to diff from (default: the most recent tag, or this repo's first commit if untagged)",
    )
    parser.add_argument('--to-ref', default='HEAD')
    args = parser.parse_args()

    from_ref = args.from_ref or latest_tag() or first_commit()
    print(generate_release_notes(from_ref, args.to_ref))


if __name__ == '__main__':
    main()
