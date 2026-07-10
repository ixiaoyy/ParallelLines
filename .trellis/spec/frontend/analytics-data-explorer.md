# Analytics and Data Explorer UI Contract

## Scenario: Admin dashboard analytics panel and CSV export

### 1. Scope / Trigger

- Trigger: changing the analytics dashboard panel, Data Explorer report selection, range filters,
  or CSV export UI.
- Applies to `features/analytics/`, `AdminDashboardPage.vue`, `shared/api/queryKeys.ts`, and
  generated OpenAPI DTO usage.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Purpose |
|---|---|
| `fetchAnalyticsOverview(range)` | Load totals, series, and top lists |
| `fetchDataExplorerReports()` | Load preset report metadata |
| `runDataExplorerReport(reportId, range)` | Load report rows |
| `exportDataExplorerReport(reportId, range)` | Fetch CSV blob with auth headers |
| `useAnalyticsOverview(range)` | Query wrapper |
| `useDataExplorerReports()` | Query wrapper |
| `useDataExplorerReport(reportId, range)` | Query wrapper |
| `useExportDataExplorerReport()` | CSV export mutation |

Query keys:

- `queryKeys.adminAnalytics(startDate, endDate)`
- `queryKeys.adminAnalyticsReports`
- `queryKeys.adminAnalyticsReport(reportId, startDate, endDate)`

### 3. Contracts

- Analytics DTOs must use generated OpenAPI component types.
- Range state stays in component refs and is part of query keys.
- The user-growth panel reads `totals.registrations` and `series[].registrations` from the same
  overview response, shows range total plus daily average/trend, and visibly states `不含马甲账号`.
  Persona filtering is a backend contract; the frontend must not recreate it from usernames.
- CSV export must use `fetch(getApiUrl(...), { headers: createApiHeaders() })`; `window.open`
  cannot be used because it omits bearer auth headers.
- Data Explorer UI renders only backend-supplied preset report columns/rows.
- Report table cells render escaped text via interpolation; no `v-html`.
- Admin dashboard permission state remains owned by `AdminDashboardPage.vue`; the analytics panel
  assumes it is mounted only for admins but still handles API errors visibly.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Overview loading | Shows calculation state |
| Backend returns 403/error | Shows analytics unavailable/error copy |
| No report selected yet | Selects first preset report when available |
| CSV export pending | Export button disabled |
| Empty report rows | Table renders headers without crashing |
| Date range changes | Overview/report queries refetch via range-aware keys |
| No real-user registrations in range | Growth summary shows zero and the chart remains readable. |

### 5. Good/Base/Bad Cases

- Good: admin changes date range and both trend bars and report rows refetch.
- Good: user-growth total, average, chart, and accessibility label all reflect the selected range
  and identify that persona accounts are excluded.
- Base: admin selects `daily_activity`, exports CSV, and backend audit log records the export.
- Bad: hardcoding report rows in the frontend or downloading CSV via unauthenticated `window.open`.
- Bad: counting or subtracting persona usernames in the component; only aggregated backend values are available.
- Bad: accepting arbitrary SQL text in the UI before backend supports a safe sandbox.

### 6. Tests Required

- Default roadmap scope: `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web lint`.
- OpenAPI changes must also pass `pnpm --dir apps/web openapi:check`.
- Full chart/e2e testing deferred unless requested or release readiness requires it.

### 7. Wrong vs Correct

#### Wrong

```ts
window.open(`${API_BASE_URL}/admin/analytics/reports/${id}/export.csv`);
```

#### Correct

```ts
const response = await fetch(getApiUrl(path), { headers: createApiHeaders() });
const blob = await response.blob();
```

Authenticated blob fetch preserves backend permission checks and audit behavior.
