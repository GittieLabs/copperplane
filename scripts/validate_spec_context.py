import argparse
import os
import re
import subprocess
import sys
import yaml

# Extension patterns considered "code" that requires a context update
CODE_EXTENSIONS = ('.rs', '.ts', '.tsx', '.js', '.jsx', '.py', '.toml', '.json')

# Ignored paths (CI configs, docs, specs/context directory files themselves)
EXCLUDE_PATHS = ('.github/', 'specs/', 'context/', 'LICENSE', 'README.md')

REQUIRED_CTX_FRONTMATTER = ['id', 'spec_ref', 'status', 'branch', 'commit_hashes']

def run_git_cmd(args):
    """Executes a git command and returns standard output."""
    result = subprocess.run(['git'] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Git error: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip().splitlines()

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
        elif path.endswith(CODE_EXTENSIONS) and not any(path.startswith(ex) for ex in EXCLUDE_PATHS):
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

        # Check Testing Requirements Matrix for valid file paths
        matrix_errors = validate_testing_matrix(ctx_file)
        errors.extend(matrix_errors)

    # Output Results
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