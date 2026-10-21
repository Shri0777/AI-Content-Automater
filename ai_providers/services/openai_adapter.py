"""
OpenAI provider adapter implementation.

Provides provider-agnostic text generation using OpenAI's chat completions API.
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


class OpenAIAdapter(BaseProviderAdapter):
    """OpenAI API adapter for text generation."""
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def display_name(self) -> str:
        return "OpenAI"
    
    @property
    def supported_capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.TEXT_GENERATION]
    
    @property
    def auth_method(self) -> AuthMethod:
        return AuthMethod.BEARER_TOKEN
    
    @property
    def default_endpoint(self) -> str:
        return "https://api.openai.com/v1"
    
    @property
    def default_model(self) -> str:
        return "gpt-4o-mini"
    
    @property
    def requires_model_name(self) -> bool:
        return True
    
    def identify_provider(
        self,
        credential: str,
        endpoint: Optional[str] = None
    ) -> bool:
        """
        Identify OpenAI by probing models endpoint with bounded timeout.
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
                    if any('gpt' in m.lower() for m in models):
                        return True
            return False
        except Exception as e:
            logger.debug(f"OpenAI identification check failed: {e}")
            return False
    
    def validate_credential(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> ValidationResult:
        """
        Validate credential and check capability/model availability with explicit error mapping.
        """
        if not credential or not credential.strip():
            return ValidationResult(
                success=False,
                message="API key is required",
                error_type=ProviderErrorType.MISSING_CREDENTIAL
            )
        
        # Capability check
        if capability and capability not in self.supported_capabilities:
            return ValidationResult(
                success=False,
                message=f"OpenAI adapter does not support capability '{capability.value}'",
                error_type=ProviderErrorType.LACKS_CAPABILITY
            )
        
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        
        # SSRF validation
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
                    message="Authentication failed: Invalid API key",
                    error_type=ProviderErrorType.INVALID_CREDENTIAL
                )
            
            if response.status_code == 403:
                return ValidationResult(
                    success=False,
                    message="Access forbidden: insufficient permissions or billing restriction",
                    error_type=ProviderErrorType.QUOTA_EXCEEDED
                )
            
            if response.status_code == 429:
                return ValidationResult(
                    success=False,
                    message="Rate limit or quota exceeded",
                    error_type=ProviderErrorType.RATE_LIMITED
                )
            
            if response.status_code != 200:
                return ValidationResult(
                    success=False,
                    message=f"Provider API error: HTTP {response.status_code}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
            data = response.json()
            if not isinstance(data, dict) or 'data' not in data:
                return ValidationResult(
                    success=False,
                    message="Unexpected response schema from OpenAI models endpoint",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
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
                message="OpenAI credentials and models validated successfully",
                provider_identified="openai",
                capabilities=["text"],
                model_available=target_model
            )
            
        except requests.exceptions.Timeout:
            return ValidationResult(
                success=False,
                message="Connection timed out while contacting OpenAI API",
                error_type=ProviderErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                success=False,
                message="Connection failed: Unable to reach OpenAI endpoint",
                error_type=ProviderErrorType.CONNECTION_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected validation error in OpenAIAdapter: {e}")
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
        Generate text using OpenAI's chat completions endpoint with bounded retries.
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
        
        messages = []
        if req.system_prompt:
            messages.append({"role": "system", "content": req.system_prompt})
        messages.append({"role": "user", "content": req.prompt})
        
        body = {
            "model": model,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            **req.extra_params,
            **kwargs
        }
        
        headers = self._get_headers(credential)
        
        # Bounded retries: max 2 attempts for transient 503 or transient network errors
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    f"{endpoint}/chat/completions",
                    headers=headers,
                    json=body,
                    timeout=30,
                    allow_redirects=False
                )
                
                if response.status_code == 401:
                    return GenerationResult(
                        success=False,
                        error="Authentication rejected: Invalid API key",
                        error_type=ProviderErrorType.INVALID_CREDENTIAL
                    )
                
                if response.status_code == 429:
                    return GenerationResult(
                        success=False,
                        error="OpenAI rate limit exceeded",
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
                        error=f"OpenAI error (HTTP {response.status_code}): {err_msg}",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE if response.status_code < 500 else ProviderErrorType.CONNECTION_ERROR
                    )
                
                data = response.json()
                choices = data.get('choices', [])
                if not choices or not isinstance(choices, list):
                    return GenerationResult(
                        success=False,
                        error="Malformed response from OpenAI: 'choices' missing or empty",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE
                    )
                
                first_choice = choices[0]
                content = first_choice.get('message', {}).get('content', '')
                usage = data.get('usage', {})
                total_tokens = usage.get('total_tokens') if isinstance(usage, dict) else None
                
                return GenerationResult(
                    success=True,
                    content=content,
                    model_used=data.get('model', model),
                    tokens_used=total_tokens,
                    metadata={
                        'finish_reason': first_choice.get('finish_reason'),
                        'usage': usage,
                    }
                )
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return GenerationResult(
                    success=False,
                    error="OpenAI generation request timed out",
                    error_type=ProviderErrorType.TIMEOUT
                )
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                return GenerationResult(
                    success=False,
                    error="Connection error contacting OpenAI endpoint",
                    error_type=ProviderErrorType.CONNECTION_ERROR
                )
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI text generation: {e}")
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
        """Get list of available models from OpenAI."""
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
        """Get authenticated request headers."""
        return {
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json"
        }
