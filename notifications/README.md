# notifications: telling users what happened

There is no email. Users see notifications when they open the app, and the
frontend polls `/api/v1/me/summary/` for the unread count.

| File | What it does |
|---|---|
| `admin.py` | Shows notifications on the admin site for troubleshooting. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `Notification` and `KIND_CHOICES`, the list of every kind with its title. A test checks every kind is really sent somewhere. |
| `serializers.py` | What a notification looks like in the API. |
| `services.py` | `notify()` (the one way to create a notification), `mark_read`, `mark_all_read`, `count_unread`, `delete_old_notifications`. |
| `tasks.py` | A nightly job that deletes notifications older than 60 days. |
| `urls.py` | `/api/v1/notifications/`, `unread-count/`, `read-all/`, `<id>/read/`. |
| `views.py` | Thin API classes, including a pager that shows 20 at a time. |

**How other features use it:**

```python
from notifications.services import notify

notify(user, "post_published", "Your poster is live on LinkedIn.", related=post)
```

Pass a `dedupe_key` to avoid repeats: while one notification with that key is
unread, calling `notify()` again returns the existing one.
