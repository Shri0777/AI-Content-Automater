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
| `checks.py` | `check_credential`: "test connection". Makes one small request with the key and saves `verified`, `invalid` or `unverified` with a reason. |
| `models.py` | `ProviderCredential` (with `status`, `last_checked_at`, `last_error`), `KIND_CHOICES`, `ADAPTERS_BY_KIND` (which providers each kind may use) and `KEY_REQUIRED_ADAPTERS`. |
| `serializers.py` | What goes in and out of the API. `api_key` is write-only: it is accepted but never sent back. Checks the model name (only safe characters), the custom address (https only) and that providers needing a key get one. |
| `services.py` | `save_credential` (replaces an older one of the same kind and clears its last check), `get_credential`, `require_credential`, `read_api_key`, `record_check`, `reject_credential` (marks a key invalid and notifies the user once), `delete_credential`. |
| `urls.py` | `/api/v1/credentials/`, `<id>/` and `<id>/test/`. |
| `views.py` | Thin API classes: list, save, delete and test (at most 10 tests a minute, because each one calls the provider). |

**How a key is kept safe:**
1. `save_credential()` encrypts the key with `encrypt_text()` (`core/crypto.py`).
2. Only the last 4 characters are kept in plain text (`key_hint`), so users
   can tell their keys apart.
3. Only the code that calls the provider uses `read_api_key()` to get the
   plain key back.

**Providers you can use:**

| Kind | `adapter` | `model_name` example | `base_url` |
|---|---|---|---|
| text | `anthropic` | `claude-opus-5-5` | optional |
| text | `openai_compatible` | `gpt-4o-mini`, `llama3.2` | the service's address, for example `https://openrouter.ai/api/v1`; empty means OpenAI |
| image | `openai_compatible` | `gpt-image-1` | as above |
| image | `nvidia_flux` | `black-forest-labs/flux.1-dev` | optional |
| image | `fal` | `fal-ai/flux/schnell` | optional |
| any | `demo` | (none) | (none), only while `DEMO_MODE` is on |

**Test connection** (`POST /api/v1/credentials/<id>/test/`): text keys and
OpenAI-compatible image keys are checked with free requests (looking up the
model or listing models, or one tiny chat message). NVIDIA and fal have no
free check, so testing them makes one small image, which may cost a
fraction of a cent.

**Status:** `unverified` (not checked, or the provider failed for another
reason, see `last_error`), `verified`, or `invalid` (the provider refused the
key; this is also set when a key is refused while making a post).

**Honesty note:** these providers are tested against stub servers that
answer in each provider's documented format. They have not yet been run
with real keys, so they are **unverified-live**.
