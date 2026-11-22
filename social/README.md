# social: linked social media accounts

Posts are published to the accounts a user links here. Each platform has one
publisher class (the adapter pattern), and the rest of the code only talks to
the base class in `publishers.py`.

| Platform | How a user links it | Token life |
|---|---|---|
| Demo network | One click (demo mode only) | No token |
| Buffer | Pastes a personal API key; every channel is found and linked | Does not expire |
| X | OAuth 2.0 with PKCE | 2 hours; refreshed (each refresh token works once) |
| LinkedIn | OAuth 2.0 (member profile) | 60 days; no refresh for self-serve apps, so the user is warned a week ahead |
| Facebook Page | Facebook Login; every Page the user may post to is linked | Page tokens have no expiry date |

Instagram is not linked yet: Meta downloads Instagram images from a public
address and wants JPEG files. Direct platforms also need a developer app
registered with the platform. Each user saves their own app's id and secret
(`PUT /api/v1/social/apps/<platform>/`, secret stored encrypted); the
operator's app in `.env` (`X_CLIENT_ID` and so on) is only a fallback. Until
one exists, `GET /api/v1/social/platforms/` reports the platform as not
ready, and gives the `callback_url` to register in the app. Every adapter is checked against a stub server that answers in
the platform's documented format; none has been run against the live
platform yet.

| File | What it does |
|---|---|
| `admin.py` | Shows linked accounts and developer apps on the admin site. Tokens and secrets are hidden. |
| `apps.py` | Tells Django this app exists. |
| `buffer_publisher.py` | `BufferPublisher`: finds a Buffer key's channels and posts through Buffer's GraphQL API, giving it the poster's public link. |
| `facebook_publisher.py` | `FacebookPublisher`: Facebook Login, long-lived token swap, and photo posts to Pages. |
| `linkedin_publisher.py` | `LinkedInPublisher`: LinkedIn login, then image upload and post creation through LinkedIn's REST API. |
| `models.py` | `SocialAccount` (encrypted tokens, expiry, status), `LinkAttempt` (one waiting OAuth link, stored as a fingerprint of its state) and `PlatformApp` (a user's own developer app, secret encrypted). |
| `oauth.py` | `start_link` and `handle_callback`: the OAuth link flow with single-use state and PKCE. |
| `platform_apps.py` | Save, list and remove a user's developer apps; `app_keys_for` picks the user's app, else the server's. |
| `platforms.py` | `get_publisher`, `publisher_for_account` (acts as the owner's app), `caption_limit_for` and `is_ready_to_link` (per user): the facts about each platform, in one place. |
| `publishers.py` | `Publisher`, the base class every platform follows; `PostContent`; and small helpers to read tokens and answers. |
| `serializers.py` | What an account looks like in the API (never its tokens), plus the link request and answer shapes. |
| `services.py` | `save_found_accounts` (checks the account limit), `link_buffer_accounts`, `link_demo_account`, `get_accounts`, `unlink_account` (revokes at the platform first) and `count_accounts_needing_attention`. |
| `tasks.py` | `refresh_social_tokens_task`: every 30 minutes, refreshes tokens that end soon and warns about ones that cannot be refreshed. |
| `tokens.py` | `store_tokens`, `refresh_account` (locks the account's row so a once-only refresh token is never used twice), `mark_needs_reauth` and `refresh_expiring_accounts`. |
| `urls.py` | `/api/v1/social/platforms/`, `apps/` and `apps/<platform>/` (your developer apps), `accounts/`, `accounts/<id>/`, `link/demo/`, `buffer/channels/` (list a key's channels to choose from), `link/buffer/`, `link/<platform>/start/` and `link/<platform>/callback/`. |
| `views.py` | Thin API classes. The callback needs no login: the user arrives from the platform, and the single-use state identifies the attempt. |
| `x_publisher.py` | `XPublisher`: X's OAuth 2.0 with PKCE, one-request image upload, posting, refresh and revoke. |

**Adding a platform:** write a `Publisher` subclass (`publish()`, and for
OAuth `authorization_url()` and `finish_link()`), add it to
`PLATFORM_CHOICES` in `models.py` and `PUBLISHER_CLASSES` in `platforms.py`,
and give its API address in `config/settings/social.py`.
