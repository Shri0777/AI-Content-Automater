"""NVIDIA NIM adapter using its OpenAI-compatible chat completions API."""
from typing import Optional

from .openai_adapter import OpenAIAdapter


class NVIDIAAdapter(OpenAIAdapter):
    """NVIDIA-hosted NIM models authenticated with an NVIDIA API key."""

    @property
    def provider_name(self) -> str:
        return "nvidia"

    @property
    def display_name(self) -> str:
        return "NVIDIA NIM"

    @property
    def default_endpoint(self) -> str:
        return "https://integrate.api.nvidia.com/v1"

    @property
    def default_model(self) -> str:
        return "qwen/qwen3-235b-a22b"

    def identify_provider(self, credential: str, endpoint: Optional[str] = None) -> bool:
        """Identify NVIDIA NIM by probing its configured models endpoint."""
        endpoint = (endpoint or self.default_endpoint).rstrip("/")
        return super().identify_provider(credential, endpoint=endpoint)
