# API Keys and Webhooks UI Contract

## Scenario: Admin integration management panel

### 1. Scope / Trigger

- Trigger: adding or changing admin UI for API keys, webhook endpoints, webhook delivery logs,
  integration scopes, event options, or one-time secret/token reveal behavior.
- Applies to `features/admin/model.ts`, `features/admin/api.ts`, `features/admin/queries.ts`,
  `features/admin/components/AdminIntegrationsPanel.vue`, its SCSS, and
  `pages/admin/AdminDashboardPage.vue`.

### 2. Signatures

DTO and option types:

- `ApiKeyResponse`, `ApiKeyCreateRequest`, `ApiKeyCreateResponse`
- `WebhookEndpointResponse`, `WebhookEndpointCreateRequest`, `WebhookEndpointCreateResponse`
- `WebhookDeliveryResponse`
- `API_KEY_SCOPE_OPTIONS`
- `WEBHOOK_EVENT_OPTIONS`

Frontend API functions:

| Function | Backend endpoint | Return |
|---|---|---|
| `fetchAdminApiKeys()` | `GET /api/v1/admin/api-keys` | `ApiKeyResponse[]` |
| `createAdminApiKey(payload)` | `POST /api/v1/admin/api-keys` | `ApiKeyCreateResponse` |
| `disableAdminApiKey(keyId)` | `POST /api/v1/admin/api-keys/{id}/disable` | `ApiKeyResponse` |
| `fetchAdminWebhooks()` | `GET /api/v1/admin/webhooks` | `WebhookEndpointResponse[]` |
| `createAdminWebhook(payload)` | `POST /api/v1/admin/webhooks` | `WebhookEndpointCreateResponse` |
| `disableAdminWebhook(webhookId)` | `POST /api/v1/admin/webhooks/{id}/disable` | `WebhookEndpointResponse` |
| `fetchAdminWebhookDeliveries(limit)` | `GET /api/v1/admin/webhook-deliveries?limit=` | `WebhookDeliveryResponse[]` |

Query composables:

- `useAdminApiKeys()`
- `useCreateAdminApiKey()`
- `useDisableAdminApiKey()`
- `useAdminWebhooks()`
- `useCreateAdminWebhook()`
- `useDisableAdminWebhook()`
- `useAdminWebhookDeliveries()`

Query keys:

- `queryKeys.adminApiKeys`
- `queryKeys.adminWebhooks`
- `queryKeys.adminWebhookDeliveries`

### 3. Contracts

- Integration management lives under the existing `/admin` permission shell. Do not add a separate
  public route until backend has public API docs and per-user token requirements.
- DTOs remain snake_case at the API boundary; components may render labels but must not reshape
  persisted payloads ad hoc.
- Token and webhook signing secret are displayed only from create mutation responses. List views
  show `token_prefix`, endpoint URL, events, status, and delivery summaries only.
- Scope/event chips must mirror backend allowed values. If backend constants change, update
  `API_KEY_SCOPE_OPTIONS`, `WEBHOOK_EVENT_OPTIONS`, and the backend spec in the same task.
- Empty key scope selection is allowed so admins can create non-authorizing keys for smoke testing;
  UI must show “无 scope” instead of hiding the row.
- Disable buttons are disabled for already disabled keys or inactive webhooks. Mutations invalidate
  the specific integration query key and `queryKeys.adminRoot`.
- Delivery log UI is read-only and should show event type, status, endpoint, attempt count, and the
  latest error/status code without exposing secrets or payload bodies.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Admin creates key without name | Component no-ops client-side; backend remains source of truth. |
| Admin creates key with empty scopes | Row is shown with “无 scope”; token is revealed once. |
| Create key succeeds | Token reveal region shows plaintext token; next refetch only shows prefix. |
| Create webhook succeeds | Signing secret reveal region shows secret; list does not show secret. |
| Disable key/webhook pending | Button disabled to avoid duplicate mutation. |
| Delivery list empty | Shows localized empty state, not a blank card. |
| Query fails with admin auth issue | Existing admin dashboard permission/error behavior remains source of truth. |

### 5. Good/Base/Bad Cases

- Good: admin opens `/admin`, sees the integration panel, creates a read-only key, copies the
  one-time token, and later disables it from the list.
- Good: admin creates a webhook subscribed to `topic.created`, then watches recent delivery status
  after a topic event.
- Base: panel renders on mobile as stacked forms/lists with long token/URL text wrapping.
- Bad: storing the plaintext token or webhook secret in Pinia/localStorage.
- Bad: importing `apiPost` directly inside the Vue component instead of using
  `features/admin/api.ts` and query composables.

### 6. Tests Required

- Downgraded roadmap scope: run `npm run typecheck` and `npm run lint` in `apps/web`.
- Focused manual/browser smoke when a local dev server is already running:
  - admin visits `/admin`;
  - creates API key and sees one-time token;
  - creates webhook and sees one-time secret;
  - disables each row and sees disabled/inactive state.
- Add component or e2e tests only when explicitly requested or when the panel gains destructive
  bulk actions, per-user token management, or routing changes.

### 7. Wrong vs Correct

#### Wrong

```vue
<script setup lang="ts">
import { apiPost } from "@/shared/api/client";

async function createKey() {
  await apiPost("/admin/api-keys", form);
}
</script>
```

#### Correct

```vue
<script setup lang="ts">
const createApiKeyMutation = useCreateAdminApiKey();

function createApiKey() {
  createApiKeyMutation.mutate({ name, scopes, note });
}
</script>
```
