#!/usr/bin/env python3
"""
Session context generation (default + record modes).

Provides:
    get_context_json          - JSON output for default mode
    get_context_text          - Text output for default mode
    get_context_record_json   - JSON for record mode
    get_context_text_record   - Text for record mode
    output_json               - Print JSON
    output_text               - Print text
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import get_git_packages
from .git import run_git
from .packages_context import get_packages_section
from .tasks import iter_active_tasks, load_task, get_all_statuses, children_progress
from .paths import (
    DIR_SCRIPTS,
    DIR_SPEC,
    DIR_TASKS,
    DIR_WORKFLOW,
    DIR_WORKSPACE,
    count_lines,
    get_active_journal_file,
    get_current_task,
    get_developer,
    get_repo_root,
    get_tasks_dir,
)


# =============================================================================
# Helpers
# =============================================================================

def _collect_package_git_info(repo_root: Path) -> list[dict]:
    """Collect git status and recent commits for packages with independent git repos.

    Only packages marked with ``git: true`` in config.yaml are included.

    Returns:
        List of dicts with keys: name, path, branch, isClean,
        uncommittedChanges, recentCommits.
        Empty list if no git-repo packages are configured.
    """
    git_pkgs = get_git_packages(repo_root)
    if not git_pkgs:
        return []

    result = []
    for pkg_name, pkg_path in git_pkgs.items():
        pkg_dir = repo_root / pkg_path
        if not (pkg_dir / ".git").exists():
            continue

        _, branch_out, _ = run_git(["branch", "--show-current"], cwd=pkg_dir)
        branch = branch_out.strip() or "unknown"

        _, status_out, _ = run_git(["status", "--porcelain"], cwd=pkg_dir)
        changes = len([l for l in status_out.splitlines() if l.strip()])

        _, log_out, _ = run_git(["log", "--oneline", "-5"], cwd=pkg_dir)
        commits = []
        for line in log_out.splitlines():
            if line.strip():
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    commits.append({"hash": parts[0], "message": parts[1]})
                elif len(parts) == 1:
                    commits.append({"hash": parts[0], "message": ""})

        result.append({
            "name": pkg_name,
            "path": pkg_path,
            "branch": branch,
            "isClean": changes == 0,
            "uncommittedChanges": changes,
            "recentCommits": commits,
        })

    return result


def _append_package_git_context(lines: list[str], package_git_info: list[dict]) -> None:
    """Append Git status and recent commits for package repositories."""
    for pkg in package_git_info:
        lines.append(f"## GIT STATUS ({pkg['name']}: {pkg['path']})")
        lines.append(f"Branch: {pkg['branch']}")
        if pkg["isClean"]:
            lines.append("Working directory: Clean")
        else:
            lines.append(
                f"Working directory: {pkg['uncommittedChanges']} uncommitted change(s)"
            )
        lines.append("")
        lines.append(f"## RECENT COMMITS ({pkg['name']}: {pkg['path']})")
        if pkg["recentCommits"]:
            for commit in pkg["recentCommits"]:
                lines.append(f"{commit['hash']} {commit['message']}")
        else:
            lines.append("(no commits)")
        lines.append("")


# =============================================================================
# JSON Output
# =============================================================================

def get_context_json(repo_root: Path | None = None) -> dict:
    """Get context as a dictionary.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.

    Returns:
        Context dictionary.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)
    tasks_dir = get_tasks_dir(repo_root)
    journal_file = get_active_journal_file(repo_root)

    journal_lines = 0
    journal_relative = ""
    if journal_file and developer:
        journal_lines = count_lines(journal_file)
        journal_relative = (
            f"{DIR_WORKFLOW}/{DIR_WORKSPACE}/{developer}/{journal_file.name}"
        )

    # Git info
    _, branch_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
    branch = branch_out.strip() or "unknown"

    _, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    git_status_count = len([line for line in status_out.splitlines() if line.strip()])
    is_clean = git_status_count == 0

    # Recent commits
    _, log_out, _ = run_git(["log", "--oneline", "-5"], cwd=repo_root)
    commits = []
    for line in log_out.splitlines():
        if line.strip():
            parts = line.split(" ", 1)
            if len(parts) >= 2:
                commits.append({"hash": parts[0], "message": parts[1]})
            elif len(parts) == 1:
                commits.append({"hash": parts[0], "message": ""})

    # Tasks
    tasks = [
        {
            "dir": t.dir_name,
            "name": t.name,
            "status": t.status,
            "children": list(t.children),
            "parent": t.parent,
        }
        for t in iter_active_tasks(tasks_dir)
    ]

    # Package git repos (independent sub-repositories)
    pkg_git_info = _collect_package_git_info(repo_root)

    result = {
        "developer": developer or "",
        "git": {
            "branch": branch,
            "isClean": is_clean,
            "uncommittedChanges": git_status_count,
            "recentCommits": commits,
        },
        "tasks": {
            "active": tasks,
            "directory": f"{DIR_WORKFLOW}/{DIR_TASKS}",
        },
        "journal": {
            "file": journal_relative,
            "lines": journal_lines,
            "nearLimit": journal_lines > 1800,
        },
    }

    if pkg_git_info:
        result["packageGit"] = pkg_git_info

    return result


def output_json(repo_root: Path | None = None) -> None:
    """Output context in JSON format.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
    """
    context = get_context_json(repo_root)
    print(json.dumps(context, indent=2, ensure_ascii=False))


# =============================================================================
# Text Output
# =============================================================================

DONE_STATUSES = {"completed", "done"}


def get_context_text(repo_root: Path | None = None, task_limit: int = 10) -> str:
    """Get compact context as formatted text.

    Default output is intentionally short for `$start`: it avoids dumping the full
    non-archived task tree, which can grow large and slow every session.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
        task_limit: Max actionable tasks to print per section.

    Returns:
        Compact formatted text output.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    lines: list[str] = []
    lines.append("========================================")
    lines.append("SESSION CONTEXT")
    lines.append("========================================")
    lines.append("")

    developer = get_developer(repo_root)
    lines.append("## DEVELOPER")
    if not developer:
        lines.append(
            f"ERROR: Not initialized. Run: python3 ./{DIR_WORKFLOW}/{DIR_SCRIPTS}/init_developer.py <name>"
        )
        return "\n".join(lines)
    lines.append(f"Name: {developer}")
    lines.append("")

    lines.append("## GIT STATUS")
    _, branch_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
    branch = branch_out.strip() or "unknown"
    lines.append(f"Branch: {branch}")

    _, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    status_lines = [line for line in status_out.splitlines() if line.strip()]
    if not status_lines:
        lines.append("Working directory: Clean")
    else:
        lines.append(f"Working directory: {len(status_lines)} uncommitted change(s)")
        _, short_out, _ = run_git(["status", "--short"], cwd=repo_root)
        for line in short_out.splitlines()[:10]:
            lines.append(line)
        if len(status_lines) > 10:
            lines.append(f"... {len(status_lines) - 10} more change(s)")
    lines.append("")

    lines.append("## RECENT COMMITS")
    _, log_out, _ = run_git(["log", "--oneline", "-3"], cwd=repo_root)
    lines.extend(log_out.splitlines() if log_out.strip() else ["(no commits)"])
    lines.append("")

    _append_package_git_context(lines, _collect_package_git_info(repo_root))

    tasks_dir = get_tasks_dir(repo_root)
    all_tasks = list(iter_active_tasks(tasks_dir))
    all_statuses = {t.dir_name: t.status for t in all_tasks}
    open_tasks = [t for t in all_tasks if t.status not in DONE_STATUSES]
    my_open_tasks = [t for t in open_tasks if t.assignee == developer]

    lines.append("## CURRENT TASK")
    current_task = get_current_task(repo_root)
    if current_task:
        lines.append(f"Path: {current_task}")
        ct = load_task(repo_root / current_task)
        if ct:
            lines.append(f"Name: {ct.name}")
            lines.append(f"Status: {ct.status}")
            if ct.description:
                lines.append(f"Description: {ct.description}")
        if (repo_root / current_task / "prd.md").is_file():
            lines.append("[!] Read this task's prd.md before continuing.")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("## TASK SUMMARY")
    status_counts: dict[str, int] = {}
    for task in all_tasks:
        status_counts[task.status] = status_counts.get(task.status, 0) + 1
    summary = ", ".join(f"{status}: {count}" for status, count in sorted(status_counts.items()))
    lines.append(f"Non-archived tasks: {len(all_tasks)}" + (f" ({summary})" if summary else ""))
    lines.append(f"Open/non-completed tasks: {len(open_tasks)}")
    lines.append("Completed tasks are summarized, not listed.")
    lines.append("")

    lines.append(f"## MY OPEN TASKS (Assigned to {developer})")
    if my_open_tasks:
        for task in sorted(my_open_tasks, key=lambda t: (t.priority, t.dir_name))[:task_limit]:
            progress = children_progress(task.children, all_statuses)
            lines.append(f"- [{task.priority}] {task.title} ({task.status}){progress} — {task.dir_name}")
        if len(my_open_tasks) > task_limit:
            lines.append(f"... {len(my_open_tasks) - task_limit} more")
    else:
        lines.append("(none)")
    lines.append("")

    other_open = [t for t in open_tasks if t.assignee != developer]
    if other_open:
        lines.append("## OTHER OPEN TASKS")
        for task in sorted(other_open, key=lambda t: (t.assignee or "", t.priority, t.dir_name))[:task_limit]:
            lines.append(f"- [{task.priority}] {task.title} ({task.status}) @{task.assignee or '-'} — {task.dir_name}")
        if len(other_open) > task_limit:
            lines.append(f"... {len(other_open) - task_limit} more")
        lines.append("")

    lines.append("## JOURNAL FILE")
    journal_file = get_active_journal_file(repo_root)
    if journal_file:
        journal_lines = count_lines(journal_file)
        relative = f"{DIR_WORKFLOW}/{DIR_WORKSPACE}/{developer}/{journal_file.name}"
        lines.append(f"Active file: {relative}")
        lines.append(f"Line count: {journal_lines} / 2000")
        if journal_lines > 1800:
            lines.append("[!] WARNING: Approaching 2000 line limit!")
    else:
        lines.append("No journal file found")
    lines.append("")

    packages_text = get_packages_section(repo_root)
    if packages_text:
        lines.append(packages_text)
        lines.append("")

    lines.append("## PATHS")
    lines.append(f"Workspace: {DIR_WORKFLOW}/{DIR_WORKSPACE}/{developer}/")
    lines.append(f"Tasks: {DIR_WORKFLOW}/{DIR_TASKS}/")
    lines.append(f"Spec: {DIR_WORKFLOW}/{DIR_SPEC}/")
    lines.append("")

    lines.append("========================================")
    return "\n".join(lines)



# =============================================================================
# Record Mode
# =============================================================================

def get_context_record_json(repo_root: Path | None = None) -> dict:
    """Get record-mode context as a dictionary.

    Focused on: my active tasks, git status, current task.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    developer = get_developer(repo_root)
    tasks_dir = get_tasks_dir(repo_root)

    # Git info
    _, branch_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
    branch = branch_out.strip() or "unknown"

    _, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    git_status_count = len([line for line in status_out.splitlines() if line.strip()])

    _, log_out, _ = run_git(["log", "--oneline", "-5"], cwd=repo_root)
    commits = []
    for line in log_out.splitlines():
        if line.strip():
            parts = line.split(" ", 1)
            if len(parts) >= 2:
                commits.append({"hash": parts[0], "message": parts[1]})

    # My tasks (single pass — collect statuses and filter by assignee)
    all_tasks_list = list(iter_active_tasks(tasks_dir))
    all_statuses = {t.dir_name: t.status for t in all_tasks_list}

    my_tasks = []
    for t in all_tasks_list:
        if t.assignee == developer:
            done = sum(
                1 for c in t.children
                if all_statuses.get(c) in ("completed", "done")
            )
            my_tasks.append({
                "dir": t.dir_name,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "children": list(t.children),
                "childrenDone": done,
                "parent": t.parent,
                "meta": t.meta,
            })

    # Current task
    current_task_info = None
    current_task = get_current_task(repo_root)
    if current_task:
        ct = load_task(repo_root / current_task)
        if ct:
            current_task_info = {
                "path": current_task,
                "name": ct.name,
                "status": ct.status,
            }

    # Package git repos
    pkg_git_info = _collect_package_git_info(repo_root)

    result = {
        "developer": developer or "",
        "git": {
            "branch": branch,
            "isClean": git_status_count == 0,
            "uncommittedChanges": git_status_count,
            "recentCommits": commits,
        },
        "myTasks": my_tasks,
        "currentTask": current_task_info,
    }

    if pkg_git_info:
        result["packageGit"] = pkg_git_info

    return result


def get_context_text_record(repo_root: Path | None = None) -> str:
    """Get context as formatted text for record-session mode.

    Focused output: MY ACTIVE TASKS first (with [!!!] emphasis),
    then GIT STATUS, RECENT COMMITS, CURRENT TASK.
    """
    if repo_root is None:
        repo_root = get_repo_root()

    lines: list[str] = []
    lines.append("========================================")
    lines.append("SESSION CONTEXT (RECORD MODE)")
    lines.append("========================================")
    lines.append("")

    developer = get_developer(repo_root)
    if not developer:
        lines.append(
            f"ERROR: Not initialized. Run: python3 ./{DIR_WORKFLOW}/{DIR_SCRIPTS}/init_developer.py <name>"
        )
        return "\n".join(lines)

    # MY ACTIVE TASKS — first and prominent
    lines.append(f"## [!!!] MY ACTIVE TASKS (Assigned to {developer})")
    lines.append("[!] Review whether any should be archived before recording this session.")
    lines.append("")

    tasks_dir = get_tasks_dir(repo_root)
    my_task_count = 0

    # Single pass — collect all tasks and filter by assignee
    all_statuses = get_all_statuses(tasks_dir)

    for t in iter_active_tasks(tasks_dir):
        if t.assignee == developer:
            progress = children_progress(t.children, all_statuses)
            lines.append(f"- [{t.priority}] {t.title} ({t.status}){progress} — {t.dir_name}")
            my_task_count += 1

    if my_task_count == 0:
        lines.append("(no active tasks assigned to you)")
    lines.append("")

    # GIT STATUS
    lines.append("## GIT STATUS")
    _, branch_out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
    branch = branch_out.strip() or "unknown"
    lines.append(f"Branch: {branch}")

    _, status_out, _ = run_git(["status", "--porcelain"], cwd=repo_root)
    status_lines = [line for line in status_out.splitlines() if line.strip()]
    status_count = len(status_lines)

    if status_count == 0:
        lines.append("Working directory: Clean")
    else:
        lines.append(f"Working directory: {status_count} uncommitted change(s)")
        lines.append("")
        lines.append("Changes:")
        _, short_out, _ = run_git(["status", "--short"], cwd=repo_root)
        for line in short_out.splitlines()[:10]:
            lines.append(line)
    lines.append("")

    # RECENT COMMITS
    lines.append("## RECENT COMMITS")
    _, log_out, _ = run_git(["log", "--oneline", "-5"], cwd=repo_root)
    if log_out.strip():
        for line in log_out.splitlines():
            lines.append(line)
    else:
        lines.append("(no commits)")
    lines.append("")

    # Package git repos — independent sub-repositories
    _append_package_git_context(lines, _collect_package_git_info(repo_root))

    # CURRENT TASK
    lines.append("## CURRENT TASK")
    current_task = get_current_task(repo_root)
    if current_task:
        lines.append(f"Path: {current_task}")
        ct = load_task(repo_root / current_task)
        if ct:
            lines.append(f"Name: {ct.name}")
            lines.append(f"Status: {ct.status}")
    else:
        lines.append("(none)")
    lines.append("")

    lines.append("========================================")

    return "\n".join(lines)


def output_text(repo_root: Path | None = None, task_limit: int = 10) -> None:
    """Output compact context in text format.

    Args:
        repo_root: Repository root path. Defaults to auto-detected.
        task_limit: Max actionable tasks to show.
    """
    print(get_context_text(repo_root, task_limit=task_limit))
