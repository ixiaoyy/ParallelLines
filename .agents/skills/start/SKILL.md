---
name: start
description: "Fast Trellis session init: get developer/git/task context, route requests, and defer spec reads until coding scope is known."
---

# Start (Fast Trellis)

Goal: restore project context quickly without loading the whole Trellis knowledge base.

## Fast init

Run and summarize only the useful bits:

```bash
python ./.trellis/scripts/get_context.py
python ./.trellis/scripts/get_context.py --mode packages
```

If a current task exists, also read only:

```bash
cat <task>/prd.md
cat <task>/task.json
```

Read `.trellis/spec/guides/index.md` for available thinking guides. Do **not** read full `.trellis/workflow.md` unless the user asks about workflow/Trellis or the command output indicates setup problems.

## Routing

Classify the user request:

| Type | Default action |
|---|---|
| Question | Answer directly from repo/context. |
| Trivial edit | Inspect target, edit directly; skip `$before-dev`; mention `$finish-work` if code changed. |
| Trellis/skill/tooling edit | Inspect local workflow files; skip `$before-dev` unless app code is touched. |
| Clear small task | Use `$before-dev` lite/full as needed, implement, `$check`. |
| Vague/architectural task | Use `$brainstorm`. |
| Existing task | Ask whether to continue it only if the user's request is ambiguous. |

## Coding rule

Before non-trivial app code changes, read task-relevant specs with `$before-dev` or equivalent targeted reads:

1. Determine affected layer: frontend / backend / fullstack.
2. Read that layer's `index.md`.
3. Read only checklist files relevant to the change.
4. Read shared guides only when their trigger applies.

Avoid loading all specs or all journals.

## Lightweight task flow

For small but real development work:

```bash
TASK_DIR=$(python ./.trellis/scripts/task.py create "<title>" --slug <slug>)
python ./.trellis/scripts/task.py init-context "$TASK_DIR" <frontend|backend|fullstack>
python ./.trellis/scripts/task.py start "$TASK_DIR"
```

Create a short `prd.md` with Goal, Requirements, Acceptance Criteria, and Technical Notes. Skip long PRDs for one-line fixes.

## Output

Keep the start response short:

- developer / branch / dirty state
- current task, if any
- relevant active-task warning, if any
- next action or direct answer
