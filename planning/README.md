# planning: content plans and their topics

A plan says **what** to post about (topics and free-text requirements),
**where** (linked social accounts) and **how** posts are approved.

| File | What it does |
|---|---|
| `admin.py` | Shows plans, with their topics, on the admin site. |
| `apps.py` | Tells Django this app exists. |
| `models.py` | `ContentPlan` and `Topic`. A plan's `ai_label_enabled` and `ai_label_text` control the "Made with AI assistance." line added to posts. |
| `serializers.py` | What goes in (`PlanCreateSerializer`) and out (`PlanSerializer`) of the API. |
| `services.py` | `create_plan` (checks the plan and topic limits and that every account is the user's), `get_plans`, `get_plan`, `delete_plan`. |
| `urls.py` | `/api/v1/plans/` and `/api/v1/plans/<id>/`. |
| `views.py` | Thin API classes: list, create, show, delete. |

**Today:** every post waits for approval (`approval_mode` is `manual`).
Schedules (days and times) arrive in Phase 5, and automatic posting with a
closed-by-default safety gate in Phase 8. Until then, posts are made with
`POST /api/v1/plans/<id>/generate-now/` (see `studio/`).
