"""Scheduling a plan through the API: create, change, pause, resume, upcoming."""

from django.contrib.auth import get_user_model

from planning.models import ContentPlan, PostSlot
from social.models import SocialAccount

URL = "/api/v1/plans/"
EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]


def new_plan(client, user, rules):
    """Create a plan with rules through the API and return the response."""
    account, _ = SocialAccount.objects.get_or_create(
        user=user, platform="demo", display_name="Demo", external_id="api-1"
    )
    details = {
        "name": "Tech news",
        "topics": [{"name": "AI", "preset": "ai_news"}],
        "account_ids": [str(account.id)],
        "schedule_rules": rules,
    }
    return client.post(URL, details, format="json")


def test_a_plan_with_a_schedule_gets_its_coming_slots(client, user):
    response = new_plan(client, user, [{"days_of_week": EVERY_DAY, "times": ["09:00"]}])

    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["schedule_rules"][0]["timezone"] == "Asia/Kolkata"
    assert body["lead_time_minutes"] == 60
    assert body["on_missed_approval"] == "expire"
    upcoming = client.get(f"{URL}{body['id']}/upcoming/").json()
    assert len(upcoming) == 14
    assert upcoming[0]["status"] == "waiting"


def test_a_wrong_time_or_timezone_is_refused(client, user):
    bad_time = new_plan(client, user, [{"days_of_week": [0], "times": ["25:00"]}])
    bad_zone = new_plan(
        client,
        user,
        [{"days_of_week": [0], "times": ["09:00"], "timezone": "Mars/Olympus"}],
    )
    bad_day = new_plan(client, user, [{"days_of_week": [7], "times": ["09:00"]}])

    assert bad_time.status_code == 400
    assert bad_zone.status_code == 400
    assert bad_day.status_code == 400
    assert not ContentPlan.objects.exists()


def test_more_times_in_a_day_than_the_plan_limit_are_refused(client, user):
    # One more than the free tier's 10 posts per plan per day.
    eleven_times = [f"{hour:02d}:00" for hour in range(8, 19)]

    response = new_plan(client, user, [{"days_of_week": [0], "times": eleven_times}])

    assert response.status_code == 403
    assert response.json()["code"] == "quota_exceeded"


def test_replacing_the_schedule_remakes_the_coming_slots(client, user):
    plan_id = new_plan(
        client, user, [{"days_of_week": EVERY_DAY, "times": ["09:00"]}]
    ).json()["id"]
    new_rules = {"schedule_rules": [{"days_of_week": [0], "times": ["18:30"]}]}

    response = client.put(f"{URL}{plan_id}/schedule/", new_rules, format="json")

    assert response.status_code == 200
    assert response.json()["schedule_rules"][0]["times"] == ["18:30"]
    assert PostSlot.objects.count() == 2


def test_pausing_removes_waiting_slots_and_resuming_makes_them_again(client, user):
    plan_id = new_plan(
        client, user, [{"days_of_week": EVERY_DAY, "times": ["09:00"]}]
    ).json()["id"]

    paused = client.post(f"{URL}{plan_id}/pause/").json()
    slots_while_paused = PostSlot.objects.count()
    resumed = client.post(f"{URL}{plan_id}/resume/").json()

    assert paused["paused"] is True
    assert slots_while_paused == 0
    assert resumed["paused"] is False
    assert PostSlot.objects.count() == 14


def test_users_cannot_schedule_or_see_each_others_plans(client, user, api_client):
    plan_id = new_plan(
        client, user, [{"days_of_week": EVERY_DAY, "times": ["09:00"]}]
    ).json()["id"]
    other = get_user_model().objects.create_user(
        email="grace@example.com", password="correct-horse-battery-staple"
    )
    api_client.force_authenticate(other)

    upcoming = api_client.get(f"{URL}{plan_id}/upcoming/")
    paused = api_client.post(f"{URL}{plan_id}/pause/")

    assert upcoming.status_code == 404
    assert paused.status_code == 404
    assert ContentPlan.objects.get(id=plan_id).paused is False
