# Product

<!-- impeccable:product-schema 1 -->

## Platform

Web application, designed for both desktop and mobile browsers.

## Users

ParallelLines serves Chinese-speaking people whose interests cross technical questions and everyday topics such as news, sports, reading, and personal experience.

- Visitors read and discover useful standalone discussions, including through search engines.
- Registered members publish topics, reply, search, follow people and boards, and use private social features.
- Moderators and administrators maintain boards, review content, manage users, inspect operations, and configure the site.
- Editors and automation operators publish recurring content through clearly disclosed managed accounts.

## Product Purpose

ParallelLines is a Chinese general-interest community where technical and everyday topics can coexist without sacrificing traceability or trust. Success means a visitor can find useful context before registering, a real member can participate with low friction, and an operator can keep the community healthy without simulating organic activity.

## Positioning

ParallelLines combines traceable forum discussion with ongoing editorial and creative columns on one community surface. Its practical differentiator is transparent operation: managed accounts are identified as official columns, automated accounts, creative characters, or a generic operator role instead of being presented as unrelated community members.

This is a product direction, not a claim of market uniqueness. No comparative market study has been supplied.

## Operating Context

- The product is a Vue frontend backed by a FastAPI API, with anonymous reading and indexing plus authenticated publishing, social, moderation, and administration flows.
- Background jobs and prepared operator accounts can support sourced editorial content and routine publishing.
- The repository's configured release path deploys pushes to `main`; API startup runs Alembic migrations before serving traffic.
- The primary audience and copy language are Chinese. Locale support must not be treated as evidence of complete multilingual coverage.

## Capabilities and Constraints

- Core capabilities include boards, topics, replies, search, profiles, following, private messaging, moderation, administration, analytics, and migration/import-export tools.
- `is_persona` means an account is managed by the site. `persona_kind` refines the public identity as `editorial`, `automation`, or `fictional`; it does not describe how an individual post was produced or reviewed.
- Content automation must preserve source traceability, public identity, permissions, idempotency, bounded retries, and observable failure states. It must not manufacture engagement or imply independent users.
- Public/private boundaries must remain consistent across API responses, rendered pages, caches, exports, and SEO structured data.
- Seeded accounts, fixture content, screenshots, and test data are implementation evidence, not proof of organic activity or user demand.

## Brand Commitments

- Name: ParallelLines / 平行线.
- Personality: calm, technical, trustworthy, bright, organized, and competent.
- Primary calls to action use solid Element UI blue `#409EFF` with white text. Brand gradients are decorative, and board tones remain separate from the global action color.
- The protected site logo and favicon paths remain the repository defaults unless a dedicated brand-change project explicitly replaces them.
- Avoid decorative SaaS dashboards, heavy purple gradients, glassmorphism, fake metrics, excessive rounding, and layouts that hide real forum content behind generic illustration or oversized hero treatments.

## Evidence on Hand

- Runnable Vue and FastAPI code, database migrations, generated API contracts, and automated tests demonstrate the implemented product surface.
- The repository contains prepared persona and publishing mechanisms that can support a transparent content cold start.
- No user-research corpus, retention data, organic participation benchmark, market comparison, testimonial set, or accessibility certification has been supplied. Do not invent these as product proof.

## Product Principles

1. Deliver useful content before chasing apparent volume.
2. Disclose operator ownership wherever identity affects trust.
3. Keep sources, claims, permissions, and data boundaries traceable.
4. Design for real participation rather than simulated activity or vanity metrics.
5. Make operational state, failures, and recovery paths observable.
6. Prefer existing product patterns and clear contracts over speculative capability.

## Accessibility & Inclusion

Aim for readable contrast, visible focus states, keyboard-reachable controls, non-hover and non-color-only cues, mobile-safe layouts, and reduced-motion-safe transitions. Chinese interface copy should stay concise and avoid internal implementation jargon unless the intended reader is an operator. These are working commitments, not a claim of formal accessibility certification.
