import argparse
import glob
import os
import re
import subprocess
import sys
import yaml

# Windows' default console codepage (cp1252) can't encode this script's emoji
# output; a subprocess (no attached console) falls back to it too, so this
# must happen unconditionally, not just when a TTY is detected.
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Extension patterns considered "code" that requires a context update
CODE_EXTENSIONS = ('.rs', '.ts', '.tsx', '.js', '.jsx', '.py', '.toml', '.json')

# Directory names that exempt everything under them from being treated as
# code, no matter how deep in the tree they appear -- root-level AND
# module-level specs/context/.github dirs all count (SPEC-902: the original
# bare `str.startswith(...)` check only ever exempted root-level paths).
#
# CTX-902.3: 'docs' exempts a real, planned documentation site (Astro,
# bringing its own package.json/tsconfig.json -- both in CODE_EXTENSIONS)
# under docs/ at the repo root. Same "any depth" caveat as every other
# entry here applies: a directory literally named `docs` *anywhere* in the
# tree is exempted, not just the root one. Confirmed acceptable for this
# repo specifically -- no other directory named `docs` exists anywhere in
# the tree today (checked directly, not assumed) -- but this is a real,
# deliberate trade-off to record, not an accident.
EXCLUDE_DIR_NAMES = {'.github', 'specs', 'context', 'docs'}

# Exact root-relative paths exempted regardless of extension.
EXCLUDE_EXACT_PATHS = {'LICENSE'}

# Lockfiles are dependency-manager-generated, not a deliberate feature
# change -- exempted by basename regardless of directory (SPEC-902: fixes
# the real, currently-triggering bug where any package-lock.json bump
# demanded a context file).
LOCKFILE_BASENAMES = {'package-lock.json', 'Cargo.lock', 'uv.lock'}

REQUIRED_CTX_FRONTMATTER = ['id', 'spec_ref', 'status', 'branch', 'commit_hashes']
# 'user_facing' is required repo-wide (CTX-901.2) -- checked for every SPEC-*.md
# on every run via validate_spec_graph(), not just files changed in this diff.
REQUIRED_SPEC_FRONTMATTER = ['id', 'title', 'status', 'location', 'user_facing']

# CTX-902.3: the required key existed since SPEC-901, but its *value* was
# never checked -- 35 of 40 real spec files said `status: Draft`, including
# specs shipped months ago, because nothing ever validated it. Matches
# SPEC-TEMPLATE.md's own placeholder enum. Checked repo-wide via
# validate_spec_graph(), same as the other structural spec checks --
# SPEC-TEMPLATE.md itself needs no explicit exemption here: its real path
# is the repo root, not any specs/ directory, so find_all_spec_files()'s
# own glob never includes it in the first place (confirmed directly, not
# assumed).
ALLOWED_SPEC_STATUSES = {'Draft', 'Approved', 'In-Progress', 'Completed', 'Deprecated'}

# Specs deliberately not children of SPEC-000 (framework/meta specs, not
# product architecture) -- excluded from the "orphan root spec" info note.
KNOWN_PARENTLESS_SPEC_IDS = {'SPEC-000', 'SPEC-901', 'SPEC-902', 'SPEC-903'}


def run_git_cmd(args):
    """Executes a git command and returns standard output."""
    result = subprocess.run(['git'] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Git error: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip().splitlines()


def is_excluded_from_code(path):
    """True if `path` should never count as an application-code change,
    regardless of its extension: any README.md (any depth), the root
    LICENSE, lockfiles, or anything under a .github/specs/context
    directory at any depth."""
    if path in EXCLUDE_EXACT_PATHS:
        return True
    basename = os.path.basename(path)
    if basename == 'README.md' or basename in LOCKFILE_BASENAMES:
        return True
    dir_components = path.split('/')[:-1]
    return any(part in EXCLUDE_DIR_NAMES for part in dir_components)


def parse_frontmatter(file_path):
    """Extracts and parses YAML frontmatter from a Markdown file."""
    if not os.path.exists(file_path):
        return None

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match:
        return None

    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"❌ YAML Syntax Error in {file_path}: {e}")
        return None


def validate_testing_matrix(file_path):
    """Parses the Testing Requirements Matrix and verifies test file paths."""
    errors = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_matrix = False
    matrix_found = False

    for line in lines:
        # Detect the Testing Requirements Matrix section header
        if re.match(r'^##\s+.*Testing Requirements Matrix', line, re.IGNORECASE):
            in_matrix = True
            matrix_found = True
            continue

        # Stop parsing if we hit the next H2 section
        if in_matrix and line.startswith('## '):
            in_matrix = False
            continue

        # Parse Markdown table rows
        if in_matrix and line.strip().startswith('|'):
            # Skip the table header and separator rows
            if 'Test ID' in line or '---' in line:
                continue

            # Split row into columns (index 0 is empty string before the first '|')
            columns = [col.strip() for col in line.split('|')]

            # Ensure the row has enough columns (Col 3 is Test File Location)
            if len(columns) >= 5:
                test_file_raw = columns[3]

                # Clean up markdown backticks e.g., `tests/rpc_test.rs` -> tests/rpc_test.rs
                test_file = test_file_raw.replace('`', '').strip()

                # Ignore placeholders
                if test_file and test_file.lower() not in ['n/a', 'none', '-']:
                    # Validate the file exists relative to the repo root
                    if not os.path.exists(test_file):
                        errors.append(f"MISSING TEST FILE: {file_path} references '{test_file}' which does not exist on disk.")

    if not matrix_found:
        errors.append(f"MISSING SECTION: {file_path} does not contain a '## 2. Testing Requirements Matrix' section.")

    return errors


_COMMIT_HASH_TOKEN = re.compile(r'[0-9a-f]{7,40}')


def extract_hash_token(entry):
    """Pulls the leading hex commit hash out of a commit_hashes entry --
    either a bare hash or this repo's own established "<hash> -
    <description>" format (both real, already in use across existing
    context files). Returns None if the entry doesn't start with
    something hash-shaped at all (SPEC-902's own severity split treats
    that as unambiguously a bug, same as a dangling link, not an
    in-progress state)."""
    if not isinstance(entry, str):
        return None
    token = entry.split(' - ', 1)[0].strip()
    return token if _COMMIT_HASH_TOKEN.fullmatch(token) else None


def git_commit_is_reachable(commit_hash):
    """True if `commit_hash` is a real ancestor of (or equal to) the
    current `HEAD` -- real *reachability*, not mere object existence.
    `git cat-file -e <hash>` was tried first and rejected: a commit
    discarded by `git commit --amend` remains a real, loose object in
    the local `.git/objects/` store until garbage collection eventually
    runs (confirmed directly -- `cat-file -e` reports it present right
    after the amend that orphaned it), so that check alone would have
    missed the exact real bug this validator exists to catch.
    `git merge-base --is-ancestor` answers the real question: will this
    hash still resolve to anything once history moves on, the same way
    a citation must resolve to a real page, not just exist as bytes
    somewhere. Deliberately never attempts a network fetch -- a hash
    that isn't already reachable in the current checkout is exactly
    the class of bug this check exists to catch, not something to
    paper over by reaching out to origin."""
    result = subprocess.run(
        ['git', 'merge-base', '--is-ancestor', commit_hash, 'HEAD'],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def validate_commit_hashes_are_real(ctx_file, base_branch, frontmatter):
    """A real bug this check exists to catch, found and fixed across ten
    context files in this repo's own history: a commit_hashes entry can
    look entirely valid -- correct hex format, matches this repo's own
    "<hash> - <description>" convention -- while referring to a commit
    that was never actually pushed anywhere. The concrete, real cause:
    `git commit --amend` used to fold the hash into the very commit it
    describes rewrites history, silently discarding the original,
    pre-amend commit the moment it's amended, before it's ever pushed.
    `scripts/validate_spec_context.py` never caught this, because the
    existing check only verifies the field is non-empty, never that a
    recorded hash actually resolves to something real.

    Deliberately scoped to hashes NEWLY ADDED in this diff (this
    file's own commit_hashes as of `base_branch`, versus its current
    value), not every hash the file has ever recorded. An older,
    already-merged context file can legitimately cite a real commit
    from a since-squashed, since-deleted feature branch (this repo's
    own established convention -- e.g. CTX-315.2's own precedent,
    confirmed directly: `git fetch <url> <that-hash>` against a fresh
    clone fails once the branch is gone, even though the commit was
    completely real and verifiable at the time it was recorded, and
    remains visible forever on the merged PR's own GitHub page). That
    older hash is not fetchable in an unrelated, later PR's own scoped
    checkout through no fault of its own -- re-validating it there
    would be a real, false failure, not a caught bug. A hash someone is
    adding to this file *right now*, in *this* diff, is different: it
    must already be part of the current branch's own history (this
    repo's own real workflow -- `/close-context` collects commits via
    `git log $(git merge-base HEAD origin/develop)..HEAD`, all of which
    are, by construction, reachable right now), so it's safe and
    correct to demand it resolve for real, while it still can."""
    errors = []
    new_hashes = frontmatter.get('commit_hashes') or []
    if not isinstance(new_hashes, list):
        return errors

    old_hashes = []
    show = subprocess.run(
        ['git', 'show', f'{base_branch}:{ctx_file}'], capture_output=True, text=True,
    )
    if show.returncode == 0:
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', show.stdout, re.DOTALL)
        if match:
            try:
                old_fm = yaml.safe_load(match.group(1)) or {}
            except yaml.YAMLError:
                old_fm = {}
            old_hashes = old_fm.get('commit_hashes') or []

    added_hashes = [h for h in new_hashes if h not in old_hashes]

    for entry in added_hashes:
        commit_hash = extract_hash_token(entry)
        if commit_hash is None:
            errors.append(
                f"MALFORMED COMMIT HASH: {ctx_file}'s commit_hashes entry {entry!r} doesn't start "
                f"with a real-looking hex commit hash (7-40 hex characters)."
            )
            continue
        if not git_commit_is_reachable(commit_hash):
            errors.append(
                f"DANGLING COMMIT HASH: {ctx_file} records '{commit_hash}' under commit_hashes, but "
                f"no commit with that hash exists in this checkout's own history. A real, common "
                f"cause: `git commit --amend` was used to fold the hash into the very commit it "
                f"describes, which rewrites the commit to a new hash and silently discards the one "
                f"just recorded, before it's ever pushed -- record the commit's real, final hash "
                f"(the one that's actually pushed), not one from before an amend rewrote it."
            )

    return errors


def validate_user_facing_section(file_path):
    """CTX-901.2: a SPEC-*.md declaring user_facing: true must have a
    '## 5. User & Interaction' section. Structural presence only, not
    content depth -- a TODO-marked stub (a pre-existing spec honestly
    backfilled rather than invented, see CTX-901.2's Plan Drift) still
    passes. Callers scope this to changed files only; unlike
    validate_spec_graph()'s repo-wide checks, a spec that already has the
    section isn't broken by an unrelated PR that doesn't touch it."""
    fm = parse_frontmatter(file_path)
    if not fm or not fm.get('user_facing'):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if re.match(r'^##\s+.*User\s*&\s*Interaction', line, re.IGNORECASE):
            return []

    return [
        f"MISSING USER & INTERACTION SECTION: {file_path} declares user_facing: true but has no "
        f"'## 5. User & Interaction' section."
    ]


def resolve_relative(from_file, rel_path):
    """Resolves rel_path relative to from_file's own directory, matching
    how the markdown links and frontmatter paths in these files are
    written (relative to the file that contains them, not the repo root)."""
    base_dir = os.path.dirname(from_file)
    return os.path.normpath(os.path.join(base_dir, rel_path))


def find_all_spec_files():
    """Every SPEC-*.md file in the repo, root or module-level, excluding
    the template."""
    return sorted(set(glob.glob('**/specs/SPEC-*.md', recursive=True)))


def find_all_context_files():
    """Every CTX-*.md file in the repo, root or module-level."""
    return sorted(set(glob.glob('**/context/CTX-*.md', recursive=True)))


def validate_spec_graph():
    """Validates the whole SPEC-*.md graph -- not just files changed in
    the current diff, because a change to SPEC-A's child_specs can break
    a link *from* SPEC-B that this PR never touched. Returns
    (hard_errors, informational_findings); informational findings never
    affect the exit code."""
    errors = []
    info = []

    spec_files = find_all_spec_files()
    context_files = find_all_context_files()

    specs_by_id = {}
    specs_by_file = {}

    for path in spec_files:
        fm = parse_frontmatter(path)
        if not fm:
            errors.append(f"INVALID SPEC FORMAT: {path} is missing valid YAML frontmatter (between --- delimiters).")
            continue

        for field in REQUIRED_SPEC_FRONTMATTER:
            if field not in fm or fm[field] is None:
                errors.append(f"MISSING SPEC FRONTMATTER FIELD: {path} is missing required key '{field}'.")

        status = fm.get('status')
        if status is not None and status not in ALLOWED_SPEC_STATUSES:
            errors.append(
                f"INVALID SPEC STATUS: {path} declares status '{status}', which is not one of "
                f"{sorted(ALLOWED_SPEC_STATUSES)}."
            )

        spec_id = fm.get('id')
        if spec_id:
            if spec_id in specs_by_id:
                errors.append(
                    f"DUPLICATE SPEC ID: '{spec_id}' is claimed by both "
                    f"{specs_by_id[spec_id]} and {path}."
                )
            else:
                specs_by_id[spec_id] = path

            filename = os.path.basename(path)
            if not (filename == f"{spec_id}.md" or filename.startswith(f"{spec_id}-")):
                errors.append(
                    f"ID/FILENAME MISMATCH: {path} declares id '{spec_id}', but its filename "
                    f"doesn't start with '{spec_id}-'."
                )

        location = fm.get('location')
        if location and os.path.normpath(location) != os.path.normpath(path):
            errors.append(
                f"LOCATION MISMATCH: {path} declares location '{location}', which does not "
                f"match its own real path."
            )

        specs_by_file[path] = fm

    # Bidirectional parent/child link check, and dangling-path checks.
    for path, fm in specs_by_file.items():
        parent = fm.get('parent_spec')
        if parent:
            resolved_parent = resolve_relative(path, parent)
            if not os.path.exists(resolved_parent):
                errors.append(
                    f"DANGLING parent_spec: {path} points at '{parent}' ({resolved_parent}), "
                    f"which does not exist."
                )
            else:
                parent_fm = specs_by_file.get(resolved_parent)
                if parent_fm is None:
                    parent_fm = parse_frontmatter(resolved_parent) or {}
                parent_children = parent_fm.get('child_specs') or []
                resolved_children = {resolve_relative(resolved_parent, c) for c in parent_children}
                if os.path.normpath(path) not in resolved_children:
                    errors.append(
                        f"ONE-DIRECTIONAL LINK: {path} points at parent '{parent}', but "
                        f"{resolved_parent}'s child_specs does not list it back."
                    )
        elif fm.get('id') not in KNOWN_PARENTLESS_SPEC_IDS:
            info.append(
                f"ORPHAN ROOT SPEC: {path} has no parent_spec and isn't one of the known "
                f"parentless framework specs -- confirm this is intentional."
            )

        for child in (fm.get('child_specs') or []):
            resolved_child = resolve_relative(path, child)
            if not os.path.exists(resolved_child):
                errors.append(
                    f"DANGLING child_specs entry: {path} lists '{child}' ({resolved_child}), "
                    f"which does not exist."
                )

    # Informational: specs with no context file anywhere referencing them.
    context_spec_refs = set()
    for ctx_path in context_files:
        ctx_fm = parse_frontmatter(ctx_path)
        if ctx_fm and ctx_fm.get('spec_ref'):
            context_spec_refs.add(resolve_relative(ctx_path, ctx_fm['spec_ref']))

    for path in specs_by_file:
        if os.path.normpath(path) not in context_spec_refs:
            info.append(f"NO CONTEXT YET: {path} has no CTX-*.md referencing it via spec_ref.")

    return errors, info


def validate_pr(base_branch, labels=None):
    """CTX-902.3: `labels` is the real PR label set (from the workflow's own
    `github.event.pull_request.labels`, passed in as `--labels`, never
    fetched here via the GitHub API -- this script stays runnable offline
    and unit-testable without any real network/token). `trivial-fix`
    bypasses exactly RULE 1 below (the missing-context-file check) and
    nothing else: the spec-graph checks, the Testing Matrix/commit-hash
    checks on any context file this PR *did* touch, and the test/lint jobs
    in the other workflows all still run unconditionally."""
    labels = labels or set()
    print(f"🔍 Analyzing diff against {base_branch}...")

    # Get list of changed files in this PR
    changed_files = run_git_cmd(['diff', '--name-only', f"{base_branch}...HEAD"])

    code_changed = False
    context_files_changed = []
    spec_files_changed = []

    for path in changed_files:
        if not path:
            continue

        # Categorize changes
        if '/context/' in path or path.startswith('context/'):
            if path.endswith('.md') and 'CTX-' in path:
                context_files_changed.append(path)
        elif '/specs/' in path or path.startswith('specs/'):
            if path.endswith('.md') and 'SPEC-' in path:
                spec_files_changed.append(path)
        elif path.endswith(CODE_EXTENSIONS) and not is_excluded_from_code(path):
            code_changed = True

    print(f"  • Code files modified: {code_changed}")
    print(f"  • CONTEXT files modified: {len(context_files_changed)}")
    print(f"  • SPEC files modified: {len(spec_files_changed)}")

    errors = []

    # RULE 1: Code changes require at least one Context file change --
    # bypassed, and only this rule, when the PR carries 'trivial-fix'
    # (CTX-902.3). A silent bypass is how this becomes a hole nobody
    # notices, so it prints a real, visible line every time it fires.
    if code_changed and not context_files_changed:
        if 'trivial-fix' in labels:
            print(
                "\n⚠️  SKIPPED: code changed with no context file, but this PR carries the "
                "'trivial-fix' label -- the context-file requirement is bypassed for this check "
                "only. Tests and lint still ran normally in their own workflows; nothing else "
                "about this validation (spec graph, commit hashes, Testing Matrix) was skipped."
            )
        else:
            errors.append(
                "CRITICAL: Application code was modified, but no CTX-*.md context file was updated in this PR.\n"
                "   -> You must update or create a CTX file under the corresponding module's context/ directory.\n"
                "   -> If this is a small, self-contained fix (a typo, a broken link, an obvious "
                "one-liner), a maintainer can add the 'trivial-fix' label instead of requiring a "
                "context file."
            )

    # RULE 2 & 3: Validate YAML Frontmatter & Testing Matrix on modified Context files
    for ctx_file in context_files_changed:
        frontmatter = parse_frontmatter(ctx_file)
        if not frontmatter:
            errors.append(f"INVALID FORMAT: {ctx_file} is missing valid YAML frontmatter (between --- delimiters).")
            continue

        # Check required frontmatter fields
        for field in REQUIRED_CTX_FRONTMATTER:
            if field not in frontmatter or frontmatter[field] is None:
                errors.append(f"MISSING FRONTMATTER FIELD: {ctx_file} is missing required key '{field}'.")

        # Verify commit_hashes is populated
        hashes = frontmatter.get('commit_hashes', [])
        if not hashes:
            errors.append(f"EMPTY COMMIT HASHES: {ctx_file} must list at least one commit hash under 'commit_hashes'.")
        else:
            errors.extend(validate_commit_hashes_are_real(ctx_file, base_branch, frontmatter))

        # spec_ref must point at a real file, not just be present (SPEC-902)
        spec_ref = frontmatter.get('spec_ref')
        if spec_ref:
            resolved = resolve_relative(ctx_file, spec_ref)
            if not os.path.exists(resolved):
                errors.append(
                    f"DANGLING spec_ref: {ctx_file} points at '{spec_ref}' ({resolved}), which "
                    f"does not exist."
                )

        # Check Testing Requirements Matrix for valid file paths
        matrix_errors = validate_testing_matrix(ctx_file)
        errors.extend(matrix_errors)

    # RULE 5 (CTX-901.2): a *changed* SPEC-*.md with user_facing: true must
    # declare its "## 5. User & Interaction" section. Deliberately scoped to
    # files changed in this diff, not repo-wide like Rule 4 below -- a spec
    # that already has the section shouldn't fail because an unrelated PR
    # touched it, and a pre-existing spec backfilled with an honest TODO
    # stub in the same PR that introduces this field still passes (the check
    # is structural presence, not content depth).
    for spec_file in spec_files_changed:
        errors.extend(validate_user_facing_section(spec_file))

    # RULE 4 (SPEC-902): validate the whole SPEC-*.md graph every run, not
    # only when this diff touches a spec -- a change to one spec's
    # child_specs can break a link from another spec this PR never touched.
    graph_errors, graph_info = validate_spec_graph()
    errors.extend(graph_errors)

    # Output Results
    if graph_info:
        print("\nℹ️  Informational findings (do not block the PR):\n")
        for note in graph_info:
            print(f"  - {note}")

    if errors:
        print("\n❌ Spec & Context Validation Failed:\n")
        for err in errors:
            print(f"  - {err}\n")
        sys.exit(1)
    else:
        print("\n✅ All Spec & Context validations passed successfully!")
        sys.exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Validate SPEC and CONTEXT file updates in PRs.")
    parser.add_argument('--base', required=True, help="Base branch/commit to compare against (e.g. origin/develop)")
    parser.add_argument(
        '--labels', default='',
        help="Comma-separated PR label names (e.g. from GitHub Actions' "
             "${{ join(github.event.pull_request.labels.*.name, ',') }}). "
             "'trivial-fix' bypasses the missing-context-file check only.",
    )
    args = parser.parse_args()

    labels = {label.strip() for label in args.labels.split(',') if label.strip()}
    validate_pr(args.base, labels)
