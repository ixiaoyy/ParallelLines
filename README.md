# 平行线

面向中文技术社区的 Discourse-inspired 论坛项目，采用 Vue 3 + FastAPI 实现。代码仓库和包名暂沿用 `ParallelLines/parallellines`。

## Design Artifacts

- Product/architecture design: `.trellis/spec/product/discourse-inspired-parallellines-design.md`
- Trellis task plan: `.trellis/spec/product/trellis-task-plan.md`
- Trellis task tree: `.trellis/tasks/05-14-parallellines-mvp`

## Stack Target

- Frontend: Vue 3, Vite, TypeScript, Ant Design Vue, Vue Router, Pinia, TanStack Query
- Backend: FastAPI, SQLAlchemy 2.x async, Alembic, MySQL/PostgreSQL, Redis
- Palette: `#F8F9FA`, `#3B82F6`, `#10B981`, `#111827`, `#4B5563`, `#1E1E1E`

## Trellis

```powershell
python .trellis\scripts\get_context.py
python .trellis\scripts\task.py list
python .trellis\scripts\task.py start 05-14-parallellines-mvp
```
