# 🛠️ Contributing: Spec & Context-Driven Development

Welcome to the **Hardware Agent Studio**! To keep this codebase scalable, self-documenting, and friendly for both human developers and AI agents, we strictly enforce a **Spec & Context-Driven Development Framework**.

Before writing code, please read this guide. **Pull Requests will be blocked by CI if these rules are not followed.**

---

## 📖 1. The Core Concepts

Every feature, architecture change, or significant bug fix is driven by two types of Markdown files:

1. **`SPEC-*.md` (The "What" and "Why")**
   * Outlines the high-level goals, system architecture, data flow, and known constraints.
   * Lives close to the code it describes (e.g., `apps/tauri-ui/specs/`).
   * Cross-cutting system specs live in the root `/specs/` directory.
2. **`CTX-*.md` (The "How" and "When")**
   * A Context file is the active implementation plan for a specific feature derived from a Spec.
   * Tracks execution phases, the Testing Requirements Matrix, and commit hashes.
   * Scoped to a single feature branch/PR lifecycle.

---

## 🔢 2. Spec ID Numbering

Every spec gets a three-digit ID chosen from a fixed range, so the number alone tells you what
layer of the system it belongs to and roughly where its file lives:

| Range | Layer | Lives in |
| :--- | :--- | :--- |
| `000` | Root architecture | `specs/` |
| `1xx` | Platform & transport foundation | module `specs/` dirs |
| `2xx` | Intelligence layer — LLMs, suppliers, datasheets | `services/python-daemon/specs/` |
| `3xx` | Product surface — viewer, chat, settings, workspace | `apps/tauri-ui/specs/` |
| `4xx` | Distribution & operations | `specs/` |
| `9xx` | Meta — the development framework itself | `specs/` |

`SPEC-000` is reserved for the root architecture overview and is never reused. When you write a new
spec, pick the next unused number in the range that matches its layer — don't reuse or skip ahead
within a range.

---

## 📂 3. Directory Layout

Specs and Context files live as close to the relevant module as possible:

```text
hardware-agent-studio/
├── specs/                           # Root / System-wide Architecture Specs
├── context/                         # Root / System-wide Contexts
├── apps/
│   └── tauri-ui/
│       ├── specs/                   # UI-specific Specs
│       └── context/                 # UI-specific Contexts
└── services/
    └── python-daemon/
        ├── specs/                   # Python IPC Daemon Specs
        └── context/                 # Python Implementation Contexts
```

---

## 🚀 4. The Development Workflow

When picking up a new feature, follow this exact workflow:

### Step 1: Read or Write the Spec
* If a Spec doesn't exist for your architectural domain, create one using `SPEC-TEMPLATE.md`, choosing its ID per the numbering scheme in §2.
* Ensure your Spec clearly defines the data contracts and architectural boundaries.

### Step 2: Create the Context File
* Create a new file like `CTX-101.1-my-feature.md` inside the relevant `context/` folder using `CONTEXT-TEMPLATE.md`.
* Fill out the **YAML Frontmatter** (id, spec_ref, branch, etc.).
* Define your execution phases and populate the **Testing Requirements Matrix**.

### Step 3: Branch and Code
* Create a feature branch matching your Context ID: `git checkout -b feat/CTX-101.1-my-feature`.
* Write your code and your unit tests. 
* **Important:** The paths in your Testing Requirements Matrix must match the actual test files on disk relative to the repo root!

### Step 4: Record Commits
* As you complete phases, commit your work.
* Paste your commit hashes back into the `commit_hashes` array in the YAML frontmatter of your `CTX-*.md` file.

### Step 5: Open a Pull Request
* Open a PR against the `develop` branch.

---

## 🛑 5. CI/CD Gatekeeper Rules

We use a custom GitHub Action (`spec-context-gatekeeper.yml`) to automatically enforce this framework. **Your PR will fail if:**

1. **Missing Context Update:** You modified application code (`.rs`, `.ts`, `.py`, etc.) but did not modify or create a `CTX-*.md` file in the same PR.
2. **Invalid Frontmatter:** Your `CTX-*.md` file is missing required YAML fields (id, status, commit_hashes).
3. **Missing Tests:** The test file paths you listed in the *Testing Requirements Matrix* do not actually exist on disk.
4. **Empty Hashes:** You forgot to record your commit hashes in the frontmatter.

---

## 💡 Tips for AI Agents
If you are an AI agent operating in this repository:
* Always read the root `SPEC-000` (Architecture Overview) first.
* Follow the parent/child links in the Spec files to traverse the graph of the module you are modifying.
* Never hallucinate test file paths in the Testing Matrix. Ensure the file is created on disk.