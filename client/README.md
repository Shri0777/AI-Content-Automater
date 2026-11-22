# Frontend (Next.js)

The web app for AI Content Automator: a landing page, sign-in, and the
signed-in app (overview, posts, plans, social accounts, AI keys,
notifications, settings). All data comes from the Django API; this app has no
server-side data of its own.

## Run it

The API must be running first (see the main [README](../README.md)).

```bash
cd client
npm install
npm run dev            # http://localhost:3000 (or: npm run build && npm run start)
```

The API address defaults to `http://localhost:8000/api/v1`. To change it,
create `client/.env.local` (not committed):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

The API must allow this app's address: `CORS_ALLOWED_ORIGINS` and
`FRONTEND_URL` in the main `.env` (both default to `http://localhost:3000`).

## How sign-in works

- The access token lives only in memory (`src/lib/api.ts`), never in
  localStorage, so a script injected into the page cannot read a stored token.
- The refresh token is an httpOnly cookie set by the API on `/api/v1/auth/`.
  Every page load calls `/auth/refresh/` (with the `X-Requested-By` header the
  API requires) to get a new access token. A request that gets 401 refreshes
  once and retries.
- Each refresh swaps the cookie for a new one. If the reply is lost (a reload
  mid-request) or two tabs refresh together, the API gives the same new
  tokens again for 30 seconds instead of logging you out
  (`accounts/refresh_replay.py`).

## Where things are

| Path | What it is |
| --- | --- |
| `src/app/page.tsx` | Landing page: the dithered hero and how a post is made. |
| `src/app/(auth)/` | Sign in, create account (invite code, then recovery codes), reset password. |
| `src/app/app/layout.tsx` | The signed-in shell: sign-in guard, sidebar, phone menu, badge counts. |
| `src/app/app/**/page.tsx` | One file per screen. |
| `src/app/social/link-result/` | Where X, LinkedIn or Facebook send you back after connecting. |
| `src/components/DitherField.tsx` | The animated dither (canvas). Pauses off screen; still under reduced motion. |
| `src/components/ui.tsx` | Buttons, fields, errors, headers, status badges. |
| `src/lib/api.ts` | Every API call, typed (`src/lib/types.ts`). |
| `src/lib/session.tsx` | Who is signed in. |

Design notes and the reference theme: [design/frontend-theme.md](../design/frontend-theme.md).

## Checks

```bash
npx tsc --noEmit && npm run lint && npm run build

# Browser tests (Playwright, Firefox). The API must be running with a worker
# (docker compose up -d); Playwright starts this app itself.
E2E_MANAGE="docker compose exec -T web python manage.py" npm run test:e2e
```

`e2e/public.spec.ts` checks every public page at 390px and 1280px wide (no
sideways scrolling, no console errors or warnings) and reduced motion.
`e2e/journey.spec.ts` follows a new user in demo mode: sign up with an invite
code, save demo keys, link a demo account, save an X developer app, use the
skip link, create a plan, make a post, edit and approve it, see it posted,
reload, check every app page on a phone screen and the phone menu, and sign
out. CI runs both against the Docker Compose stack (`browser-tests` job).

To use a Firefox you already have instead of downloading Playwright's, set
`E2E_FIREFOX_PATH` to its executable.
