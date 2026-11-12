# credentials: the user's own AI and news keys

The app is free because each user brings their own provider keys. A user
keeps at most one credential of each kind:

| Kind | Used for |
|---|---|
| `text` | Writing captions and image prompts, and reviewing posts. |
| `image` | Making the poster artwork. |
| `news` | An optional extra news source. |

| File | What it does |
|---|---|
| `admin.py` | Shows credentials on the admin site. The encrypted key is hidden. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `ProviderCredential`, `KIND_CHOICES` and `ADAPTERS_BY_KIND` (which providers each kind may use). |
| `serializers.py` | What goes in and out of the API. `api_key` is write-only: it is accepted but never sent back. |
| `services.py` | `save_credential` (replaces an older one of the same kind), `get_credential`, `require_credential`, `read_api_key`, `delete_credential`. |
| `urls.py` | `/api/v1/credentials/` and `/api/v1/credentials/<id>/`. |
| `views.py` | Thin API classes: list, save and delete. |

**How a key is kept safe:**
1. `save_credential()` encrypts the key with `encrypt_text()` (`core/crypto.py`).
2. Only the last 4 characters are kept in plain text (`key_hint`), so users
   can tell their keys apart.
3. Only the code that calls the provider uses `read_api_key()` to get the
   plain key back.

**Demo mode:** the only provider today is `demo`, the built-in fake (see
`demo/`). It is accepted only while `DEMO_MODE` is on. Real providers arrive
in Phase 3.
