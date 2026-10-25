"""
Unit tests for the platform-to-image-format mapping
(`content/services/platform_formats.py`).

All external services are mocked/absent here: this module is pure Python and
makes no network or AI calls.
"""

from django.test import TestCase

from content.services.platform_formats import (
    SIZE_LANDSCAPE,
    SIZE_PORTRAIT,
    SIZE_SQUARE,
    SUPPORTED_SIZES,
    get_format_for_service,
    get_required_variants,
    group_destinations_by_format,
    is_supported_size,
    normalize_service,
)


class NormalizeServiceTests(TestCase):
    def test_normalizes_known_service(self):
        self.assertEqual(normalize_service("LinkedIn"), "linkedin")

    def test_normalizes_whitespace_and_case(self):
        self.assertEqual(normalize_service("  TWITTER  "), "twitter")

    def test_normalizes_empty(self):
        self.assertEqual(normalize_service(""), "")
        self.assertEqual(normalize_service(None), "")


class GetFormatForServiceTests(TestCase):
    def test_known_service_returns_mapped_format(self):
        fmt = get_format_for_service("instagram")
        self.assertEqual(fmt.service, "instagram")
        self.assertEqual(fmt.size, SIZE_SQUARE)
        self.assertEqual(fmt.orientation, "square")

    def test_linkedin_maps_to_landscape(self):
        fmt = get_format_for_service("linkedin")
        self.assertEqual(fmt.size, SIZE_LANDSCAPE)
        self.assertEqual(fmt.orientation, "landscape")

    def test_unknown_service_falls_back_to_square(self):
        fmt = get_format_for_service("not-a-real-service")
        self.assertEqual(fmt.size, SIZE_SQUARE)
        self.assertEqual(fmt.orientation, "square")
        self.assertFalse(fmt.verified)

    def test_all_known_formats_use_supported_sizes(self):
        for service in ("instagram", "linkedin", "twitter", "facebook", "pinterest"):
            fmt = get_format_for_service(service)
            self.assertIn(fmt.size, SUPPORTED_SIZES)

    def test_unknown_service_is_not_verified(self):
        fmt = get_format_for_service("mystery-service")
        self.assertFalse(fmt.verified)


class IsSupportedSizeTests(TestCase):
    def test_supported_sizes_accepted(self):
        for size in SUPPORTED_SIZES:
            self.assertTrue(is_supported_size(size))

    def test_unsupported_size_rejected(self):
        self.assertFalse(is_supported_size("800x600"))
        self.assertFalse(is_supported_size(""))


class GroupDestinationsByFormatTests(TestCase):
    def test_group_by_size(self):
        destinations = [
            {"id": "ch_1", "service": "instagram"},   # square
            {"id": "ch_2", "service": "facebook"},     # square
            {"id": "ch_3", "service": "linkedin"},     # landscape
        ]
        groups = group_destinations_by_format(destinations)
        # instagram + facebook share square -> one group
        self.assertEqual(set(groups.keys()), {SIZE_SQUARE, SIZE_LANDSCAPE})
        self.assertEqual(set(groups[SIZE_SQUARE]), {"ch_1", "ch_2"})
        self.assertEqual(set(groups[SIZE_LANDSCAPE]), {"ch_3"})

    def test_unknown_service_grouped_under_square(self):
        destinations = [{"id": "ch_9", "service": "mystery"}]
        groups = group_destinations_by_format(destinations)
        self.assertEqual(set(groups.keys()), {SIZE_SQUARE})
        self.assertEqual(set(groups[SIZE_SQUARE]), {"ch_9"})

    def test_empty_input(self):
        self.assertEqual(group_destinations_by_format([]), {})

    def test_string_inputs_accepted(self):
        groups = group_destinations_by_format(["twitter", "linkedin"])
        self.assertEqual(set(groups.keys()), {SIZE_LANDSCAPE})


class GetRequiredVariantsTests(TestCase):
    def test_one_variant_per_unique_size(self):
        destinations = [
            {"id": "ch_1", "service": "instagram"},   # square
            {"id": "ch_2", "service": "facebook"},     # square (shared)
            {"id": "ch_3", "service": "linkedin"},     # landscape
            {"id": "ch_4", "service": "pinterest"},    # portrait
        ]
        variants = get_required_variants(destinations)
        sizes = {v.size for v in variants}
        self.assertEqual(sizes, {SIZE_SQUARE, SIZE_LANDSCAPE, SIZE_PORTRAIT})
        self.assertEqual(len(variants), 3)

    def test_shared_format_reuses_one_variant(self):
        destinations = [
            {"id": "ch_1", "service": "instagram"},
            {"id": "ch_2", "service": "facebook"},
        ]
        variants = get_required_variants(destinations)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].size, SIZE_SQUARE)

    def test_no_destinations_no_variants(self):
        self.assertEqual(get_required_variants([]), [])
