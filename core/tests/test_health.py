"""Tests for the health check endpoint."""

import pytest


@pytest.mark.django_db
def test_health_reports_ok_when_the_database_answers(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_does_not_need_a_login(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code != 401
