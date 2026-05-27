---
name: record-session
description: "Record completed, human-tested work into Trellis workspace journals and archive genuinely done tasks."
---

# Record Session

Use after human testing and commit. Do not use as a substitute for validation.

## Steps

1. Get record context:
   ```bash
   python ./.trellis/scripts/get_context.py --mode record
   ```
2. Archive tasks that are genuinely done:
   ```bash
   python ./.trellis/scripts/task.py archive <task-name>
   ```
   Judge by completed work/commit, not stale `task.json` status.
3. Add session:
   ```bash
   python ./.trellis/scripts/add_session.py \
     --title "Session Title" \
     --commit "hash1,hash2" \
     --summary "Brief summary"
   ```
   Or pass detailed notes with `--stdin`.

## Notes

`add_session.py` appends to journal, rotates over 2000 lines, updates indexes, and records branch context when available.

Do not run application commits; only Trellis metadata scripts may commit their own metadata if designed to do so.
