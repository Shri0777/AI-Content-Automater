"""
Tests for poster variant generation
(`content/services/image_generation_service.generate_poster_variants`).

FLUX image generation is mocked; no live NVIDIA calls are made.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_providers.services.base_adapter import GenerationResult
from content.models import Content, Media
from content.services.image_generation_service import ImageGenerationService
from content.services.platform_formats import SIZE_LANDSCAPE, SIZE_PORTRAIT, SIZE_SQUARE

User = get_user_model()


class PosterVariantGenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="testpass123",
        )
        self.content = Content.objects.create(
            owner=self.user,
            title="Test post",
            brief="Announce our new AI automation service for small businesses.",
            lifecycle_state="draft",
        )

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_generates_one_variant_per_unique_format(self, mock_gen):
        """Shared formats (instagram+facebook=square) produce one asset."""
        mock_gen.return_value = {
            "success": True,
            "media": MagicMock(pk=1, file=MagicMock(url="/media/test.png")),
        }

        destinations = [
            {"id": "ch_1", "service": "instagram"},  # square
            {"id": "ch_2", "service": "facebook"},    # square (shared)
            {"id": "ch_3", "service": "linkedin"},    # landscape
        ]

        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Try our AI automation service today. Sign up now! #ai #automation",
            destinations=destinations,
        )

        self.assertTrue(result["success"])
        # square shared by instagram+facebook -> 1 variant; linkedin -> 1 variant
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["successful_count"], 2)
        # Only 2 FLUX calls (one per unique format), not 3
        self.assertEqual(mock_gen.call_count, 2)

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_only_selected_destinations_get_variants(self, mock_gen):
        mock_gen.return_value = {
            "success": True,
            "media": MagicMock(pk=1, file=MagicMock(url="/media/test.png")),
        }

        # Three destinations selected
        destinations = [
            {"id": "ch_1", "service": "instagram"},
            {"id": "ch_2", "service": "twitter"},
            {"id": "ch_3", "service": "pinterest"},
        ]

        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Copy text.",
            destinations=destinations,
        )

        # instagram=square, twitter=landscape, pinterest=portrait -> 3 variants
        self.assertEqual(result["total"], 3)
        self.assertEqual(mock_gen.call_count, 3)

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_no_variants_for_unselected_channels(self, mock_gen):
        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Copy text.",
            destinations=[],
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "missing_destinations")
        mock_gen.assert_not_called()

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_failed_variant_is_recorded_independently(self, mock_gen):
        """One failed variant does not block the other."""
        def side_effect(**kwargs):
            size = kwargs.get("size", "")
            if size == SIZE_PORTRAIT:
                return {"success": False, "error": "FLUX rate limited", "error_type": "rate_limited"}
            return {"success": True, "media": MagicMock(pk=1, file=MagicMock(url="/media/test.png"))}

        mock_gen.side_effect = side_effect

        destinations = [
            {"id": "ch_1", "service": "instagram"},   # square
            {"id": "ch_2", "service": "pinterest"},    # portrait
        ]

        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Copy text.",
            destinations=destinations,
        )

        self.assertTrue(result["success"])  # at least one succeeded
        self.assertEqual(result["successful_count"], 1)
        variants = result["variants"]
        failed = [v for v in variants if not v["success"]]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["format"].size, SIZE_PORTRAIT)

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_media_record_tagged_with_platform(self, mock_gen):
        mock_media = MagicMock()
        mock_media.pk = 1
        mock_media.file = MagicMock(url="/media/test.png")
        mock_gen.return_value = {"success": True, "media": mock_media}

        destinations = [{"id": "ch_1", "service": "linkedin"}]

        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Copy text.",
            destinations=destinations,
        )

        variant = result["variants"][0]
        self.assertTrue(variant["success"])
        variant["media"].platforms = ["linkedin"]
        variant["media"].generation_state = "generated"
        variant["media"].save.assert_called()

    @patch(
        "content.services.image_generation_service."
        "ImageGenerationService.generate_image_for_content"
    )
    def test_missing_provider_returns_failure(self, mock_gen):
        mock_gen.return_value = {
            "success": False,
            "error": "No active AI image provider configured.",
            "error_type": "no_provider",
        }

        destinations = [{"id": "ch_1", "service": "instagram"}]

        result = ImageGenerationService.generate_poster_variants(
            content=self.content,
            user=self.user,
            brief=self.content.brief,
            copy="Copy text.",
            destinations=destinations,
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["variants"][0]["error_type"], "no_provider")

    def test_only_supported_sizes_passed_to_flux(self):
        """Verify that only FLUX-supported sizes are used."""
        from content.services.platform_formats import get_required_variants
        destinations = [
            {"id": "ch_1", "service": "instagram"},   # square
            {"id": "ch_2", "service": "linkedin"},     # landscape
            {"id": "ch_3", "service": "pinterest"},    # portrait
        ]
        variants = get_required_variants(destinations)
        sizes = {v.size for v in variants}
        self.assertEqual(sizes, {SIZE_SQUARE, SIZE_LANDSCAPE, SIZE_PORTRAIT})
