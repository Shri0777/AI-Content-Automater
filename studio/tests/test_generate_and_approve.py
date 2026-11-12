"""Tests for making a post, reviewing it and approving or rejecting it.

Background jobs run straight away in tests (CELERY_TASK_ALWAYS_EAGER), so
after "generate now" returns, the post has already gone through every stage.
"""

from io import BytesIO

from django.contrib.auth import get_user_model
from kombu.exceptions import OperationalError
from PIL import Image

from notifications.models import Notification
from publishing.tasks import publish_post_task
from studio.models import Post
from studio.tasks import advance_post_task


def generate(client, plan):
    """Ask for a post now and return the response."""
    return client.post(f"/api/v1/plans/{plan.id}/generate-now/")


def post_detail(client, post_id):
    """Return the post's details from the API."""
    return client.get(f"/api/v1/posts/{post_id}/").json()


def test_generate_now_makes_a_post_that_waits_for_approval(client, plan):
    response = generate(client, plan)

    assert response.status_code == 202
    post = post_detail(client, response.json()["id"])
    assert post["status"] == "awaiting_approval"
    assert post["demo_mode"] is True
    assert post["article"]["url"].startswith("https://example.com/demo/ai_news/")
    version = post["versions"][0]
    assert post["article"]["url"] in version["caption"]
    assert version["review"]["verdict"] == "pass"
    stages = [step["stage"] for step in post["steps"]]
    assert stages == ["researching", "drafting", "imaging", "reviewing"]


def test_the_user_is_told_a_post_is_waiting(client, user, plan):
    generate(client, plan)

    assert Notification.objects.filter(
        user=user, kind="post_awaiting_approval"
    ).exists()
    assert client.get("/api/v1/me/summary/").json()["posts_awaiting_approval"] == 1


def test_the_poster_is_a_real_png_image(client, plan):
    post_id = generate(client, plan).json()["id"]
    poster_url = post_detail(client, post_id)["poster_url"]

    response = client.get(poster_url)

    assert response.status_code == 200
    assert response["Content-Type"] == "image/png"
    image = Image.open(BytesIO(response.content))
    assert image.size == (1080, 1080)


def test_approving_publishes_to_the_plans_accounts_with_the_ai_label(client, plan):
    post_id = generate(client, plan).json()["id"]

    response = client.post(f"/api/v1/posts/{post_id}/approve/")

    assert response.status_code == 200
    post = post_detail(client, post_id)
    assert post["status"] == "published"
    publication = post["publications"][0]
    assert publication["status"] == "published"
    assert publication["external_id"].startswith("demo-post-")
    assert publication["account_name"] == "Demo account 1"


def test_a_post_cannot_be_approved_twice(client, plan):
    post_id = generate(client, plan).json()["id"]
    client.post(f"/api/v1/posts/{post_id}/approve/")

    response = client.post(f"/api/v1/posts/{post_id}/approve/")

    assert response.status_code == 409
    assert response.json()["code"] == "status_conflict"
    assert len(post_detail(client, post_id)["publications"]) == 1


def test_a_rejected_post_is_never_published(client, plan):
    post_id = generate(client, plan).json()["id"]

    assert client.post(f"/api/v1/posts/{post_id}/reject/").status_code == 200
    assert client.post(f"/api/v1/posts/{post_id}/approve/").status_code == 409
    assert post_detail(client, post_id)["publications"] == []


def test_each_post_uses_a_different_article(client, plan):
    first = post_detail(client, generate(client, plan).json()["id"])
    second = post_detail(client, generate(client, plan).json()["id"])

    assert first["article"]["url"] != second["article"]["url"]


def test_a_post_is_skipped_when_no_unused_article_is_left(client, plan):
    for _ in range(3):
        generate(client, plan)

    post = post_detail(client, generate(client, plan).json()["id"])

    assert post["status"] == "skipped"
    assert "filler" in post["status_reason"]


def test_generating_needs_text_and_image_credentials(client, user, plan):
    user.providercredential_set.filter(kind="image").delete()

    response = generate(client, plan)

    assert response.status_code == 400
    assert response.json()["code"] == "credential_missing"
    assert not Post.objects.exists()


def test_generate_now_is_limited_per_day(client, plan):
    for _ in range(4):
        assert generate(client, plan).status_code == 202

    response = generate(client, plan)

    assert response.status_code == 403
    assert response.json()["resource"] == "posts_per_plan_per_day"
    assert Post.objects.count() == 4


def test_users_cannot_see_or_approve_other_users_posts(client, plan):
    post_id = generate(client, plan).json()["id"]
    other = get_user_model().objects.create_user(
        email="grace@example.com", password="correct-horse-battery-staple"
    )
    client.force_authenticate(other)

    assert client.get(f"/api/v1/posts/{post_id}/").status_code == 404
    assert client.get(f"/api/v1/posts/{post_id}/poster/").status_code == 404
    assert client.post(f"/api/v1/posts/{post_id}/approve/").status_code == 404
    assert client.get("/api/v1/posts/").json()["results"] == []


def test_a_post_fails_clearly_when_background_jobs_are_down(client, plan, monkeypatch):
    def queue_is_down(post_id):
        raise OperationalError("Connection refused")

    monkeypatch.setattr(advance_post_task, "delay", queue_is_down)

    response = generate(client, plan)

    assert response.status_code == 503
    assert response.json()["code"] == "jobs_unavailable"
    assert Post.objects.get().status == "failed"


def test_an_approved_post_fails_clearly_when_background_jobs_are_down(
    client, plan, monkeypatch
):
    post_id = generate(client, plan).json()["id"]

    def queue_is_down(post_id):
        raise OperationalError("Connection refused")

    monkeypatch.setattr(publish_post_task, "delay", queue_is_down)

    response = client.post(f"/api/v1/posts/{post_id}/approve/")

    assert response.status_code == 503
    assert Post.objects.get().status == "failed"


def test_a_job_for_a_deleted_post_finishes_quietly(plan):
    post = Post.objects.create(user=plan.user, plan=plan)
    post_id = str(post.id)
    plan.delete()

    assert advance_post_task.delay(post_id).get() == "deleted"
    assert publish_post_task.delay(post_id).get() == "deleted"
