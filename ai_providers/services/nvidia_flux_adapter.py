"""
NVIDIA FLUX image generation adapter.

Implements image generation using NVIDIA's black-forest-labs/flux-3-image-klein model.
"""
import logging
import time
from typing import Any, Dict, List, Optional
from io import BytesIO

import requests
from PIL import Image as PILImage

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


class NVIDIAFluxAdapter(BaseProviderAdapter):
    """
    NVIDIA FLUX image generation adapter using the NVIDIA API.
    
    Uses the documented NVIDIA API endpoint for black-forest-labs/flux-3-image-klein model.
    """
    
    @property
    def provider_name(self) -> str:
        return "nvidia_flux"
    
    @property
    def display_name(self) -> str:
        return "NVIDIA FLUX"
    
    @property
    def supported_capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability.IMAGE_GENERATION]
    
    @property
    def auth_method(self) -> AuthMethod:
        return AuthMethod.BEARER_TOKEN
    
    @property
    def default_endpoint(self) -> str:
        return "https://integrate.api.nvidia.com/v1"
    
    @property
    def default_model(self) -> str:
        return "black-forest-labs/flux-3-image-klein"
    
    @property
    def requires_model_name(self) -> bool:
        return True
    
    def identify_provider(
        self,
        credential: str,
        endpoint: Optional[str] = None
    ) -> bool:
        """
        Identify NVIDIA by checking if credential works with the NVIDIA API.
        """
        if not credential or not credential.strip():
            return False
            
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        is_safe, _ = validate_safe_endpoint(endpoint)
        if not is_safe:
            return False
        
        # Try to validate with a models endpoint or similar lightweight check
        try:
            headers = self._get_headers(credential)
            # NVIDIA API supports models endpoint
            response = requests.get(
                f"{endpoint}/models",
                headers=headers,
                timeout=5,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'data' in data:
                    models = [m.get('id', '') for m in data.get('data', []) if isinstance(m, dict)]
                    # Check for FLUX model presence
                    if any('flux' in m.lower() or 'black-forest' in m.lower() for m in models):
                        return True
            return False
        except Exception as e:
            logger.debug(f"NVIDIA FLUX identification check failed: {e}")
            return False
    
    def validate_credential(
        self,
        credential: str,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
        capability: Optional[ProviderCapability] = None
    ) -> ValidationResult:
        """
        Validate credential for NVIDIA FLUX image generation.
        """
        if not credential or not credential.strip():
            return ValidationResult(
                success=False,
                message="NVIDIA API key is required",
                error_type=ProviderErrorType.MISSING_CREDENTIAL
            )
        
        # Capability check
        if capability and capability not in self.supported_capabilities:
            return ValidationResult(
                success=False,
                message=f"NVIDIA FLUX adapter only supports image generation",
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
            
            # Check models endpoint to validate credential
            response = requests.get(
                f"{endpoint}/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                return ValidationResult(
                    success=False,
                    message="Authentication failed: Invalid NVIDIA API key",
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
                    message=f"NVIDIA API error: HTTP {response.status_code}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
            data = response.json()
            if not isinstance(data, dict) or 'data' not in data:
                return ValidationResult(
                    success=False,
                    message="Unexpected response schema from NVIDIA models endpoint",
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
                    capabilities=["image"]
                )
            
            return ValidationResult(
                success=True,
                message="NVIDIA FLUX credentials validated successfully",
                provider_identified="nvidia_flux",
                capabilities=["image"],
                model_available=target_model
            )
            
        except requests.exceptions.Timeout:
            return ValidationResult(
                success=False,
                message="Connection timed out while contacting NVIDIA API",
                error_type=ProviderErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return ValidationResult(
                success=False,
                message="Connection failed: Unable to reach NVIDIA endpoint",
                error_type=ProviderErrorType.CONNECTION_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected validation error in NVIDIAFluxAdapter: {e}")
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
        """NVIDIA FLUX does not support text generation."""
        return GenerationResult(
            success=False,
            error="NVIDIA FLUX adapter only supports image generation",
            error_type=ProviderErrorType.LACKS_CAPABILITY
        )
    
    def generate_image(
        self,
        prompt: str,
        credential: str,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """
        Generate image using NVIDIA FLUX model.
        
        Returns GenerationResult with:
        - success: bool
        - content: PIL Image object if successful
        - metadata: dict with generation details
        - error: error message if failed
        """
        if not prompt or not prompt.strip():
            return GenerationResult(
                success=False,
                error="Image prompt cannot be empty",
                error_type=ProviderErrorType.MALFORMED_RESPONSE
            )
        
        endpoint = (endpoint or self.default_endpoint).rstrip('/')
        model = model_name or self.default_model
        
        is_safe, reason = validate_safe_endpoint(endpoint)
        if not is_safe:
            return GenerationResult(
                success=False,
                error=f"Endpoint blocked by SSRF protection: {reason}",
                error_type=ProviderErrorType.SSRF_BLOCKED
            )
        
        # NVIDIA API uses images/generations endpoint similar to OpenAI
        # See: https://docs.api.nvidia.com/nim/reference/flux-1-1-klein
        body = {
            "model": model,
            "prompt": prompt,
            "n": 1,  # Number of images
            "size": kwargs.get("size", "1024x1024"),  # Image dimensions
        }
        
        # Add optional parameters if provided
        if "quality" in kwargs:
            body["quality"] = kwargs["quality"]
        if "style" in kwargs:
            body["style"] = kwargs["style"]
        
        headers = self._get_headers(credential)
        
        # Bounded retries for transient failures
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    f"{endpoint}/images/generations",
                    headers=headers,
                    json=body,
                    timeout=60,  # Image generation can take longer
                    allow_redirects=False
                )
                
                if response.status_code == 401:
                    return GenerationResult(
                        success=False,
                        error="Authentication rejected: Invalid NVIDIA API key",
                        error_type=ProviderErrorType.INVALID_CREDENTIAL
                    )
                
                if response.status_code == 429:
                    return GenerationResult(
                        success=False,
                        error="NVIDIA rate limit exceeded",
                        error_type=ProviderErrorType.RATE_LIMITED
                    )
                
                if response.status_code == 400:
                    try:
                        err_data = response.json()
                        err_msg = err_data.get('error', {}).get('message', response.text)
                    except Exception:
                        err_msg = response.text
                    return GenerationResult(
                        success=False,
                        error=f"Invalid request: {err_msg}",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE
                    )
                
                if response.status_code in (500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(1 * (attempt + 1))
                    continue
                
                if response.status_code != 200:
                    try:
                        err_data = response.json()
                        err_msg = err_data.get('error', {}).get('message', response.text)
                    except Exception:
                        err_msg = response.text
                    return GenerationResult(
                        success=False,
                        error=f"NVIDIA API error (HTTP {response.status_code}): {err_msg}",
                        error_type=ProviderErrorType.CONNECTION_ERROR if response.status_code >= 500 else ProviderErrorType.MALFORMED_RESPONSE
                    )
                
                data = response.json()
                
                # Parse response - NVIDIA API returns images in OpenAI-compatible format
                images_data = data.get('data', [])
                if not images_data or not isinstance(images_data, list):
                    return GenerationResult(
                        success=False,
                        error="Malformed response from NVIDIA: 'data' missing or empty",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE
                    )
                
                first_image = images_data[0]
                
                # Handle different response formats
                image_url = first_image.get('url')
                image_b64 = first_image.get('b64_json')
                
                if image_url:
                    # Download image from URL with safety checks
                    return self._download_image_safely(image_url, data)
                elif image_b64:
                    # Decode base64 image
                    return self._decode_base64_image(image_b64, data)
                else:
                    return GenerationResult(
                        success=False,
                        error="No image URL or base64 data in NVIDIA response",
                        error_type=ProviderErrorType.MALFORMED_RESPONSE
                    )
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return GenerationResult(
                    success=False,
                    error="NVIDIA image generation request timed out",
                    error_type=ProviderErrorType.TIMEOUT
                )
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    time.sleep(1)
                    continue
                return GenerationResult(
                    success=False,
                    error="Connection error contacting NVIDIA endpoint",
                    error_type=ProviderErrorType.CONNECTION_ERROR
                )
            except Exception as e:
                logger.error(f"Unexpected error in NVIDIA FLUX image generation: {e}")
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
    
    def _download_image_safely(self, image_url: str, response_data: Dict) -> GenerationResult:
        """
        Download image from URL with safety checks.
        """
        # Validate URL is safe
        is_safe, reason = validate_safe_endpoint(image_url)
        if not is_safe:
            return GenerationResult(
                success=False,
                error=f"Image URL blocked by SSRF protection: {reason}",
                error_type=ProviderErrorType.SSRF_BLOCKED
            )
        
        try:
            # Download with timeout and size limit
            response = requests.get(
                image_url,
                timeout=30,
                stream=True,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                return GenerationResult(
                    success=False,
                    error=f"Failed to download image: HTTP {response.status_code}",
                    error_type=ProviderErrorType.CONNECTION_ERROR
                )
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                return GenerationResult(
                    success=False,
                    error=f"Invalid content type: {content_type}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
            # Read with size limit (10MB max)
            max_size = 10 * 1024 * 1024
            content = BytesIO()
            total_size = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    total_size += len(chunk)
                    if total_size > max_size:
                        return GenerationResult(
                            success=False,
                            error="Image size exceeds 10MB limit",
                            error_type=ProviderErrorType.MALFORMED_RESPONSE
                        )
                    content.write(chunk)
            
            content.seek(0)
            
            # Load and validate image
            try:
                image = PILImage.open(content)
                image.verify()  # Verify it's a valid image
                content.seek(0)
                image = PILImage.open(content)  # Reopen after verify
                
                return GenerationResult(
                    success=True,
                    content=image,
                    model_used=response_data.get('model', self.default_model),
                    metadata={
                        'format': image.format,
                        'size': image.size,
                        'mode': image.mode,
                        'revised_prompt': response_data.get('revised_prompt'),
                    }
                )
            except Exception as e:
                return GenerationResult(
                    success=False,
                    error=f"Invalid image data: {str(e)}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
                
        except requests.exceptions.Timeout:
            return GenerationResult(
                success=False,
                error="Timeout downloading generated image",
                error_type=ProviderErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return GenerationResult(
                success=False,
                error="Connection error downloading image",
                error_type=ProviderErrorType.CONNECTION_ERROR
            )
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return GenerationResult(
                success=False,
                error=f"Failed to download image: {str(e)}",
                error_type=ProviderErrorType.UNKNOWN
            )
    
    def _decode_base64_image(self, b64_data: str, response_data: Dict) -> GenerationResult:
        """
        Decode base64 image data.
        """
        try:
            import base64
            
            image_bytes = base64.b64decode(b64_data)
            
            # Check size limit (10MB)
            if len(image_bytes) > 10 * 1024 * 1024:
                return GenerationResult(
                    success=False,
                    error="Image size exceeds 10MB limit",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
            
            content = BytesIO(image_bytes)
            
            # Load and validate image
            try:
                image = PILImage.open(content)
                image.verify()
                content.seek(0)
                image = PILImage.open(content)
                
                return GenerationResult(
                    success=True,
                    content=image,
                    model_used=response_data.get('model', self.default_model),
                    metadata={
                        'format': image.format,
                        'size': image.size,
                        'mode': image.mode,
                        'revised_prompt': response_data.get('revised_prompt'),
                    }
                )
            except Exception as e:
                return GenerationResult(
                    success=False,
                    error=f"Invalid image data: {str(e)}",
                    error_type=ProviderErrorType.MALFORMED_RESPONSE
                )
                
        except Exception as e:
            logger.error(f"Error decoding base64 image: {e}")
            return GenerationResult(
                success=False,
                error=f"Failed to decode image: {str(e)}",
                error_type=ProviderErrorType.UNKNOWN
            )
    
    def _get_headers(self, credential: str) -> Dict[str, str]:
        """Get authenticated request headers."""
        return {
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json"
        }
