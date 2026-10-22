# Frontend Architecture

## Purpose

`frontend` is a Django presentation application. It owns the authenticated application shell, reusable display components, dashboard, publishing overview, help page, design tokens, CSS, and small browser-only enhancements. It does not own domain state transitions, credential handling, research collection, or external publishing.

## Route Ownership

| Route | Owner | Responsibility |
|---|---|---|
| `/` | `frontend:dashboard` | Authenticated, owner-scoped summary only. |
| `/publishing/` | `frontend:publishing` | Read-only history from `ContentPublication`; publication remains on content detail. |
| `/help/` | `frontend:help` | Static guide to implemented safeguards. |
| `/content/` | `content` | Content CRUD, versions, review, approval, publishing preparation, and Buffer actions. |
| `/research/` | `research` | Profile, requests, execution, source selection, and generation handoff. |
| `/ai/` | `ai_providers` | Provider configuration, encrypted credential handling, validation, and HTMX status refresh. |
| `/auth/` | `users` | Registration, session authentication, logout, and password reset. |

The project root includes `frontend.urls`; domain URL names and state-changing endpoints are unchanged.

## Templates And Components

`frontend/templates/frontend/base.html` supplies the authenticated shell. Existing content, research, and provider templates inherit it through their former base templates, avoiding duplicated navigation. `public_base.html` supplies the matching unauthenticated authentication surface.

Reusable components are deliberately small: sidebar, topbar, message container, empty state, and status badge. Status labels are rendered from existing model values, never client-generated lifecycle data.

## Data And Security Boundaries

The dashboard reads only querysets filtered to `request.user`. The publishing overview reads only `ContentPublication.user=request.user`; it does not call Buffer or infer a successful external outcome. Buffer configuration status comes from the existing service without a live validation call. Existing content, research, provider, and publishing views remain the server-side authorization boundary and retain CSRF-protected POST actions.

Provider credentials are never inserted into dashboard data, data attributes, or JavaScript. Provider templates continue to use the existing masking and encrypted storage behavior.

## Static Assets

The CSS is split by responsibility under `frontend/static/frontend/css/`: tokens, reset/base, layout, components, forms, dashboard, and responsive overrides. `app.js` controls only the mobile navigation drawer. `interactions.js` disables the submitted button to reduce accidental duplicate submissions and honors existing `data-confirm` controls. It stores no domain data or credentials.

## Integration Notes

The provider dashboard retains the existing HTMX connection-status request. Other lists use ordinary GET and POST forms as graceful server-rendered fallbacks because no new backend partial contract was introduced. The content list's search, lifecycle filter, sorting, and pagination stay owner-scoped on the server.
