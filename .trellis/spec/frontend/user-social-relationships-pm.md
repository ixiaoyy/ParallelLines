# Frontend User Relationships and Private Messages Contract

## Scenario: Profile relationship actions and private message inbox

### 1. Scope / Trigger

- Trigger: changing user profile relationship buttons, private-message creation, private-message inbox, or notification rendering for social events.
- Applies to `features/social/`, `pages/user/UserProfilePage.vue`, `pages/messages/`, `app/router.ts`, `AppShell.vue`, notification models, and shared query keys.

### 2. Signatures

Frontend APIs/composables:

| Function / Composable | Backend endpoint | Purpose |
|---|---|---|
| `fetchUserRelationship(username)` | `GET /users/{username}/relationship` | Load relationship state |
| `setUserRelationship(username, kind, active)` | `PUT/DELETE /users/{username}/{kind}` | Mutate follow/ignore/block |
| `fetchPrivateMessages()` | `GET /users/messages` | List PM inbox |
| `createPrivateMessage(payload)` | `POST /users/messages` | Create PM topic |
| `useUserRelationship(username, enabled)` | relationship endpoint | TanStack Query wrapper |
| `useUpdateUserRelationship(username)` | relationship endpoints | Mutation + cache invalidation |
| `usePrivateMessages()` | messages endpoint | Inbox query |
| `useCreatePrivateMessage()` | messages endpoint | Create PM mutation |

Routes:

- `/messages`: authenticated private-message inbox; unauthenticated state shows login CTA.
- `/u/:username`: shows relationship actions for other users.

### 3. Contracts

- Relationship server state stays in TanStack Query under `queryKeys.userRelationship(username)`.
- `/u/:username` must not show relationship controls for own profile.
- Unauthenticated relationship/PM actions route to `/auth?redirect=<current path>`.
- Blocking and ignoring update visible helper copy and invalidate profile/user topics/notifications.
- Private-message creation from profile sends `{ participant_usernames, title, raw_md }` and navigates to the returned topic route.
- `/messages` lists only server-returned PM topics; no fixture fallback.
- Notification UI recognizes `user_new_topic` and `private_message` types and links PM notifications to the private topic.

### 4. Validation & Error Matrix

| Case | Expected behavior |
|---|---|
| Own profile | No follow/ignore/block/PM controls |
| Missing token on social action | Redirect to auth with current path |
| `relationship_blocked` | Shows block-boundary copy |
| `private_message_blocked` | Shows PM block-boundary copy |
| Inbox unauthenticated | Login CTA; no PM query is useful to user |
| Inbox empty | Honest empty state explains profile-page PM entry point |
| PM create success | Navigate to returned topic detail |

### 5. Good/Base/Bad Cases

- Good: profile hero displays relationship boundary summary and keeps actions grouped away from public stats.
- Good: PM inbox uses the forum visual language but labels private access explicitly.
- Base: user creates PM from another user's profile and lands in topic detail.
- Bad: decoding JWT or storing relationship state in Pinia/localStorage instead of Query.

### 6. Tests Required

- `pnpm --dir apps/web typecheck`
- `pnpm --dir apps/web lint`
- `pnpm --dir apps/web build`
- Manual smoke: authenticated profile follow/ignore/block buttons and PM creation.
- Manual smoke: `/messages` unauthenticated state and authenticated inbox.
