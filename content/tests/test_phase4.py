"""
Phase 4 Test Suite: Evidence-Grounded Content Generation, Quality Review, and Bounded Correction.

Covers:
- ContentGenerationService: Grounded generation, evidence mapping, error handling
- QualityReviewService: Stage 1 & Stage 2 reviews, dimensional rubrics, deterministic fallback
- ContentCorrectionService: Automated revisions, bounded limit enforcement (FR-010)
- Traceability: ResearchContentAssociation citation tracking
- Immutability & Approval: Explicit human approval, material edit invalidation
- Views & Authorization: request_generate_content, trigger_review, apply_correction, approve_version, IDOR checks
"""
import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ai_providers.models import ProviderConfig, ProviderCredential
from ai_providers.services.base_adapter import GenerationRequest, GenerationResult
from content.models import Content, ContentReview, ContentVersion
from content.services.correction_service import MAX_AUTOMATED_REVISIONS, ContentCorrectionService
from content.services.generation_service import ContentGenerationService
from content.services.review_service import QualityReviewService
from research.models import ContentCreationRequest, Research, ResearchContentAssociation
from users.models import UserProfile

User = get_user_model()


class Phase4ServiceTests(TestCase):
    """Unit and integration tests for Phase 4 services."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='author@example.com',
            email='author@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.other_user = User.objects.create_user(
            username='stranger@example.com',
            email='stranger@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.other_user)

        # Create ContentCreationRequest
        self.creation_request = ContentCreationRequest.objects.create(
            user=self.user,
            topics=['Django Architecture', 'PostgreSQL'],
            audience='Software Engineers',
            content_goal='Educational deep-dive',
            freshness_days=7,
            language='en',
            source_categories=['news', 'tech'],
            status='researching'
        )

        # Create Research Items
        self.r1 = Research.objects.create(
            owner=self.user,
            creation_request=self.creation_request,
            entry_type='rss',
            title='Understanding PostgreSQL Trigger Immutability',
            summary='PostgreSQL triggers can enforce append-only immutable versions efficiently.',
            url='https://postgres.org/triggers',
            canonical_url='https://postgres.org/triggers',
            overall_score=0.92,
            is_selected=True
        )
        self.r2 = Research.objects.create(
            owner=self.user,
            creation_request=self.creation_request,
            entry_type='gnews',
            title='Django 5.1 Architecture Patterns',
            summary='Clean domain service patterns improve testability in Django applications.',
            url='https://djangoproject.com/patterns',
            canonical_url='https://djangoproject.com/patterns',
            overall_score=0.88,
            is_selected=True
        )
        self.r_unselected = Research.objects.create(
            owner=self.user,
            creation_request=self.creation_request,
            entry_type='rss',
            title='Random Irrelevant Post',
            summary='Not relevant.',
            overall_score=0.20,
            is_selected=False
        )

        # Set up a mock adapter
        self.mock_adapter = MagicMock()
        self.mock_adapter.provider_name = 'mock_openai'

    @patch('ai_providers.services.validation_service.CredentialValidationService.get_active_provider_for_user')
    def test_content_generation_success(self, mock_get_provider):
        """Test successful evidence-grounded draft generation and Stage 1 review."""
        mock_get_provider.return_value = (self.mock_adapter, 'sk-test', 'gpt-4o', None)

        generated_text = (
            "Title: Mastering Immutable Architecture in Django\n\n"
            "Immutable patterns provide bulletproof audit trails in database systems [1]. "
            "By pairing PostgreSQL trigger enforcement with clean service boundaries in Django [2], "
            "engineering teams can build highly reliable data pipelines without regressions."
        )
        self.mock_adapter.generate_text.return_value = GenerationResult(
            success=True,
            content=generated_text,
            tokens_used=120,
            model_used='gpt-4o'
        )

        result = ContentGenerationService.generate_draft_for_request(
            creation_request_id=self.creation_request.pk,
            user=self.user
        )

        self.assertTrue(result['success'])
        content = result['content']
        version = result['version']
        review = result['review']

        self.assertEqual(content.title, "Mastering Immutable Architecture in Django")
        self.assertEqual(content.owner, self.user)
        self.assertEqual(version.version_number, 1)
        self.assertFalse(version.is_approved)  # Must start unapproved
        self.assertEqual(content.current_version, version)

        # Verify evidence traceability
        associations = ResearchContentAssociation.objects.filter(content=content)
        self.assertEqual(associations.count(), 2)
        citation_indices = set(associations.values_list('citation_index', flat=True))
        self.assertEqual(citation_indices, {1, 2})

        # Verify Stage 1 review was executed
        self.assertIsNotNone(review)
        self.assertEqual(review.content_version, version)
        self.assertEqual(review.stage, 1)
        self.assertEqual(review.status, 'passed')

        # Verify creation request status updated
        self.creation_request.refresh_from_db()
        self.assertEqual(self.creation_request.status, 'completed')
        self.assertEqual(self.creation_request.content, content)

    def test_generation_missing_evidence(self):
        """Generation fails cleanly when no research evidence exists."""
        empty_request = ContentCreationRequest.objects.create(
            user=self.user,
            topics=['AI'],
            audience='engineers',
            content_goal='educational',
            freshness_days=7,
            language='en',
            source_categories=['tech'],
            status='researching'
        )
        result = ContentGenerationService.generate_draft_for_request(
            creation_request_id=empty_request.pk,
            user=self.user
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'missing_evidence')

    def test_generation_unauthorized_user(self):
        """Generation fails when requested by a different user."""
        result = ContentGenerationService.generate_draft_for_request(
            creation_request_id=self.creation_request.pk,
            user=self.other_user
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'not_found')

    @patch('ai_providers.services.validation_service.CredentialValidationService.get_active_provider_for_user')
    def test_generation_no_provider_configured(self, mock_get_provider):
        """Generation handles absence of active AI provider gracefully."""
        mock_get_provider.return_value = (None, None, None, None)

        result = ContentGenerationService.generate_draft_for_request(
            creation_request_id=self.creation_request.pk,
            user=self.user
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'no_provider')

    @patch('ai_providers.services.validation_service.CredentialValidationService.get_active_provider_for_user')
    def test_generation_provider_failure(self, mock_get_provider):
        """Generation reports provider failure without crashing."""
        mock_get_provider.return_value = (self.mock_adapter, 'sk-test', 'gpt-4o', None)
        self.mock_adapter.generate_text.return_value = GenerationResult(
            success=False,
            error="Rate limit exceeded",
            error_type="rate_limited"
        )

        result = ContentGenerationService.generate_draft_for_request(
            creation_request_id=self.creation_request.pk,
            user=self.user
        )
        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'rate_limited')
        self.creation_request.refresh_from_db()
        self.assertEqual(self.creation_request.status, 'failed')

    def test_deterministic_review_and_hallucination_penalty(self):
        """Review service applies penalties to hallucinated citations in deterministic fallback."""
        content = Content.objects.create(
            owner=self.user,
            title="Citation Test",
            lifecycle_state='in_progress'
        )
        # Content cites [1] and [99] (hallucinated citation)
        text_with_bad_citation = (
            "Here is a claim backed by source [1]. "
            "Here is another claim citing hallucinated source [99] which does not exist."
        )
        version = ContentVersion.create_initial_version(
            content=content,
            created_by=self.user,
            content_text=text_with_bad_citation
        )
        content.current_version = version
        content.save()

        # Link only source [1]
        ResearchContentAssociation.objects.create(
            research=self.r1,
            content=content,
            content_version=version,
            associated_by=self.user,
            citation_index=1
        )

        # Execute deterministic review (no adapter provided)
        review = QualityReviewService.review_version(
            content_version=version,
            stage=1,
            user=self.user,
            provider_adapter=None
        )

        self.assertIsNotNone(review)
        self.assertEqual(review.stage, 1)
        # Should flag invalid citation [99]
        self.assertTrue(any('99' in finding for finding in review.findings))
        self.assertTrue(len(review.unsupported_claims) > 0)
        self.assertEqual(review.evidence_support_rating, 'Medium')

    @patch('ai_providers.services.validation_service.CredentialValidationService.get_active_provider_for_user')
    def test_bounded_correction_limit(self, mock_get_provider):
        """Test that automated corrections are strictly bounded to MAX_AUTOMATED_REVISIONS (2)."""
        mock_get_provider.return_value = (self.mock_adapter, 'sk-test', 'gpt-4o', None)

        content = Content.objects.create(
            owner=self.user,
            title="Correction Limit Test",
            lifecycle_state='in_progress'
        )
        v1 = ContentVersion.create_initial_version(
            content=content,
            created_by=self.user,
            content_text="Draft needing revision."
        )
        content.current_version = v1
        content.save()

        # Attach initial review with findings
        ContentReview.objects.create(
            content_version=v1,
            stage=1,
            status='needs_revision',
            score=0.60,
            findings=["Needs clearer citations."],
            unsupported_claims=[]
        )

        self.mock_adapter.generate_text.return_value = GenerationResult(
            success=True,
            content="Corrected text addressing review.",
            tokens_used=100
        )

        # 1st Correction (Should succeed -> Revision 1)
        res1 = ContentCorrectionService.apply_bounded_correction(content.pk, self.user)
        self.assertTrue(res1['success'])
        self.assertEqual(res1['revisions_used'], 1)
        self.assertEqual(res1['revisions_remaining'], 1)
        self.assertEqual(res1['version'].version_number, 2)
        self.assertFalse(res1['version'].is_approved)
        self.assertIn('Automated revision 1', res1['version'].change_summary)

        # 2nd Correction (Should succeed -> Revision 2)
        res2 = ContentCorrectionService.apply_bounded_correction(content.pk, self.user)
        self.assertTrue(res2['success'])
        self.assertEqual(res2['revisions_used'], 2)
        self.assertEqual(res2['revisions_remaining'], 0)
        self.assertEqual(res2['version'].version_number, 3)
        self.assertFalse(res2['version'].is_approved)
        self.assertIn('Automated revision 2', res2['version'].change_summary)

        # 3rd Correction (MUST fail with limit_reached error per FR-010)
        res3 = ContentCorrectionService.apply_bounded_correction(content.pk, self.user)
        self.assertFalse(res3['success'])
        self.assertEqual(res3['error_type'], 'limit_reached')
        self.assertIn("Maximum automated correction limit reached", res3['error'])


class Phase4ViewTests(TestCase):
    """View-level integration and security tests for Phase 4."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner@example.com',
            email='owner@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.owner)

        self.attacker = User.objects.create_user(
            username='attacker@example.com',
            email='attacker@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.attacker)

        self.creation_request = ContentCreationRequest.objects.create(
            user=self.owner,
            topics=['AI Engineering'],
            audience='engineers',
            content_goal='educational',
            freshness_days=7,
            language='en',
            source_categories=['tech'],
            status='researching'
        )
        self.research = Research.objects.create(
            owner=self.owner,
            creation_request=self.creation_request,
            title='AI Engineering Fundamentals',
            summary='Key principles for building AI products.',
            overall_score=0.90,
            is_selected=True
        )

        self.content = Content.objects.create(
            owner=self.owner,
            title='Production AI Architecture',
            topic='AI Engineering',
            lifecycle_state='in_progress'
        )
        self.v1 = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.owner,
            content_text='Initial draft [1] regarding AI systems.'
        )
        self.content.current_version = self.v1
        self.content.save()

        self.assoc = ResearchContentAssociation.objects.create(
            research=self.research,
            content=self.content,
            content_version=self.v1,
            associated_by=self.owner,
            citation_index=1
        )

    def test_request_generate_content_requires_login(self):
        """Unauthenticated user cannot generate content."""
        response = self.client.post(
            reverse('research:request_generate_content', kwargs={'pk': self.creation_request.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/login/', response.url)

    @patch('content.services.generation_service.ContentGenerationService.generate_draft_for_request')
    def test_request_generate_content_success(self, mock_generate):
        """Owner can generate content and is redirected to content detail."""
        self.client.login(username='owner@example.com', password='testpass123')
        mock_generate.return_value = {
            'success': True,
            'content': self.content,
            'version': self.v1,
            'evidence_count': 1
        }

        response = self.client.post(
            reverse('research:request_generate_content', kwargs={'pk': self.creation_request.pk}),
            {'custom_instructions': 'Be concise'}
        )
        self.assertRedirects(response, reverse('content:detail', kwargs={'pk': self.content.pk}))

    def test_trigger_review_forbidden_for_non_owner(self):
        """Attacker cannot trigger review on another user's content."""
        self.client.login(username='attacker@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:trigger_review', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_trigger_review_success_for_owner(self):
        """Owner can trigger quality review."""
        self.client.login(username='owner@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:trigger_review', kwargs={'pk': self.content.pk})
        )
        self.assertRedirects(response, reverse('content:detail', kwargs={'pk': self.content.pk}))
        self.assertEqual(self.v1.reviews.count(), 1)

    def test_apply_correction_forbidden_for_non_owner(self):
        """Attacker cannot apply correction to another user's content."""
        self.client.login(username='attacker@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:apply_correction', kwargs={'pk': self.content.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_approve_version_workflow(self):
        """Explicit human approval sets is_approved and transitions state."""
        self.client.login(username='owner@example.com', password='testpass123')
        self.content.lifecycle_state = 'pending_review'
        self.content.save()

        self.assertFalse(self.v1.is_approved)

        response = self.client.post(
            reverse('content:approve_version', kwargs={'pk': self.content.pk}),
            {'version_number': self.v1.version_number}
        )
        self.assertRedirects(response, reverse('content:detail', kwargs={'pk': self.content.pk}))

        self.v1.refresh_from_db()
        self.content.refresh_from_db()
        self.assertTrue(self.v1.is_approved)
        self.assertEqual(self.content.lifecycle_state, 'approved')

    def test_material_edit_invalidates_approval(self):
        """A material edit resets an approved content back to in_progress."""
        self.client.login(username='owner@example.com', password='testpass123')
        self.content.lifecycle_state = 'approved'
        self.content.save()
        self.v1.is_approved = True
        self.v1.save(update_fields=['is_approved'])

        # Create new version through edit view
        response = self.client.post(
            reverse('content:edit', kwargs={'pk': self.content.pk}),
            {
                'title': 'Updated Title',
                'topic': 'AI Engineering',
                'create_version': 'true',
                'content_text': 'Material edit to text.',
                'change_summary': 'Manual rewrite'
            }
        )
        self.assertRedirects(response, reverse('content:detail', kwargs={'pk': self.content.pk}))

        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'in_progress')
        new_version = self.content.current_version
        self.assertEqual(new_version.version_number, 2)
        self.assertFalse(new_version.is_approved)

    def test_detail_view_renders_evidence_and_review(self):
        """Content detail view renders evidence associations and review info."""
        self.client.login(username='owner@example.com', password='testpass123')
        ContentReview.objects.create(
            content_version=self.v1,
            stage=1,
            status='passed',
            score=0.88,
            findings=["Well grounded."],
            unsupported_claims=[]
        )

        response = self.client.get(reverse('content:detail', kwargs={'pk': self.content.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research Evidence &amp; Grounding")
        self.assertContains(response, "AI Engineering Fundamentals")
        self.assertContains(response, "AI Quality Review")
        self.assertContains(response, "Bounded AI Correction")
        self.assertContains(response, "Revisions Used: 0 / 2")

    @patch('content.services.generation_service.ContentGenerationService.generate_draft_for_request')
    def test_request_generate_content_failure_redirects(self, mock_generate):
        """When draft generation fails, view redirects back to request detail with error message."""
        self.client.login(username='owner@example.com', password='testpass123')
        mock_generate.return_value = {
            'success': False,
            'error': 'Missing evidence sources',
            'error_type': 'missing_evidence'
        }

        response = self.client.post(
            reverse('research:request_generate_content', kwargs={'pk': self.creation_request.pk}),
            {'custom_instructions': ''}
        )
        self.assertRedirects(response, reverse('research:request_detail', kwargs={'pk': self.creation_request.pk}))

    def test_approve_version_forbidden_for_attacker(self):
        """Attacker cannot approve another user's content version."""
        self.client.login(username='attacker@example.com', password='testpass123')
        response = self.client.post(
            reverse('content:approve_version', kwargs={'pk': self.content.pk}),
            {'version_number': self.v1.version_number}
        )
        self.assertEqual(response.status_code, 403)


class Phase4ModelAndReviewDetailsTests(TestCase):
    """Tests for ContentReview models, AI review parsing, and error branches."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='eval@example.com',
            email='eval@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)

        self.content = Content.objects.create(
            owner=self.user,
            title='AI Review Model Test',
            lifecycle_state='in_progress'
        )
        self.version = ContentVersion.create_initial_version(
            content=self.content,
            created_by=self.user,
            content_text='Evaluation draft citing source [1].'
        )
        self.content.current_version = self.version
        self.content.save()

        self.research = Research.objects.create(
            owner=self.user,
            title='Verified Research Item',
            summary='Solid empirical findings.',
            overall_score=0.95
        )
        self.assoc = ResearchContentAssociation.objects.create(
            research=self.research,
            content=self.content,
            content_version=self.version,
            associated_by=self.user,
            citation_index=1,
            relevance_note='Primary source'
        )

    def test_models_str_representations(self):
        """Test __str__ representations of ContentReview and ResearchContentAssociation."""
        review = ContentReview.objects.create(
            content_version=self.version,
            stage=1,
            status='passed',
            score=0.91
        )
        self.assertIn("v1", str(review))
        self.assertIn("Stage 1", str(review))
        self.assertIn("passed", str(review))

        self.assertIn(self.research.title, str(self.assoc))
        self.assertIn("[1]", str(self.assoc))

    def test_ai_review_parsing_with_json(self):
        """Test QualityReviewService parsing successful AI structured critique."""
        mock_adapter = MagicMock()
        mock_adapter.provider_name = 'openai'
        mock_json_content = json.dumps({
            'score': 0.89,
            'relevance_rating': 'High',
            'evidence_support_rating': 'High',
            'factual_consistency_rating': 'High',
            'clarity_rating': 'High',
            'findings': ['Clear structure and good citation density.'],
            'unsupported_claims': [],
            'summary': 'High quality evidence-grounded draft.'
        })
        mock_adapter.generate_text.return_value = GenerationResult(
            success=True,
            content=f"```json\n{mock_json_content}\n```",
            tokens_used=150
        )

        review = QualityReviewService.review_version(
            content_version=self.version,
            stage=1,
            user=self.user,
            provider_adapter=mock_adapter,
            credential='test-key'
        )

        self.assertEqual(review.status, 'passed')
        self.assertEqual(review.score, 0.89)
        self.assertEqual(review.relevance_rating, 'High')
        self.assertEqual(review.evidence_support_rating, 'High')
        self.assertEqual(len(review.findings), 1)
        self.assertEqual(len(review.unsupported_claims), 0)

        # Lifecycle transitioned to pending_review on passed review
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'pending_review')

    def test_ai_review_failing_score(self):
        """Test QualityReviewService marks status as needs_revision if score < 0.75."""
        mock_adapter = MagicMock()
        mock_adapter.provider_name = 'openai'
        mock_json_content = json.dumps({
            'score': 0.62,
            'relevance_rating': 'Medium',
            'evidence_support_rating': 'Low',
            'factual_consistency_rating': 'Medium',
            'clarity_rating': 'Medium',
            'findings': ['Insufficient source citations.'],
            'unsupported_claims': ['Claim about 10x performance gain not in sources.'],
            'summary': 'Draft requires revision and evidence support.'
        })
        mock_adapter.generate_text.return_value = GenerationResult(
            success=True,
            content=mock_json_content,
            tokens_used=140
        )

        review = QualityReviewService.review_version(
            content_version=self.version,
            stage=1,
            user=self.user,
            provider_adapter=mock_adapter,
            credential='test-key'
        )

        self.assertEqual(review.status, 'needs_revision')
        self.assertEqual(review.score, 0.62)
        self.assertEqual(review.evidence_support_rating, 'Low')
        self.assertEqual(len(review.unsupported_claims), 1)

        # Content state remains in_progress
        self.content.refresh_from_db()
        self.assertEqual(self.content.lifecycle_state, 'in_progress')

