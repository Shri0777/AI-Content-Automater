# Code Readability Standard: "a beginner can read every file"

This is a **top-level requirement** of V4, equal in weight to the features. It applies to every file we write, including tests and scripts.
Related: [system-design.md](system-design.md), [decisions.md](decisions.md) (ADR-013), [test-strategy.md](test-strategy.md).

---

## 1. The goal and the test
**Simple code, not fewer features.** No feature is cut or weakened for readability. Complexity is moved into small, well-named functions and plain data, never into clever syntax.

**The Beginner Test.** Someone who knows basic Python (variables, functions, `if`, `for`, simple classes) and has read `docs/CODE-TOUR.md` can read any file from top to bottom in one sitting, without looking up unfamiliar syntax or patterns, and can say what it does. If a file fails this, we **rewrite the code**. We do not just add a comment to excuse it.

## 2. The Beginner Subset (what we write)
- Variables, functions, `if` / `elif` / `else`, `for`, `while`, `return`
- Lists, dicts, tuples, sets
- f-strings
- Simple classes: Django models, serializers, API view classes, and **one level** of inheritance (a base class plus one subclass per provider)
- `try` / `except` with **specific** exception types
- `with` for transactions and files
- List comprehensions with **one** `for` and at most one `if`
- Simple type hints on function signatures (`str`, `int`, `bool`, `list`, `dict`, `str | None`)
- Django and Celery's own decorators (`@transaction.atomic`, `@shared_task`) and nothing we invent

## 3. What we avoid
| Avoid | Write this instead |
|---|---|
| `async` / `await` | Normal functions. Concurrency comes from Celery workers, not from our code. |
| Metaclasses, multiple inheritance, mixins | One base class, one level of subclasses |
| Our own decorators, closures, nested functions | Plain top-level functions with clear names |
| `*args` / `**kwargs` in our code | Named parameters |
| `lambda` | A short named `def` |
| Generators and `yield` | Build a list and return it |
| Nested or multi-`for` comprehensions | An ordinary `for` loop |
| Chained ternaries, the walrus operator | `if` statements and early returns |
| `functools`, `itertools`, `inspect`, `importlib`, dynamic `getattr` / `setattr` | Explicit code |
| Django signals | An explicit function call at the place it happens |
| `Generic`, `TypeVar`, `Protocol`, `ABC` | A plain base class whose methods raise `NotImplementedError` with a helpful message |
| DRF `ViewSet`, routers, mixins | Explicit `APIView` classes with `get` / `post` methods (ADR-013) |
| Raw SQL | Django ORM. The **named exceptions** below are the only special cases. |
| Global mutable state | Pass values as parameters |

**Named exceptions** (each lives in one clearly labelled function with a "Why this is here" comment):
1. The dispatcher's `select_for_update(skip_locked=True)`: lets several dispatchers share work without double-claiming a slot.
2. The quota counter's conditional `update(used=F("used") + 1)`: makes "use the last allowed unit" safe when two requests arrive together.
3. The encryption helpers wrap `cryptography`'s `Fernet`. Callers only ever see `encrypt_text(text)` and `decrypt_text(token)`.

## 4. Shape rules (enforced by tooling)
| Rule | Limit |
|---|---|
| File length | Aim for 200 lines or fewer. Hard cap 250. |
| Function length | Aim for 20 lines or fewer. Hard cap 30. |
| Function complexity (`ruff` C901) | 7 or lower |
| Function parameters | 5 or fewer. More than that means pass one small object. |
| Nesting depth | 3 levels or fewer. Use early returns. |
| Line length | 88 characters |
| One job per function | If its name needs "and", split it. |

## 5. Naming
- Full English words. No abbreviations except universal ones (`id`, `url`).
- Functions are verbs (`claim_due_slots`, `send_notification`). Data is nouns (`due_slots`, `review_result`).
- Booleans read as questions (`is_expired`, `has_quota_left`).
- Status values are readable words (`awaiting_approval`, not `AA` or `3`).

## 6. Documentation inside the code
- **Every module** starts with a docstring: what it does, why it exists, and where it fits in the flow.
- **Every function and class** has a one-line docstring.
- **Comments explain why, not what.** `# Skip posts whose window has passed so we never post stale news` is good. `# loop over posts` is noise.
- **Every app has a `README.md`** (about 10 lines): purpose, files, the main flow.
- **`docs/CODE-TOUR.md`** (written in Phase 1, extended at the end of every phase): reading order, glossary, the repeated patterns explained once, and one request followed end to end through the code.

## 7. Predictable layout and one-way flow
Every app has the same file names, so a beginner always knows where to look:
```
models.py        database tables (Django models)
serializers.py   what goes in and out of the API
views.py         thin API classes: check input, call a service, return the result
urls.py          routes
services.py      plain functions that do the real work
tasks.py         Celery wrappers (10 lines or fewer each) that call services
tests/           tests named as full sentences
README.md        10-line orientation
```
**The flow is one-way: views call services, services call models and adapters, tasks call services.** No business logic lives in views, serializers or tasks.

## 8. The only patterns we use (each explained once in the code tour)
1. **Service function**: plain function, plain arguments, returns plain data.
2. **Adapter**: one base class (methods raise `NotImplementedError`) plus one subclass per provider with identical method names. Used for news sources, image models, social platforms.
3. **Status table**: a dict `ALLOWED_TRANSITIONS` plus a `change_status(post, new_status)` function. No state-machine library.
4. **Task wrapper**: a Celery task that loads an object by ID and calls one service function.
5. **Quota check**: `check_quota(user, resource)` before the work, `use_quota(user, resource)` when it counts.
6. **Notification helper**: `notify(user, kind, ...)`.
7. **Plain exceptions**: our own `class QuotaExceeded(Exception)` and friends, with messages a user can read.
8. **Wrapper for each library**: each external library (LiteLLM, Pillow, trafilatura, cryptography) is used in exactly one file behind a tiny function with an obvious name (`ask_text_model`, `draw_headline`, `extract_article_text`, `encrypt_text`). The rest of the code never sees the library.

If a new pattern seems necessary, we first try to avoid it. If it is truly needed, it is added to this list and to the code tour in the same change.

## 9. Errors
- Raise our own simple exceptions. Catch **specific** exceptions only. No bare `except:`.
- Messages are plain English sentences a user could read: "You have reached your limit of 3 active plans."
- A failure in a stage is recorded on the `GenerationStep` and shown through the post's `status` and `skip_reason`.

## 10. Tests are documentation
- Test names are full sentences: `test_slot_over_quota_is_skipped_with_reason`.
- Each test has three visible parts (set up, do, check) separated by blank lines.
- One behaviour per test. No clever fixtures. Tables of cases are written as a plain list with a `for` loop or a clearly named `parametrize`.
- Where earlier designs used property-based or mutation testing, we use **explicit, named cases** instead (for example named daylight-saving dates), which a beginner can read and extend.

## 11. Enforcement (so the standard cannot quietly erode)
1. **Ruff configuration** in `pyproject.toml`: complexity, branch and statement limits, argument limit, docstring rules, line length, and banned imports (`asyncio`, `functools`, `itertools`, `inspect`, `importlib`). Exact rule names are confirmed against the installed Ruff version at setup.
2. **`scripts/check_readability.py`**: a small, itself-readable script that fails CI if a file is over 250 lines, a module lacks a docstring, or the code contains `async def`, `lambda`, `yield`, or `*args` / `**kwargs` outside an allow-list.
3. **Fresh-eyes review at the end of every phase**: a reviewer with no prior context reads each new file once and lists anything they could not follow in a single pass. Items are fixed by simplifying code. The phase is not done until this list is empty.
4. **Code tour kept current**: a phase is not done if the tour does not match the code.

## 12. Before and after (one tiny illustration)
Clever, short, hard for a beginner:
```python
ok = next((t for t in TRANSITIONS.get(post.status, ()) if t == new), None) is not None
```
What we write:
```python
def can_change_status(current_status, new_status):
    """Say whether a post may move from one status to another."""
    allowed_next_statuses = ALLOWED_TRANSITIONS[current_status]
    return new_status in allowed_next_statuses
```

## 13. How earlier design choices were simplified
| Earlier choice | Beginner-readable replacement |
|---|---|
| DRF ViewSets and routers | Explicit `APIView` classes |
| State-machine library idea | A dict plus `change_status()` |
| Hypothesis property-based tests | Named test cases, including specific daylight-saving dates |
| Mutation testing on the auto-post gate | An exhaustive, readable table of every input combination |
| `Protocol` / abstract interfaces | A plain base class and subclasses |
| Threaded or gevent worker pools | A single line of Celery configuration, deferred with deployment |
| MultiFernet exposed to callers | Two helper functions, `encrypt_text` and `decrypt_text` |
| Django signals for notifications | An explicit `notify(...)` call where the event happens |

## 14. What this costs, honestly
- More lines of code in places (explicit loops instead of one-liners). That is intended.
- More documentation work each phase (tour, app READMEs). That is also intended, and it doubles as portfolio material.
- Some libraries are used through wrappers, so a library upgrade touches one file.
