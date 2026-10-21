"""
Views for AI provider configuration and readiness dashboard.

Implements secure provider management, credential validation,
secret masking, and HTMX status updates without frontend framework dependencies.
"""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ProviderConfig
from .services.base_adapter import ProviderCapability
from .services.registry import registry
from .services.validation_service import CredentialValidationService

logger = logging.getLogger(__name__)


@login_required
def provider_dashboard(request):
    """
    Display user's AI provider configurations and readiness status.
    """
    text_config = ProviderConfig.objects.filter(
        user=request.user,
        capability='text',
        is_active=True
    ).first()
    
    image_config = ProviderConfig.objects.filter(
        user=request.user,
        capability='image',
        is_active=True
    ).first()
    
    text_cred = text_config.get_active_credential() if text_config else None
    image_cred = image_config.get_active_credential() if image_config else None
    
    # Check for canonical environment fallback if no database text config exists
    env_provider = None
    if not text_config:
        env_provider_info = registry.get_environment_text_provider()
        if env_provider_info:
            adapter, api_key, model_name, endpoint = env_provider_info
            masked_key = (
                f"{api_key[:4]}••••••••{api_key[-4:]}"
                if len(api_key) > 8 else "••••••••"
            )
            env_provider = {
                'adapter': adapter,
                'display_name': adapter.display_name,
                'model_name': model_name,
                'masked_key': masked_key,
                'endpoint': endpoint or adapter.default_endpoint,
            }
    
    available_text_providers = registry.get_providers_by_capability(ProviderCapability.TEXT_GENERATION)
    
    context = {
        'text_config': text_config,
        'image_config': image_config,
        'text_credential_masked': text_cred.get_masked_value() if text_cred else None,
        'image_credential_masked': image_cred.get_masked_value() if image_cred else None,
        'env_provider': env_provider,
        'available_text_providers': available_text_providers,
    }
    
    return render(request, 'ai_providers/dashboard.html', context)


@login_required
def configure_provider(request):
    """
    Configure a new or existing provider credential and endpoint.
    """
    capability = request.GET.get('capability', 'text')
    config_id = request.GET.get('config_id')
    
    existing_config = None
    if config_id:
        existing_config = get_object_or_404(ProviderConfig, pk=config_id, user=request.user)
        capability = existing_config.capability
    elif request.method == 'GET':
        existing_config = ProviderConfig.objects.filter(
            user=request.user,
            capability=capability,
            is_active=True
        ).first()

    if request.method == 'POST':
        capability = request.POST.get('capability', 'text')
        credential = request.POST.get('credential', '').strip()
        provider = request.POST.get('provider', '').strip()
        model_name = request.POST.get('model_name', '').strip()
        endpoint_url = request.POST.get('endpoint_url', '').strip()
        post_config_id = request.POST.get('config_id')

        # Prevent overwriting existing credential with empty input
        result = CredentialValidationService.validate_and_save(
            user=request.user,
            credential_value=credential if credential else None,
            capability=capability,
            provider_name=provider if provider and provider != 'auto' else None,
            endpoint=endpoint_url if endpoint_url else None,
            model_name=model_name if model_name else None,
            config_id=int(post_config_id) if post_config_id and post_config_id.isdigit() else (existing_config.pk if existing_config else None)
        )
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('ai_providers:dashboard')
        else:
            messages.error(request, result['error'])
            # Re-render with submitted parameters for quick correction
            cap_enum = (
                ProviderCapability.TEXT_GENERATION if capability == 'text'
                else ProviderCapability.IMAGE_GENERATION
            )
            available_providers = registry.get_providers_by_capability(cap_enum)
            context = {
                'capability': capability,
                'available_providers': available_providers,
                'existing_config': existing_config,
                'selected_provider': provider,
                'selected_model': model_name,
                'selected_endpoint': endpoint_url,
            }
            return render(request, 'ai_providers/configure.html', context)
    
    cap_enum = (
        ProviderCapability.TEXT_GENERATION if capability == 'text'
        else ProviderCapability.IMAGE_GENERATION
    )
    available_providers = registry.get_providers_by_capability(cap_enum)
    
    context = {
        'capability': capability,
        'available_providers': available_providers,
        'existing_config': existing_config,
        'selected_provider': existing_config.provider_name if existing_config else 'auto',
        'selected_model': existing_config.model_name if existing_config else '',
        'selected_endpoint': existing_config.endpoint_url if existing_config else '',
    }
    
    return render(request, 'ai_providers/configure.html', context)


@login_required
@require_POST
def validate_config(request, pk):
    """
    Re-validate an existing configuration (supports HTMX partial response).
    """
    config = get_object_or_404(ProviderConfig, pk=pk, user=request.user)
    validation = CredentialValidationService.validate_existing(config)
    
    if request.headers.get('HX-Request'):
        context = {
            'config': config,
            'validation': validation,
        }
        return render(request, 'ai_providers/partials/status.html', context)
    
    if validation.success:
        messages.success(request, validation.message)
    else:
        messages.error(request, validation.message)
    
    return redirect('ai_providers:dashboard')


@login_required
@require_POST
def remove_config(request, pk):
    """
    Remove an active provider configuration and delete associated credentials.
    """
    config = get_object_or_404(ProviderConfig, pk=pk, user=request.user)
    display_title = config.capability.title()
    provider_title = config.provider_name
    config.delete()
    messages.success(request, f"{display_title} provider configuration for '{provider_title}' removed successfully.")
    return redirect('ai_providers:dashboard')
