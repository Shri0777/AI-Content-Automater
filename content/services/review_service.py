"""
Quality review service for AI Content Automater V2 (Phase 4).

Implements mandatory AI Review Stages 1 & 2 (FR-007, FR-009, BR-002) evaluating:
- Relevance to topic and audience
- Evidence support and source traceability
- Factual consistency with supplied sources
- Clarity, educational value, and readability
- Unsupported claims and invented references
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from django.utils import timezone

from ai_providers.services.base_adapter import GenerationRequest
from ai_providers.services.validation_service import CredentialValidationService
from content.models import ContentReview, ContentVersion
from research.models import ResearchContentAssociation

logger = logging.getLogger(__name__)


class QualityReviewService:
    """
    Evaluates generated content versions against evidence and quality rubrics.
    """
    
    @staticmethod
    def review_version(
        content_version: ContentVersion,
        stage: int = 1,
        user: Optional[Any] = None,
        provider_adapter: Optional[Any] = None,
        credential: Optional[str] = None,
        model_name: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> ContentReview:
        """
        Execute automated quality review on a specific ContentVersion.
        
        Args:
            content_version: The ContentVersion to review
            stage: Review stage (1=initial, 2=post-correction)
            user: Content owner
            provider_adapter, credential, model_name, endpoint: Optional AI provider info
            
        Returns:
            Persisted ContentReview record.
        """
        content = content_version.content
        review_user = user or content.owner
        
        # 1. Fetch associated evidence
        associations = list(
            ResearchContentAssociation.objects.filter(
                content=content
            ).select_related('research')
        )
        
        # 2. Extract citations from content text
        content_text = content_version.content_text or ""
        cited_indices = set(re.findall(r'\[(\d+)\]', content_text))
        
        # 3. Resolve AI provider if not passed
        if not provider_adapter or not credential:
            provider_adapter, credential, model_name, endpoint = CredentialValidationService.get_active_provider_for_user(
                user=review_user,
                capability='text'
            )
        
        # 4. Perform review (AI-assisted with deterministic fallback)
        review_data = QualityReviewService._evaluate_content(
            content_text=content_text,
            topic=content.topic or content.title,
            associations=associations,
            cited_indices=cited_indices,
            adapter=provider_adapter,
            credential=credential,
            model_name=model_name,
            endpoint=endpoint
        )
        
        # 5. Determine status
        score = review_data['score']
        has_critical_unsupported = len(review_data['unsupported_claims']) > 0 and review_data['evidence_support_rating'] == 'Low'
        
        if score >= 0.75 and not has_critical_unsupported:
            status = 'passed'
        else:
            status = 'needs_revision'
        
        # 6. Persist ContentReview
        review = ContentReview.objects.create(
            content_version=content_version,
            stage=stage,
            status=status,
            score=round(score, 2),
            relevance_rating=review_data['relevance_rating'],
            evidence_support_rating=review_data['evidence_support_rating'],
            factual_consistency_rating=review_data['factual_consistency_rating'],
            clarity_rating=review_data['clarity_rating'],
            findings=review_data['findings'],
            unsupported_claims=review_data['unsupported_claims'],
            summary=review_data['summary'],
            reviewed_by_provider=provider_adapter.provider_name if provider_adapter else 'rules_engine',
            model_name=model_name
        )
        
        # 7. Update content lifecycle state if review passes and content is in_progress
        if status == 'passed' and content.lifecycle_state == 'in_progress':
            try:
                content.transition_to('pending_review')
            except Exception as e:
                logger.debug(f"Lifecycle transition to pending_review skipped: {e}")

        from content.models import WorkflowAuditLog
        WorkflowAuditLog.objects.create(
            content=content,
            content_version=content_version,
            user=review_user,
            event_type=f"review_stage_{stage}",
            from_state=content.lifecycle_state,
            to_state=content.lifecycle_state,
            message=f"AI Quality Review Stage {stage} completed: {status.upper()} (Score: {review.score:.2f}).",
            details={'stage': stage, 'status': status, 'score': review.score, 'findings_count': len(review.findings)}
        )
        
        return review
    
    @staticmethod
    def _evaluate_content(
        content_text: str,
        topic: str,
        associations: List[ResearchContentAssociation],
        cited_indices: set,
        adapter: Optional[Any],
        credential: Optional[str],
        model_name: Optional[str],
        endpoint: Optional[str]
    ) -> Dict[str, Any]:
        """Run analytical AI evaluation or deterministic fallback."""
        if adapter and credential:
            try:
                ai_eval = QualityReviewService._run_ai_evaluation(
                    content_text=content_text,
                    topic=topic,
                    associations=associations,
                    adapter=adapter,
                    credential=credential,
                    model_name=model_name,
                    endpoint=endpoint
                )
                if ai_eval:
                    return ai_eval
            except Exception as e:
                logger.warning(f"AI quality review evaluation failed, falling back to deterministic rules: {e}")
        
        # Deterministic rule-based evaluation fallback
        return QualityReviewService._run_deterministic_evaluation(
            content_text=content_text,
            topic=topic,
            associations=associations,
            cited_indices=cited_indices
        )
    
    @staticmethod
    def _run_ai_evaluation(
        content_text: str,
        topic: str,
        associations: List[ResearchContentAssociation],
        adapter: Any,
        credential: str,
        model_name: Optional[str],
        endpoint: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Query AI provider to produce a structured critique JSON."""
        evidence_snippets = []
        for a in associations:
            r = a.research
            evidence_snippets.append(
                f"[{a.citation_index}] {r.title} ({r.source_name}): {r.summary}"
            )
        evidence_str = "\n".join(evidence_snippets)
        
        prompt = (
            f"Review the following draft for factual evidence grounding and quality.\n\n"
            f"Topic: {topic}\n\n"
            f"Supplied Evidence:\n{evidence_str}\n\n"
            f"Draft Text to Review:\n{content_text}\n\n"
            f"Analyze strictly against the supplied evidence. Respond ONLY with valid JSON in this exact structure:\n"
            f"{{\n"
            f'  "score": 0.85,\n'
            f'  "relevance_rating": "High",\n'
            f'  "evidence_support_rating": "High",\n'
            f'  "factual_consistency_rating": "High",\n'
            f'  "clarity_rating": "High",\n'
            f'  "findings": ["Finding 1", "Finding 2"],\n'
            f'  "unsupported_claims": [],\n'
            f'  "summary": "Executive summary of evaluation."\n'
            f"}}"
        )
        
        system_prompt = (
            "You are a strict, objective editorial reviewer and fact checker. "
            "You verify whether content is rigorously supported by provided sources. "
            "Never invent facts or validate claims not supported by the evidence."
        )
        
        req = GenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model_name=model_name,
            endpoint=endpoint,
            max_tokens=800,
            temperature=0.2
        )
        
        res = adapter.generate_text(req, credential=credential)
        if not res.success or not res.content:
            return None
        
        # Parse JSON from response
        text = res.content.strip()
        # Find json bounds if surrounded by markdown code fences
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        data = json.loads(text)
        return {
            'score': float(data.get('score', 0.8)),
            'relevance_rating': str(data.get('relevance_rating', 'High')),
            'evidence_support_rating': str(data.get('evidence_support_rating', 'High')),
            'factual_consistency_rating': str(data.get('factual_consistency_rating', 'High')),
            'clarity_rating': str(data.get('clarity_rating', 'High')),
            'findings': list(data.get('findings', [])),
            'unsupported_claims': list(data.get('unsupported_claims', [])),
            'summary': str(data.get('summary', 'Review completed successfully.'))
        }
    
    @staticmethod
    def _run_deterministic_evaluation(
        content_text: str,
        topic: str,
        associations: List[ResearchContentAssociation],
        cited_indices: set
    ) -> Dict[str, Any]:
        """Evaluate content using deterministic heuristics and citation analysis."""
        findings = []
        unsupported = []
        
        # Check citations
        if not cited_indices:
            findings.append("No bracketed source citations ([1], [2]) detected in the text.")
            evidence_support = "Low"
            score = 0.55
        else:
            valid_indices = {str(a.citation_index) for a in associations}
            hallucinated_citations = cited_indices - valid_indices
            if hallucinated_citations:
                findings.append(f"Citations {sorted(hallucinated_citations)} do not match any supplied research sources.")
                unsupported.append(f"Invalid source markers: {sorted(hallucinated_citations)}")
                evidence_support = "Medium"
                score = 0.68
            else:
                findings.append(f"Properly grounded with {len(cited_indices)} verified source citations.")
                evidence_support = "High"
                score = 0.88
        
        # Check text length / substance
        word_count = len(content_text.split())
        if word_count < 40:
            findings.append("Draft is very short; consider expanding with more detail from the sources.")
            clarity = "Medium"
            score -= 0.1
        elif word_count > 600:
            findings.append("Draft exceeds standard social media length; consider tightening key points.")
            clarity = "Medium"
        else:
            clarity = "High"
            
        # Topic check
        topic_words = set(topic.lower().split())
        content_lower = content_text.lower()
        if any(w in content_lower for w in topic_words if len(w) > 3):
            relevance = "High"
        else:
            relevance = "Medium"
            findings.append(f"Ensure the draft clearly highlights core keywords related to '{topic}'.")
            
        summary = (
            f"Review completed ({evidence_support} evidence support). "
            f"Draft contains {word_count} words and {len(cited_indices)} source citations."
        )
        
        return {
            'score': max(0.1, min(1.0, score)),
            'relevance_rating': relevance,
            'evidence_support_rating': evidence_support,
            'factual_consistency_rating': 'High' if not unsupported else 'Medium',
            'clarity_rating': clarity,
            'findings': findings,
            'unsupported_claims': unsupported,
            'summary': summary
        }
