# Subscriptions and Payments UI Contract

## Scenario: Billing page and admin payment event tracking

### 1. Scope / Trigger

- Trigger: changing billing routes, subscription plan display, current entitlement display, or admin
  payment event list.
- Applies to `features/payments/`, `pages/billing/`, `AdminDashboardPage.vue`, `AppShell.vue`, and
  `shared/api/queryKeys.ts`.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Purpose |
|---|---|
| `fetchSubscriptionPlans()` | Public plan list |
| `fetchMySubscription()` | Current user status/entitlements |
| `fetchAdminPaymentEvents()` | Admin billing event list |
| `useSubscriptionPlans()` | Query wrapper |
| `useMySubscription(enabled)` | Auth-gated query wrapper |
| `useAdminPaymentEvents(enabled)` | Admin dashboard event query |

Routes/navigation:

- `/billing` → `BillingPage.vue`
- App shell authenticated nav shows `会员`.

### 3. Contracts

- Billing UI is read-only until a real hosted checkout flow is added; do not simulate paid state on
  the client.
- Subscription status and entitlements come from `/subscriptions/me`.
- Admin payment events are operational telemetry only; they do not expose raw webhook payloads.
- Authenticated pages show login CTA when no current user exists.
- Payment copy must avoid claiming real charges are supported unless a provider checkout flow is
  implemented.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Visitor opens `/billing` | Login CTA for current subscription |
| Plans endpoint returns default plan | Plan cards show price, interval, and entitlements |
| Active subscription | Current card shows status and entitlement chips |
| Expired/no subscription | Current card shows no active entitlement |
| Admin events empty | Admin panel shows honest empty state |
| Admin events fail | Admin panel shows visible error state |

### 5. Good/Base/Bad Cases

- Good: billing page explains signed webhook boundary and shows backend-returned status.
- Base: admin sees recent webhook events and can investigate failed payments.
- Bad: setting entitlement chips from URL query parameters after a payment redirect.
- Bad: `window.localStorage.paid=true` or any local-only paid access source of truth.

### 6. Tests Required

- Default roadmap scope: `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web lint`.
- OpenAPI changes must also pass `pnpm --dir apps/web openapi:check`.
- Full checkout/browser tests are deferred until real provider checkout is introduced.

### 7. Wrong vs Correct

#### Wrong

```ts
localStorage.setItem("paid_member", "true");
```

#### Correct

```ts
const subscription = await fetchMySubscription();
const entitlements = subscription.entitlements;
```

The backend webhook processor is the only source of paid entitlement truth.
