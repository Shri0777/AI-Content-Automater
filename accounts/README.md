# accounts: users, registration and login

People log in with their email address. New accounts need an invite code
while `REGISTRATION_MODE` is `invite` (the default).

| File | What it does |
|---|---|
| `admin.py` | Shows users on the admin site (never their passwords). |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `User` (email login, timezone, tier) and `InviteCode` (single use, stored only as a fingerprint). |
| `serializers.py` | What goes in and out of the API: registration, login, the user's details, `/me/summary`. |
| `services.py` | The real work: invite codes, `register_user`, `log_in`, `refresh_login`, `log_out`. |
| `urls.py` | `/api/v1/auth/register/`, `login/`, `refresh/`, `logout/`, `/api/v1/me/` and `/api/v1/me/summary/`. |
| `views.py` | Thin API classes. They also set and clear the refresh-token cookie. |
| `management/commands/create_invite_codes.py` | `python manage.py create_invite_codes 5` prints five new invite codes. |

**Main flow (login):** `LoginView.post()` checks the input with
`LoginSerializer`, calls `services.log_in()`, sends the access token in the
body and puts the refresh token in an httpOnly cookie with
`set_refresh_cookie()`.

**Why a cookie?** Browser scripts cannot read an httpOnly cookie, so a bug in
the frontend cannot leak the long-lived refresh token (ADR-009).
