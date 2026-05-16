# Post-MVP Gap Audit

## High-impact gaps selected for this task

1. **No first-class auth UI**: backend auth exists and write APIs expect bearer tokens, but users cannot log in/register from the product UI.
2. **No current-user affordance**: topbar cannot show who is logged in or provide logout/profile navigation.
3. **No public user profile pages**: product design includes user center and authored topics; route/API are missing.
4. **Post actions are partly inert**: copy link, only-author filter, quote, copy code, and edit are either missing or placeholder UI.
5. **Smoke test is too narrow**: previous smoke covers publish/reply but not login UI, post controls, profile navigation, or broad button clicks.

## Deferred gaps after this task

- Rich Markdown editor toolbar and upload pipeline.
- Full preferences/settings page.
- Password reset/email verification.
- Board/admin configuration UI beyond moderation queue.
- Rate limiting and upload security hardening.
- Virtualized long topic stream and accessibility audit automation.
