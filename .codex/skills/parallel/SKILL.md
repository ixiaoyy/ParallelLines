---
name: parallel
description: "Orchestrate Trellis multi-agent worktrees: plan focused tasks, configure context, start agents, and report monitoring commands."
---

# Parallel

Use when multiple independent work items should run in isolated worktrees.

## Role

You are the orchestrator in the main repo. Do not implement feature code directly; plan and dispatch worktree agents.

## Fast startup

```bash
python ./.trellis/scripts/get_context.py
python ./.trellis/scripts/get_context.py --mode packages
cat .trellis/spec/guides/index.md
```

Do not read full `.trellis/workflow.md` unless the user asks about workflow details.

## Choose approach

### A. Plan agent (recommended for complex/unclear work)

```bash
python ./.trellis/scripts/multi_agent/plan.py \
  --name "<feature-name>" \
  --type "<backend|frontend|fullstack>" \
  --requirement "<requirement>" \
  --platform codex
```

Then:

```bash
python ./.trellis/scripts/multi_agent/start.py "$TASK_DIR" --platform codex
```

### B. Manual setup (clear/focused work)

```bash
TASK_DIR=$(python ./.trellis/scripts/task.py create "<title>" --slug <slug>)
python ./.trellis/scripts/task.py init-context "$TASK_DIR" <backend|frontend|fullstack>
python ./.trellis/scripts/task.py set-branch "$TASK_DIR" codex/<name>
python ./.trellis/scripts/task.py add-context "$TASK_DIR" implement "<path>" "<reason>"
python ./.trellis/scripts/task.py add-context "$TASK_DIR" check "<path>" "<reason>"
python ./.trellis/scripts/task.py validate "$TASK_DIR"
python ./.trellis/scripts/multi_agent/start.py "$TASK_DIR" --platform codex
```

Create a concise `prd.md` before start.

## Monitoring output

Give user:

```bash
python ./.trellis/scripts/multi_agent/status.py
python ./.trellis/scripts/multi_agent/status.py --log <name>
python ./.trellis/scripts/multi_agent/status.py --watch <name>
python ./.trellis/scripts/multi_agent/cleanup.py <branch>
```

## Rules

- Prefer narrow independent tasks.
- Dispatch only after requirements and context are clear enough.
- Do not commit in the main repo unless explicitly asked.
