"""
Platform-to-image-format mapping for the brief-first poster workflow.

Single source of truth for converting selected Buffer destination channels into
the image orientation and NVIDIA FLUX generation size needed for each poster
variant.

This is a reasoned DEFAULT mapping. The current verified Buffer integration
(`content/services/buffer_service.py`) returns channel `id`, `service`,
`formatted_username`, and `avatar` but does NOT expose per-channel media-format
or placement requirements. Therefore placements such as Instagram Stories or
Reels are not claimed as exactly supported. Square 1024x1024 is the documented
fallback when a service or placement cannot be identified reliably.

Update this module when platform requirements are verified against live Buffer
channels or Buffer documentation.
"""

from dataclasses import dataclass

# Sizes supported by the NVIDIA FLUX adapter (verified in
# ai_providers/services/nvidia_flux_adapter.py generate_image body).
SUPPORTED_SIZES = ("1024x1024", "1792x1024", "1024x1792")

SIZE_SQUARE = "1024x1024"
SIZE_LANDSCAPE = "1792x1024"
SIZE_PORTRAIT = "1024x1792"

ORIENTATION_SQUARE = "square"
ORIENTATION_LANDSCAPE = "landscape"
ORIENTATION_PORTRAIT = "portrait"

# Default generation size when a service/placement cannot be identified.
DEFAULT_SIZE = SIZE_SQUARE
DEFAULT_ORIENTATION = ORIENTATION_SQUARE


@dataclass(frozen=True)
class PlatformFormat:
    """The image format to generate for one destination platform."""

    service: str          # normalized Buffer service name (e.g. "instagram")
    orientation: str      # one of ORIENTATION_*
    size: str             # one of SUPPORTED_SIZES
    aspect_ratio: str     # human-readable aspect ratio (e.g. "1:1")
    label: str            # UI-friendly label
    verified: bool        # True only when placement support is verified


# Default mapping: normalized Buffer service -> format.
# All entries are marked verified=False because the current integration has not
# been confirmed against live Buffer channels. Square is the fallback for any
# service not listed here.
_PLATFORM_FORMATS = {
    "instagram": PlatformFormat(
        service="instagram",
        orientation=ORIENTATION_SQUARE,
        size=SIZE_SQUARE,
        aspect_ratio="1:1",
        label="Instagram feed (square)",
        verified=False,
    ),
    "linkedin": PlatformFormat(
        service="linkedin",
        orientation=ORIENTATION_LANDSCAPE,
        size=SIZE_LANDSCAPE,
        aspect_ratio="16:9",
        label="LinkedIn (landscape)",
        verified=False,
    ),
    "twitter": PlatformFormat(
        service="twitter",
        orientation=ORIENTATION_LANDSCAPE,
        size=SIZE_LANDSCAPE,
        aspect_ratio="16:9",
        label="X/Twitter (landscape)",
        verified=False,
    ),
    "facebook": PlatformFormat(
        service="facebook",
        orientation=ORIENTATION_SQUARE,
        size=SIZE_SQUARE,
        aspect_ratio="1:1",
        label="Facebook feed (square)",
        verified=False,
    ),
    "pinterest": PlatformFormat(
        service="pinterest",
        orientation=ORIENTATION_PORTRAIT,
        size=SIZE_PORTRAIT,
        aspect_ratio="2:3 (closest available: 9:16)",
        label="Pinterest (portrait)",
        verified=False,
    ),
}


def normalize_service(service_name: str) -> str:
    """Normalize a Buffer service name for safe lookup."""
    return (service_name or "").strip().lower()


def get_format_for_service(service_name: str) -> PlatformFormat:
    """Return the format for a Buffer service, falling back to square.

    Unknown or unverified services receive the documented square default so the
    workflow never fails for an unrecognized platform. The returned format is
    marked verified=False unless explicitly listed above as verified.
    """
    service = normalize_service(service_name)
    fmt = _PLATFORM_FORMATS.get(service)
    if fmt is not None:
        return fmt
    return PlatformFormat(
        service=service or "unknown",
        orientation=DEFAULT_ORIENTATION,
        size=DEFAULT_SIZE,
        aspect_ratio="1:1",
        label="Square feed (default)",
        verified=False,
    )


def is_supported_size(size: str) -> bool:
    """Return True if the size is supported by the FLUX adapter."""
    return size in SUPPORTED_SIZES


def group_destinations_by_format(destinations):
    """Group destination profiles by the image format they require.

    Args:
        destinations: iterable of profile dicts from BufferPublishingService
            (each with 'id' and 'service' keys) or strings naming a service.

    Returns:
        dict mapping size string -> list of destination identifiers (profile IDs
        or service names) that share that format. Only selected destinations are
        grouped; unselected destinations are never included by the caller.
    """
    groups = {}
    for dest in destinations:
        if isinstance(dest, dict):
            service = dest.get("service", "unknown")
            identifier = dest.get("id") or service
        else:
            service = str(dest)
            identifier = service
        fmt = get_format_for_service(service)
        groups.setdefault(fmt.size, []).append(identifier)
    return groups


def get_required_variants(destinations):
    """Return the unique PlatformFormat variants needed for selected destinations.

    One variant per unique generation size, so destinations that safely share a
    format produce a single asset. Destinations with materially different aspect
    ratios produce distinct variants.
    """
    seen = {}
    for dest in destinations:
        if isinstance(dest, dict):
            service = dest.get("service", "unknown")
        else:
            service = str(dest)
        fmt = get_format_for_service(service)
        seen.setdefault(fmt.size, fmt)
    return list(seen.values())
