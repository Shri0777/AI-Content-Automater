# OpenAI & NVIDIA FLUX Integration Guide

## Overview

The AI Content Automater now supports:
1. **Text Generation**: OpenAI-compatible chat completions API (OpenAI, NVIDIA NIM)
2. **Image Generation**: NVIDIA FLUX.3 (black-forest-labs/flux-3-image-klein)

Both integrations are production-ready with full test coverage, secure credential management, and end-to-end UI support.

## Table of Contents

1. [Configuration](#configuration)
2. [Text Generation Setup](#text-generation-setup)
3. [Image Generation Setup](#image-generation-setup)
4. [Usage](#usage)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)
7. [Docker Deployment](#docker-deployment)

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# Text Generation (OpenAI-compatible)
TEXT_PROVIDER=openai  # openai|nvidia|anthropic|auto
TEXT_API_KEY=your-api-key-here
TEXT_API_BASE_URL=https://api.openai.com/v1  # Optional, defaults based on provider
TEXT_MODEL=gpt-4o-mini  # Optional, provider-specific default used if blank

# Image Generation (NVIDIA FLUX)
IMAGE_PROVIDER=nvidia_flux  # nvidia_flux|auto
IMAGE_API_KEY=your-nvidia-api-key-here
IMAGE_MODEL=black-forest-labs/flux-3-image-klein
```

### Credential Encryption

The application uses Fernet encryption for stored credentials. Ensure you have:

```bash
CREDENTIAL_ENCRYPTION_KEY=your-fernet-key-here
```

Generate a key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Text Generation Setup

### Option 1: OpenAI

1. **Obtain API Key**: Visit https://platform.openai.com/api-keys
2. **Configure**:
   ```bash
   TEXT_PROVIDER=openai
   TEXT_API_KEY=sk-...
   TEXT_API_BASE_URL=https://api.openai.com/v1
   TEXT_MODEL=gpt-4o-mini  # Or gpt-4o, gpt-3.5-turbo
   ```

3. **Supported Models**:
   - `gpt-4o` - Latest GPT-4 Omni model
   - `gpt-4o-mini` - Faster, more affordable variant
   - `gpt-3.5-turbo` - Cost-effective option
   - `gpt-4-turbo` - Previous generation flagship

### Option 2: NVIDIA NIM (OpenAI-compatible)

1. **Obtain API Key**: Visit https://build.nvidia.com/
2. **Configure**:
   ```bash
   TEXT_PROVIDER=nvidia
   TEXT_API_KEY=nvapi-...
   TEXT_API_BASE_URL=https://integrate.api.nvidia.com/v1
   TEXT_MODEL=meta/llama3-70b-instruct  # Or other NVIDIA-hosted models
   ```

3. **Supported Models** (via NVIDIA):
   - `meta/llama3-70b-instruct` - Meta's Llama 3 70B
   - `meta/llama3-8b-instruct` - Meta's Llama 3 8B
   - `openai/gpt-oss-20b` - NVIDIA's OpenAI-compatible model
   - `qwen/qwen3-235b-a22b` - Qwen 3 235B model

### Provider Selection Logic

1. **User Configuration First**: If user configures a provider in AI Settings dashboard
2. **Environment Fallback**: Uses `TEXT_PROVIDER` and `TEXT_API_KEY` if no user config
3. **Auto-Detection**: When `TEXT_PROVIDER=auto`, attempts to identify provider from endpoint

## Image Generation Setup

### NVIDIA FLUX.3

1. **Obtain API Key**: Visit https://build.nvidia.com/
   - Navigate to "Image Generation" section
   - Enable FLUX.3 API access
   - Generate API key

2. **Configure**:
   ```bash
   IMAGE_PROVIDER=nvidia_flux
   IMAGE_API_KEY=nvapi-...
   IMAGE_MODEL=black-forest-labs/flux-3-image-klein
   ```

3. **Model Details**:
   - **Model**: black-forest-labs/flux-3-image-klein
   - **Endpoint**: https://integrate.api.nvidia.com/v1/images/generations
   - **Supported Sizes**: 1024x1024, 1792x1024, 1024x1792
   - **Response Time**: 5-15 seconds typically
   - **Output**: High-quality promotional images

## Usage

### Configuring Providers in UI

1. **Navigate to AI Settings**: Click "AI Providers" in the navigation
2. **Configure Text Provider**:
   - Click "Configure Provider"
   - Select "Text Generation"
   - Choose provider (OpenAI, NVIDIA, etc.)
   - Enter API key
   - Set endpoint (if custom)
   - Select model
   - Click "Test Connection" to verify
   - Save configuration

3. **Configure Image Provider**:
   - Same process, select "Image Generation"
   - Choose "NVIDIA FLUX"
   - Enter NVIDIA API key
   - Model is pre-configured
   - Test and save

### Generating Content (Text)

1. **Create Content**: Click "Create Content"
2. **Add Details**: Title, topic, description
3. **Generate**: System uses configured text provider
4. **Review**: AI quality review stages run automatically
5. **Approve**: Review and approve for publishing

### Generating Images

1. **Open Content**: Navigate to content detail page
2. **Image Generation Section**: Scroll to "AI Image Generation"
3. **Enter Prompt**: Describe the image you want
   - Example: "A modern tech workspace with clean design and blue accents"
4. **Configure Options** (optional):
   - Size: Square, Landscape, or Portrait
   - Quality: Standard or HD
   - Style: Vivid or Natural
5. **Generate**: Click "Generate Image"
6. **View Results**: Generated images appear in "Associated Media" below

### Image Best Practices

**Good Prompts**:
- "Professional office environment with natural lighting and plants"
- "Abstract technology background with blue and purple gradients"
- "Modern workspace with laptop, coffee, and minimalist design"

**Avoid**:
- Vague prompts: "Nice image" or "Something cool"
- Excessive detail: Keep prompts focused and descriptive
- Prohibited content: Violence, explicit content, copyrighted characters

## Testing

### Test Provider Connections

```bash
# Activate virtual environment
source venv/bin/activate

# Test text provider
python manage.py shell
>>> from ai_providers.services.validation_service import CredentialValidationService
>>> from ai_providers.services.registry import registry
>>> adapter, cred, model, ep = registry.get_environment_text_provider()
>>> print(f"Text Provider: {adapter.display_name if adapter else 'Not configured'}")

# Test image provider
>>> adapter, cred, model, ep = registry.get_environment_image_provider()
>>> print(f"Image Provider: {adapter.display_name if adapter else 'Not configured'}")
```

### Run Automated Tests

```bash
# Run all tests
python manage.py test --keepdb

# Run provider-specific tests
python manage.py test ai_providers.tests.NVIDIATextAdapterTests --keepdb
python manage.py test ai_providers.tests.NVIDIAFluxAdapterTests --keepdb
python manage.py test content.tests.test_image_generation_views --keepdb

# Run image generation service tests
python manage.py test ai_providers.tests.ImageGenerationServiceTests --keepdb
```

## Troubleshooting

### Text Generation Issues

**Error: "No active AI provider configured"**
- Check `TEXT_API_KEY` is set in `.env`
- Verify `TEXT_PROVIDER` is set correctly
- Check provider dashboard for configuration status

**Error: "Authentication failed"**
- Verify API key is valid and active
- Check key has correct prefix (sk- for OpenAI, nvapi- for NVIDIA)
- Ensure no extra spaces or quotes in `.env`

**Error: "Model not found"**
- Check model name matches provider's available models
- OpenAI: Use `gpt-4o`, `gpt-4o-mini`, or `gpt-3.5-turbo`
- NVIDIA: Use models from their catalog

**Timeout Issues**:
- Default timeout is 60 seconds
- Large responses may take longer
- Check network connectivity
- Consider using smaller models for faster responses

### Image Generation Issues

**Error: "No active AI image provider configured"**
- Check `IMAGE_API_KEY` is set
- Verify `IMAGE_PROVIDER=nvidia_flux`
- Test connection in AI Settings dashboard

**Error: "Image generation failed"**
- Check NVIDIA API key is valid
- Verify account has FLUX.3 access enabled
- Check prompt doesn't violate content policies
- Ensure prompt is not empty

**Error: "Image download failed"**
- Network connectivity issue
- Temporary NVIDIA service issue
- Retry after a few moments

**Slow Generation**:
- Normal range: 5-15 seconds
- HD quality takes longer than standard
- Larger image sizes take more time
- NVIDIA API may have queue during peak times

### Provider Dashboard Issues

**Error: "Credential validation failed"**
- Invalid API key format
- Key expired or revoked
- Network connectivity issue
- Endpoint URL incorrect

**Status shows "Not tested"**:
- Connection not yet tested
- Click "Test Connection" button
- Wait for validation to complete

## Docker Deployment

### Environment Variables in Docker

Update your `docker-compose.yml` or create `.env.docker`:

```bash
# Copy example
cp .env.example .env.docker

# Edit with your keys
vim .env.docker

# Ensure Docker Compose uses the file
docker-compose --env-file .env.docker up
```

### Build and Run

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f web
docker-compose logs -f worker

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Restart after config changes
docker-compose restart web worker beat
```

### Volume Management

Media files (generated images) are persisted in Docker volumes:

```bash
# List volumes
docker volume ls | grep ai-automater

# Backup media files
docker run --rm -v ai-automater_media:/data -v $(pwd):/backup alpine tar czf /backup/media-backup.tar.gz /data

# Restore media files
docker run --rm -v ai-automater_media:/data -v $(pwd):/backup alpine tar xzf /backup/media-backup.tar.gz -C /
```

### Production Considerations

1. **Secrets Management**:
   - Use Docker secrets or environment injection
   - Never commit real keys to Git
   - Rotate keys periodically

2. **Resource Limits**:
   - Text generation: 512MB-1GB RAM per worker
   - Image generation: 1-2GB RAM (includes download/processing)
   - Adjust `docker-compose.yml` resources as needed

3. **Monitoring**:
   - Monitor Celery queue lengths
   - Track image generation success rates
   - Set up alerts for provider failures

4. **Scaling**:
   - Multiple worker containers for parallel generation
   - Separate queues for text and image generation
   - Redis cluster for high availability

## API Rate Limits

### OpenAI
- **Free Tier**: 3 requests/minute
- **Pay-as-you-go**: Varies by model
- **Rate limit errors**: Automatically retried with backoff

### NVIDIA
- **Free Tier**: 100 requests/day
- **Paid Tier**: Higher limits with subscription
- **FLUX.3**: Typically no strict per-minute limit

## Cost Estimates

### Text Generation (per 1,000 requests)

**OpenAI**:
- GPT-4o-mini: ~$0.15 (input) + ~$0.60 (output)
- GPT-4o: ~$5.00 (input) + ~$15.00 (output)

**NVIDIA**:
- Free tier: $0
- Paid tier: Varies by model

### Image Generation (per 100 images)

**NVIDIA FLUX.3**:
- Free tier: $0 (within daily limit)
- Standard quality: ~$0.04 per image (paid)
- HD quality: ~$0.08 per image (paid)

## Security Best Practices

1. **Never commit API keys**: Use `.env` files (git-ignored)
2. **Rotate keys regularly**: Every 90 days minimum
3. **Use environment-specific keys**: Different keys for dev/staging/production
4. **Monitor usage**: Set up billing alerts
5. **Restrict keys**: Use API key restrictions when available
6. **Audit access**: Review who has access to keys
7. **Use encryption**: All stored credentials are Fernet-encrypted

## Support

For issues:
1. Check logs: `docker-compose logs -f web worker`
2. Verify configuration: AI Settings dashboard
3. Test connection: Use "Test Connection" buttons
4. Review documentation: This guide
5. Check provider status: OpenAI/NVIDIA status pages

## Additional Resources

- **OpenAI Documentation**: https://platform.openai.com/docs
- **NVIDIA Documentation**: https://docs.nvidia.com/ai/
- **NVIDIA Build**: https://build.nvidia.com/
- **Django Documentation**: https://docs.djangoproject.com/
- **Celery Documentation**: https://docs.celeryproject.org/
