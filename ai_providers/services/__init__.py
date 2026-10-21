"""
AI Provider services initialization.

Registers all available provider adapters.
"""
from .base_adapter import (
    BaseProviderAdapter,
    ProviderCapability,
    AuthMethod,
    ValidationResult,
    GenerationResult
)
from .registry import registry, ProviderRegistry
from .openai_adapter import OpenAIAdapter

# Register available providers
registry.register(OpenAIAdapter())

__all__ = [
    'BaseProviderAdapter',
    'ProviderCapability',
    'AuthMethod',
    'ValidationResult',
    'GenerationResult',
    'ProviderRegistry',
    'registry',
]
