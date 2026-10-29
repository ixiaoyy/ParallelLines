# Chat branding

This layer reuses the forum's protected assets at `/logo-lines-mark.png` and
`/favicon.svg`; it does not copy, redraw or edit those assets. Model specs use the
same PNG through native `iconURL` and `preset.iconURL` fields.

`forum-theme.json` is an inline native `interface.theme` version 1 definition for
the pinned LibreChat release. The light palette comes from
`apps/web/src/shared/styles/tokens.scss` and `button-surfaces.scss`: primary
`#409EFF`, hover `#66B1FF`, white panels, `#F8FAFC` canvas, `#334155` titles,
`#475569` text and `#E2E8F0` borders. Dark mode retains the native dark surfaces
and applies the same forum blue controls; no new dark forum palette is invented.

Integration points:

1. In `deploy/librechat/config.cjs`, require `./sso/branding/forum-theme.json`
   and assign a cloned value to `config.interface.theme`.
2. In the mounted `sso/runtime/index.js`, require
   `/integration/sso/branding/shell-branding.cjs`. Call `applyShellBranding(indexHTML)`
   after reading the shell and before native theme/CSP processing.
3. Register `installBrandLogoRoute(app)` before the native static middleware.
   This replaces only the native fixed `assets/logo.svg` request with a fixed
   redirect to the public forum logo. Normal chat file/image ACLs are untouched.
4. The existing `./:/integration:ro` production bind already includes this
   directory for both the runtime helper and config generator. No extra public
   file mount or static directory is needed.

The HTML transform replaces shell favicon links and the initial document title
only. It never rewrites native conversation titles or compiled JavaScript.

Run `node --test deploy/librechat/sso/branding/branding.test.cjs` from the project
root. The parent integration also checks theme validity against the pinned
native theme token validator.
