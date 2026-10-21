"""
Anthropic provider adapter implementation.

Provides provider-agnostic text generation using Anthropic's messages API.
"""
import logging
import time
from typing import Any, Dict, List, Optional

import requests

from .base_adapter import (
    AuthMethod,
    BaseProviderAdapter,
    GenerationRequest,
    GenerationResult,
    ProviderCapability,
    ProviderErrorType,
    ValidationResult,
)
from .security import validate_safe_endpoint

logger = logging.getLogger(__name__)


class AnthropicAdapter(BaseProviderAdapter):
    """Anthropic API adapter for text generation."""
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def display_name(self) -> str:
        return "Anthropic"
    
    @property
    def supported_capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.TEXT_GENERATION]
    
    @property
    def auth_method(self) -> AuthMethod:
        return AuthMethod.API_KEY_HEADER
    
    @property
    def default_endpoint(self) -> str:
        return "https://api.anthropic.com/v1"
    
    @property
    def default_model(self) -> str:
        return "claude-3-5-sonnet-20241022"
    
    @property
    def requires_model_name(self) -> bool:
        return True
    
    def identify_provider(
        self,
        credential: str,
        endpoint: Optional[str] = None
    ) -> bool:
        """
        Identify Anthropic by probing models endpoint or API contract.
        """
        if not credential or not credential.strip():
            return False
            
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        is_safe, _ = validate_safe_endpoint(endpoint)
        if not is_safe:
            return False
        
        try:
            headers = self._get_headers(credential)
            response = requests.get(
                f"{endpoint}/models",
                headers=headers,
                timeout=5,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                    models = [m.get('id', '') for m in data['data'] if isinstance(m, dict)]
                    if any('claude' in m.lower() for m in models):
                        return True
            return False
        except Exception as e:
            logger.debug(f"Anthropic identification check failed: {e}")
            return False
    
    def validate_credential(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> ValidationResult:
        """
        Validate credential and check capability/model availability.
        """
        if not credential or not credential.strip():
            return ValidationResult(
                success=False,
                message="API key is required",
                error_type=ProviderErrorType.MISSING_CREDENTIAL
            )
        
        if capability and capability not in self.supported_capabilities:
            return ValidationResult(
                success=False,
                message=f"Anthropic adapter does not support capability '{capability.value}'",
                error_type=ProviderErrorType.LACKS_CAPABILITY
            )
        
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        is_safe, reason = validate_safe_endpoint(endpoint)
        if not is_safe:
            return ValidationResult(
                success=False,
                message=f"Invalid or blocked endpoint: {reason}",
                error_type=ProviderErrorType.SSRF_BLOCKED
            )
        
        try:
            headers = self._get_headers(credential)
            response = requests.get(
                f"{endpoint}/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                return ValidationResult(
                    success=False,
                    message="Authentication failed: Invalid Anthropic API key",
                    error_type=ProviderErrorType.INVALID_CREDENTIAL
                )
            
            if response.status_code == 403:
                return ValidationResult(
                    success=False,
                    message="Access forbidden: check Anthropic workspace permissions or billing",
                    error_type=ProviderErrorType.QUOTA_EXCEEDED
                )
            
            if response.status_code == 429:
                return ValidationResult(
                    success=False,
                    message="Anthropic rate limit or quota exceeded",
                    error_type=ProviderErrorType.RATE_LIMITED
                )
            
            if response.status_code != 200:
                return ValidationResult(
                    success=False,
                    message=f"Provider API error: HTTP {response.status_code}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
            data = response.json()
            available_models = [
                m.get('id') for m in data.get('data', [])
                if isinstance(m, dict) and 'id' in m
            ]
            
            target_model = model_name or self.default_model
            if model_name and target_model not in available_models:
                return ValidationResult(
                    success=False,
                    message=f"Requested model '{model_name}' is not available for this account",
                    error_type=ProviderErrorType.MODEL_UNAVAILABLE,
                    capabilities=["text"]
                )
            
            return ValidationResult(
                success=True,
                message="Anthropic credentials and models validated successfully",
                provider_identified="anthropic",
                capabilities=["text"],
                model_available=target_model
            )
            
        except requests.exceptions.Timeout:
            return ValidationResult(
                success=False,
                message="Connection timed out while contacting Anthropic API",
                error_type=ProviderErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                success=False,
                message="Connection failed: Unable to reach Anthropic endpoint",
                error_type=ProviderErrorType.CONNECTION_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected validation error in AnthropicAdapter: {e}")
            return ValidationResult(
                success=False,
                message=f"Validation error: {str(e)}",
                error_type=ProviderErrorType.UNKNOWN
            )
    
    def generate_text(
        self,
        request: GenerationRequest | str,
        credential: str,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate text using Anthropic's messages endpoint with bounded retries.
        """
        if isinstance(request, str):
            req = GenerationRequest(prompt=request, model_name=model_name, endpoint=endpoint)
        else:
            req = request
            
        endpoint = (req.endpoint or endpoint or self.default_endpoint).rstrip('/')
        model = req.model_name or model_name or self.default_model
        
        is_safe, reason = validate_safe_endpoint(endpoint)
        if not is_safe:
            return GenerationResult(
                success=False,
                error=f"Endpoint blocked by SSRF protection: {reason}",
                error_type=ProviderErrorType.SSRF_BLOCKED
            )
        
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "messages": [
                {"role": "user", "content": req.prompt}
            ],
            **req.extra_params,
            **kwargs
        }
        if req.system_prompt:
            body["system"] = req.system_prompt
            
        headers = self._get_headers(credential)
        
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    f"{endpoint}/messages",
                    headers=headers,
                    json=body,
                    timeout=30,
                    allow_redirects=False
                )
                
                if response.status_code == 401:
                    return GenerationResult(
                        success=False,
                        error="Authentication rejected: Invalid Anthropic API key",
                        error_type=ProviderErrorType.INVALID_CREDENTIAL
                    )
                
                if response.status_code == 429:
                    return GenerationResult(
                        success=False,
                        error="Anthropic rate limit exceeded",
                        error_type=ProviderErrorType.RATE_LIMITED
                    )
                
                if response.status_code in (500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                
                if response.status_code != 200:
                    try:
                        err_data = response.json()
                        err_msg = err_data.get('error', {}).get('message', response.text)
                    except Exception:
                        err_msg = response.text
                    return GenerationResult(
                        success=False,
                        error=f"Anthropic error (HTTP {response.status_code}): {err_msg}",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE if response.status_code < 500 else ProviderErrorType.CONNECTION_ERROR
                    )
                
                data = response.json()
                content_blocks = data.get('content', [])
                if not content_blocks or not isinstance(content_blocks, list):
                    return GenerationResult(
                        success=False,
                        error="Malformed response from Anthropic: 'content' missing or empty",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE
                    )
                
                # Concatenate text blocks
                text_parts = [
                    block.get('text', '') for block in content_blocks
                    if isinstance(block, dict) and block.get('type') == 'text'
                ]
                text = "".join(text_parts)
                
                usage = data.get('usage', {})
                input_tokens = usage.get('input_tokens', 0) if isinstance(usage, dict) else 0
                output_tokens = usage.get('output_tokens', 0) if isinstance(usage, dict) else 0
                
                return GenerationResult(
                    success=True,
                    content=text,
                    model_used=data.get('model', model),
                    tokens_used=input_tokens + output_tokens,
                    metadata={
                        'stop_reason': data.get('stop_reason'),
                        'usage': usage,
                    }
                )
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return GenerationResult(
                    success=False,
                    error="Anthropic generation request timed out",
                    error_type=ProviderErrorType.TIMEOUT
                )
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return GenerationResult(
                    success=False,
                    error="Connection error contacting Anthropic endpoint",
                    error_type=ProviderErrorType.CONNECTION_ERROR
                )
            except Exception as e:
                logger.error(f"Unexpected error in Anthropic text generation: {e}")
                return GenerationResult(
                    success=False,
                    error=str(e),
                    error_type=ProviderErrorType.UNKNOWN
                )
        
        return GenerationResult(
            success=False,
            error="Exceeded maximum retries for transient failure",
            error_type=ProviderErrorType.CONNECTION_ERROR
        )
    
    def get_available_models(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> List[str]:
        """Get list of available models from Anthropic."""
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        is_safe, _ = validate_safe_endpoint(endpoint)
        if not is_safe:
            return []
        
        try:
            headers = self._get_headers(credential)
            response = requests.get(f"{endpoint}/models", headers=headers, timeout=10, allow_redirects=False)
            if response.status_code == 200:
                data = response.json()
                return [
                    m.get('id') for m in data.get('data', [])
                    if isinstance(m, dict) and 'id' in m
                ]
            return []
        except Exception:
            return []
    
    def _get_headers(self, credential: str) -> Dict[str, str]:
        """Get authenticated request headers for Anthropic."""
        return {
            "x-api-key": credential,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
