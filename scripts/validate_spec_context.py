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
EXCLUDE_DIR_NAMES = {'.github', 'specs', 'context'}

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


def validate_pr(base_branch):
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

    # RULE 1: Code changes require at least one Context file change
    if code_changed and not context_files_changed:
        errors.append(
            "CRITICAL: Application code was modified, but no CTX-*.md context file was updated in this PR.\n"
            "   -> You must update or create a CTX file under the corresponding module's context/ directory."
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
    args = parser.parse_args()

    validate_pr(args.base)
