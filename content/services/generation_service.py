"""
Content generation service for AI Content Automater V2 (Phase 4).

Generates evidence-grounded social and educational content using research sources,
user research profiles, and the Phase 3 provider adapter.
"""
import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from ai_providers.services.base_adapter import GenerationRequest
from ai_providers.services.validation_service import CredentialValidationService
from content.models import Content, ContentVersion
from research.models import ContentCreationRequest, Research, ResearchContentAssociation

from .review_service import QualityReviewService

logger = logging.getLogger(__name__)
User = get_user_model()


class ContentGenerationService:
    """
    Orchestrates evidence-grounded content generation from selected research items.
    """
    
    @staticmethod
    def generate_draft_for_request(
        creation_request_id: int,
        user: Any,
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a content draft from the research items of a ContentCreationRequest.
        
        Args:
            creation_request_id: PK of the ContentCreationRequest
            user: Authenticated user (ownership verified)
            custom_instructions: Optional extra prompt instructions
            
        Returns:
            Dict with success, content, version, review, or error details.
        """
        creation_request = ContentCreationRequest.objects.filter(
            pk=creation_request_id,
            user=user
        ).first()
        
        if not creation_request:
            return {
                'success': False,
                'error': 'Research request not found or unauthorized.',
                'error_type': 'not_found'
            }
        
        # 1. Gather research evidence
        # Prioritize items marked as selected by user
        research_qs = Research.objects.filter(
            creation_request=creation_request,
            owner=user,
            is_excluded=False
        )
        
        selected_sources = list(research_qs.filter(is_selected=True).order_by('-overall_score'))
        if not selected_sources:
            # Fall back to top 5 ranked available sources if user hasn't toggled specific selections
            selected_sources = list(research_qs.order_by('-overall_score')[:5])
        
        if not selected_sources:
            return {
                'success': False,
                'error': 'No research sources available. Please collect or select research before generating content.',
                'error_type': 'missing_evidence'
            }
        
        # 2. Resolve active AI provider (user config with canonical env fallback)
        adapter, credential, model_name, endpoint = CredentialValidationService.get_active_provider_for_user(
            user=user,
            capability='text'
        )
        
        if not adapter or not credential:
            return {
                'success': False,
                'error': 'No active AI text provider configured. Please configure OpenAI or Anthropic in AI Settings.',
                'error_type': 'no_provider'
            }
        
        # 3. Construct evidence-grounded prompt
        evidence_text, evidence_mapping = ContentGenerationService._format_evidence(selected_sources)
        
        topics_str = ', '.join(creation_request.topics) if creation_request.topics else 'Technology & Software'
        audience_str = creation_request.audience or 'developers and technology learners'
        goal_str = creation_request.content_goal or 'educational and informative'
        
        system_prompt = (
            "You are an expert technical content writer and educator. "
            "Your task is to write high-quality, clear, engaging social media and blog content "
            "grounded STRICTLY in the supplied research evidence.\n\n"
            "STRICT GROUNDING RULES:\n"
            "1. Base all factual statements, statistics, and conclusions EXCLUSIVELY on the provided sources.\n"
            "2. Never hallucinate, invent claims, fabricate quotes, or make unverified claims.\n"
            "3. Cite supporting sources in the text using bracketed references like [1], [2].\n"
            "4. If sources conflict or evidence is preliminary, explicitly note the uncertainty.\n"
            "5. If evidence is insufficient to answer an aspect, acknowledge the limitation.\n"
            "6. Provide a compelling Title on the first line (starting with 'Title: ')."
        )
        
        user_prompt = (
            f"Topic: {topics_str}\n"
            f"Target Audience: {audience_str}\n"
            f"Content Goal: {goal_str}\n"
        )
        if creation_request.specific_query:
            user_prompt += f"Specific Focus: {creation_request.specific_query}\n"
        if custom_instructions:
            user_prompt += f"Additional Guidance: {custom_instructions}\n"
            
        user_prompt += (
            f"\n--- RESEARCH EVIDENCE ---\n"
            f"{evidence_text}\n"
            f"--- END EVIDENCE ---\n\n"
            f"Write an informative, original post tailored to {audience_str}. "
            f"Ground your points in the research items above and include bracketed citations like [1], [2]."
        )
        
        # 4. Generate content via provider adapter
        creation_request.status = 'generating'
        creation_request.save(update_fields=['status', 'updated_at'])
        
        gen_request = GenerationRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model_name=model_name,
            endpoint=endpoint,
            max_tokens=1500,
            temperature=0.6
        )
        
        gen_result = adapter.generate_text(gen_request, credential=credential)
        
        if not gen_result.success:
            creation_request.status = 'failed'
            creation_request.error_message = gen_result.error
            creation_request.error_type = gen_result.error_type or 'generation_failed'
            creation_request.save(update_fields=['status', 'error_message', 'error_type', 'updated_at'])
            return {
                'success': False,
                'error': f"AI generation failed: {gen_result.error}",
                'error_type': gen_result.error_type or 'generation_failed'
            }
        
        generated_raw = gen_result.content or ''
        title, body = ContentGenerationService._parse_title_and_body(generated_raw, topics_str)
        
        # 5. Persist Content and ContentVersion
        content = creation_request.content
        if not content:
            content = Content.objects.create(
                owner=user,
                title=title,
                topic=topics_str,
                lifecycle_state='in_progress'
            )
            creation_request.content = content
            creation_request.save(update_fields=['content'])
        else:
            content.title = title
            content.topic = topics_str
            if content.lifecycle_state == 'draft':
                content.lifecycle_state = 'in_progress'
            content.save()
        
        # Create immutable version snapshot
        if content.versions.exists():
            version = ContentVersion.create_next_version(
                content=content,
                created_by=user,
                content_text=body,
                change_summary=f"AI generated draft grounded in {len(selected_sources)} research sources"
            )
        else:
            version = ContentVersion.create_initial_version(
                content=content,
                created_by=user,
                content_text=body,
                change_summary=f"Initial AI generated draft grounded in {len(selected_sources)} research sources"
            )
        
        content.current_version = version
        content.save(update_fields=['current_version', 'updated_at'])
        
        # 6. Record Evidence Traceability Associations
        for idx, research_item in evidence_mapping.items():
            ResearchContentAssociation.objects.update_or_create(
                research=research_item,
                content=content,
                content_version=version,
                defaults={
                    'associated_by': user,
                    'citation_index': idx,
                    'relevance_note': f"Cited as [{idx}] in draft: {research_item.title}"
                }
            )
        
        # 7. Execute Mandatory AI Quality Review Stage 1 (FR-007, BR-002)
        creation_request.status = 'reviewing'
        creation_request.save(update_fields=['status', 'updated_at'])
        
        review = QualityReviewService.review_version(
            content_version=version,
            stage=1,
            user=user,
            provider_adapter=adapter,
            credential=credential,
            model_name=model_name,
            endpoint=endpoint
        )
        
        creation_request.status = 'completed'
        creation_request.completed_at = timezone.now()
        creation_request.error_message = None
        creation_request.error_type = None
        creation_request.save(update_fields=['status', 'completed_at', 'error_message', 'error_type', 'updated_at'])
        
        from content.models import WorkflowAuditLog
        WorkflowAuditLog.objects.create(
            content=content,
            content_version=version,
            user=user,
            event_type='draft_generated',
            from_state='in_progress',
            to_state=content.lifecycle_state,
            message=f"Generated draft '{content.title}' v{version.version_number} grounded in {len(selected_sources)} sources.",
            details={'evidence_count': len(selected_sources), 'review_score': review.score}
        )
        
        return {
            'success': True,
            'content': content,
            'version': version,
            'review': review,
            'evidence_count': len(selected_sources)
        }
    
    @staticmethod
    def _format_evidence(sources: List[Research]) -> tuple[str, Dict[int, Research]]:
        """Format research items with numbered citation markers."""
        lines = []
        mapping = {}
        for i, s in enumerate(sources, start=1):
            mapping[i] = s
            pub_date = s.published_date.strftime("%Y-%m-%d") if s.published_date else "Recent"
            lines.append(
                f"[{i}] Title: {s.title}\n"
                f"    Source: {s.source_name} ({pub_date})\n"
                f"    URL: {s.canonical_url or s.url}\n"
                f"    Summary: {s.summary}\n"
            )
        return "\n".join(lines), mapping
    
    @staticmethod
    def _parse_title_and_body(raw_text: str, fallback_topic: str) -> tuple[str, str]:
        """Extract title from raw text and return clean title and body."""
        lines = raw_text.strip().splitlines()
        title = fallback_topic
        body_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower().startswith('title:'):
                title = stripped[6:].strip().strip('*').strip('"')
                body_lines = lines[i+1:]
                break
            elif stripped.startswith('# '):
                title = stripped[2:].strip()
                body_lines = lines[i+1:]
                break
        
        if not body_lines:
            body_lines = lines
            
        body = "\n".join(body_lines).strip()
        if not title:
            title = f"Insights on {fallback_topic}"
            
        return title[:255], body
