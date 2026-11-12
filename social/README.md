# social: linked social media accounts

Posts are published to the accounts a user links here. Today only the fake
**demo network** exists (demo mode); Buffer, LinkedIn, X and Meta arrive in
Phase 4.

| File | What it does |
|---|---|
| `admin.py` | Shows linked accounts on the admin site. Tokens are hidden. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `SocialAccount`, `PLATFORM_CHOICES` and `CAPTION_LIMITS` (the longest caption each platform accepts). |
| `publishers.py` | `Publisher`, the base class every platform's publisher follows (the adapter pattern). |
| `serializers.py` | What an account looks like in the API (never its token). |
| `services.py` | `link_demo_account` (checks the 5-account limit), `get_accounts`, `unlink_account`, `count_accounts_needing_attention` and `get_publisher(platform)`. |
| `urls.py` | `/api/v1/social/accounts/`, `accounts/<id>/` and `link/demo/`. |
| `views.py` | Thin API classes: list, unlink, link a demo account. |

**Adding a platform later:** write a `Publisher` subclass with a `publish()`
method, add the platform to `PLATFORM_CHOICES` and `CAPTION_LIMITS`, and
return the new class from `get_publisher()`. Nothing else changes.
