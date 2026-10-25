"""
Tests for the brief-based post copy generation service
(`content/services/brief_generation_service.py`).

External AI providers are mocked; no live AI requests are made.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_providers.services.base_adapter import GenerationResult
from content.models import Content, ContentVersion, ContentReview
from content.services.brief_generation_service import BriefGenerationService

User = get_user_model()


class BriefGenerationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="testpass123",
        )
        self.content = Content.objects.create(
            owner=self.user,
            title="My post",
            brief="Announce our new AI automation service for small businesses.",
            lifecycle_state="draft",
            generation_status="queued",
        )

    @patch(
        "content.services.brief_generation_service."
        "CredentialValidationService.get_active_provider_for_user"
    )
    @patch(
        "content.services.brief_generation_service."
        "QualityReviewService.review_version"
    )
    def test_successful_generation_creates_version_and_review(
        self, mock_review, mock_get_provider
    ):
        # Mock provider adapter.
        mock_adapter = MagicMock()
        mock_adapter.generate_text.return_value = GenerationResult(
            success=True,
            content="Hook: Try AI automation.\nBody: Save time.\nCTA: Sign up today.\n#ai #automation",
            model_used="gpt-4o-mini",
        )
        mock_get_provider.return_value = (mock_adapter, "cred", "gpt-4o-mini", None)

        # Mock review to return an object with the attributes the service reads.
        mock_review.return_value = MagicMock(status="passed", score=0.9)

        result = BriefGenerationService.generate_post_from_brief(
            content=self.content, user=self.user
        )

        self.assertTrue(result["success"])
        self.assertIn("version", result)
        self.assertIn("review", result)
        self.assertEqual(self.content.versions.count(), 1)
        version = self.content.versions.first()
        self.assertEqual(version.content_text, result["version"].content_text)
        self.assertFalse(version.is_approved)  # human approval still required
        self.assertEqual(self.content.generation_status, "complete")

    @patch(
        "content.services.brief_generation_service."
        "CredentialValidationService.get_active_provider_for_user"
    )
    def test_missing_provider_returns_recoverable_failure(self, mock_get_provider):
        mock_get_provider.return_value = (None, None, None, None)

        result = BriefGenerationService.generate_post_from_brief(
            content=self.content, user=self.user
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "no_provider")
        self.content.refresh_from_db()
        self.assertEqual(self.content.generation_status, "failed")

    @patch(
        "content.services.brief_generation_service."
        "CredentialValidationService.get_active_provider_for_user"
    )
    @patch(
        "content.services.brief_generation_service."
        "QualityReviewService.review_version"
    )
    def test_review_failure_does_not_mark_approved(
        self, mock_review, mock_get_provider
    ):
        mock_adapter = MagicMock()
        mock_adapter.generate_text.return_value = GenerationResult(
            success=True, content="Some copy here.", model_used="gpt-4o-mini"
        )
        mock_get_provider.return_value = (mock_adapter, "cred", "gpt-4o-mini", None)
        mock_review.return_value = MagicMock(status="failed", score=0.3)

        result = BriefGenerationService.generate_post_from_brief(
            content=self.content, user=self.user
        )

        self.assertTrue(result["success"])
        version = self.content.versions.first()
        self.assertFalse(version.is_approved)
        self.assertEqual(self.content.generation_status, "partial")

    @patch(
        "content.services.brief_generation_service."
        "CredentialValidationService.get_active_provider_for_user"
    )
    def test_empty_brief_fails(self, mock_get_provider):
        empty_brief_content = Content.objects.create(
            owner=self.user,
            title="Empty",
            brief="   ",
            lifecycle_state="draft",
        )
        result = BriefGenerationService.generate_post_from_brief(
            content=empty_brief_content, user=self.user
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "missing_brief")
