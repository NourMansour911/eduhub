---
name: update-readme
description: "Inspect recent git changes since the last README commit and update README.md with new features and code changes."
---

# Update README & Documentation Workflow (`/update-readme`)

Use this workflow to keep `README.md` (and related project docs) synchronized with recent code modifications, new skills, workflows, and architectural changes.

---

## Workflow Objectives

1. **Git Commit Inspection**: Find the exact commit where `README.md` was last modified.
2. **Delta Analysis**: Extract all file diffs, new commits, added features, and structural changes since that commit.
3. **Structured Documentation Update**: Update `README.md` with accurate representations of the current codebase state.

---

## Step-by-Step Execution Guide for Agent

### Step 1: Find Last Commit Modifying README
Run the following git command to locate the timestamp and commit hash of the last edit to `README.md`:

```bash
git log -1 --format="%H %cd %s" -- README.md
```

If `README.md` has never been committed, fallback to analyzing the last 10 commits:

```bash
git log -n 10 --oneline
```

### Step 2: Extract Changes Since Last README Commit
Run git diff and commit log commands to review all modifications:

```bash
# Get summary of changed files
git diff --stat <LAST_README_COMMIT>..HEAD

# Get detailed commit logs
git log <LAST_README_COMMIT>..HEAD --oneline
```

### Step 3: Identify Key Project Additions
Analyze the extracted diff for:
- New API endpoints or router files.
- New microservices, LangGraph nodes, or chains.
- New Skills (`.agents/skills/`) or Workflows (`.agents/workflows/`).
- Architectural shifts (e.g., Guardrails integration, Prompt Versioning, Evaluation frameworks).
- Environment variable updates (`.env` / `requirements.txt`).

### Step 4: Propose README Delta & Updates
Present a summary to the user outlining what sections of `README.md` will be updated:
- **New Features**: Added capabilities.
- **Project Structure Tree**: Any new directories or core files.
- **Skills & Workflows**: Newly defined `.agents` skills or workflow commands.
- **Tech Stack & Integrations**: New packages or security layers (e.g. Guardrails, LangSmith Hub).

### Step 5: Apply & Verify README Updates
1. Edit `README.md` cleanly, preserving existing formatting, code examples, and standard section headers.
2. Ensure markdown tables, links, and code snippets are accurate and formatted properly.
3. Inform the user of the completed updates.
