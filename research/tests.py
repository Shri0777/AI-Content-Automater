"""
Tests for research models and services.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from unittest.mock import Mock, patch, MagicMock
import feedparser

from research.models import ResearchProfile, ContentCreationRequest, Research
from research.services import RSSFeedService, GNewsService, RankingService
from content.models import Content
from users.models import UserProfile

User = get_user_model()


class ResearchProfileTests(TestCase):
    """Tests for ResearchProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
    
    def test_get_or_create_creates_with_defaults(self):
        """Test that get_or_create_for_user creates profile with V3 defaults."""
        profile = ResearchProfile.get_or_create_for_user(self.user)
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.topics, ['AI', 'software development', 'cloud', 'DevOps'])
        self.assertEqual(profile.audience, 'developers and technology learners')
        self.assertEqual(profile.content_goal, 'educational and informative')
        self.assertEqual(profile.freshness_days, 7)
        self.assertTrue(profile.allow_older_sources)
        self.assertEqual(profile.language, 'en')
        self.assertIn('documentation', profile.source_categories)
        self.assertIn('news', profile.source_categories)
    
    def test_get_or_create_returns_existing(self):
        """Test that get_or_create_for_user returns existing profile."""
        profile1 = ResearchProfile.get_or_create_for_user(self.user)
        profile1.topics = ['custom', 'topics']
        profile1.save()
        
        profile2 = ResearchProfile.get_or_create_for_user(self.user)
        
        self.assertEqual(profile1.pk, profile2.pk)
        self.assertEqual(profile2.topics, ['custom', 'topics'])
    
    def test_profile_can_be_updated(self):
        """Test that profile can be edited."""
        profile = ResearchProfile.get_or_create_for_user(self.user)
        
        profile.topics = ['new', 'topics']
        profile.freshness_days = 14
        profile.save()
        
        profile.refresh_from_db()
        self.assertEqual(profile.topics, ['new', 'topics'])
        self.assertEqual(profile.freshness_days, 14)


class ContentCreationRequestTests(TestCase):
    """Tests for ContentCreationRequest model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
        
        self.content = Content.objects.create(
            owner=self.user,
            title='Test Content',
            topic='Testing'
        )
    
    def test_create_from_profile_uses_defaults(self):
        """Test creating request from profile defaults."""
        profile = ResearchProfile.get_or_create_for_user(self.user)
        
        request = ContentCreationRequest.create_from_profile(
            user=self.user,
            content=self.content
        )
        
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.content, self.content)
        self.assertEqual(request.topics, profile.topics)
        self.assertEqual(request.audience, profile.audience)
        self.assertEqual(request.freshness_days, 7)
        self.assertEqual(request.status, 'configuring')
    
    def test_create_from_profile_with_overrides(self):
        """Test creating request with overrides."""
        profile = ResearchProfile.get_or_create_for_user(self.user)
        
        overrides = {
            'topics': ['override', 'topics'],
            'freshness_days': 14,
            'specific_query': 'Custom query'
        }
        
        request = ContentCreationRequest.create_from_profile(
            user=self.user,
            overrides=overrides
        )
        
        # Overridden fields
        self.assertEqual(request.topics, ['override', 'topics'])
        self.assertEqual(request.freshness_days, 14)
        self.assertEqual(request.specific_query, 'Custom query')
        
        # Non-overridden fields still use profile defaults
        self.assertEqual(request.audience, profile.audience)
        self.assertEqual(request.content_goal, profile.content_goal)
    
    def test_profile_unchanged_after_request_creation(self):
        """Test that profile defaults are not modified when creating request."""
        profile = ResearchProfile.get_or_create_for_user(self.user)
        original_topics = profile.topics.copy()
        
        overrides = {'topics': ['different', 'topics']}
        request = ContentCreationRequest.create_from_profile(
            user=self.user,
            overrides=overrides
        )
        
        profile.refresh_from_db()
        self.assertEqual(profile.topics, original_topics)
        self.assertNotEqual(profile.topics, request.topics)


class ResearchModelTests(TestCase):
    """Tests for Research model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=self.user)
    
    def test_research_creation(self):
        """Test creating research item."""
        research = Research.objects.create(
            owner=self.user,
            entry_type='rss',
            title='Test Article',
            summary='Test summary',
            url='https://example.com/article',
            canonical_url='https://example.com/article',
            source_name='Example Source',
            published_date=timezone.now(),
            relevance_score=0.8,
            overall_score=0.75
        )
        
        self.assertEqual(research.owner, self.user)
        self.assertEqual(research.title, 'Test Article')
        self.assertFalse(research.is_selected)
        self.assertFalse(research.is_excluded)
    
    def test_is_fresh_within_window(self):
        """Test is_fresh returns True for recent content."""
        recent_date = timezone.now() - timedelta(days=3)
        research = Research.objects.create(
            owner=self.user,
            title='Recent',
            summary='Summary',
            url='https://example.com/1',
            canonical_url='https://example.com/1',
            source_name='Source',
            published_date=recent_date
        )
        
        self.assertTrue(research.is_fresh(days=7))
    
    def test_is_fresh_outside_window(self):
        """Test is_fresh returns False for old content."""
        old_date = timezone.now() - timedelta(days=30)
        research = Research.objects.create(
            owner=self.user,
            title='Old',
            summary='Summary',
            url='https://example.com/2',
            canonical_url='https://example.com/2',
            source_name='Source',
            published_date=old_date
        )
        
        self.assertFalse(research.is_fresh(days=7))
    
    def test_is_fresh_no_date(self):
        """Test is_fresh returns False when no published_date."""
        research = Research.objects.create(
            owner=self.user,
            title='No Date',
            summary='Summary',
            url='https://example.com/3',
            canonical_url='https://example.com/3',
            source_name='Source',
            published_date=None
        )
        
        self.assertFalse(research.is_fresh(days=7))


class RSSFeedServiceTests(TestCase):
    """Tests for RSSFeedService."""
    
    def setUp(self):
        self.service = RSSFeedService(timeout=5, max_entries=10)
    
    def test_url_safety_blocks_private_ips(self):
        """Test that private IP addresses are blocked."""
        private_urls = [
            'http://127.0.0.1/feed.xml',
            'http://192.168.1.1/rss',
            'http://10.0.0.1/feed',
            'http://172.16.0.1/rss'
        ]
        
        for url in private_urls:
            self.assertFalse(self.service._is_safe_url(url))
    
    def test_url_safety_blocks_non_http(self):
        """Test that non-HTTP(S) schemes are blocked."""
        unsafe_urls = [
            'file:///etc/passwd',
            'ftp://example.com/feed',
            'javascript:alert(1)'
        ]
        
        for url in unsafe_urls:
            self.assertFalse(self.service._is_safe_url(url))
    
    def test_url_safety_allows_public_https(self):
        """Test that public HTTPS URLs are allowed."""
        # Note: This test may fail if DNS resolution fails
        # In production tests, mock the DNS resolution
        with patch('socket.gethostbyname', return_value='93.184.216.34'):  # example.com IP
            result = self.service._is_safe_url('https://example.com/feed.xml')
            self.assertTrue(result)
    
    @patch('feedparser.parse')
    def test_fetch_feed_handles_malformed(self, mock_parse):
        """Test handling of malformed feeds."""
        mock_feed = Mock()
        mock_feed.bozo = True
        mock_feed.bozo_exception = Exception('Parse error')
        mock_feed.entries = []
        # Don't set status attribute to avoid hasattr check
        mock_parse.return_value = mock_feed
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.is_redirect = False
        mock_response.is_permanent_redirect = False
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b'<rss></rss>']
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda self, *args: None
        with patch.object(self.service, '_is_safe_url', return_value=True), patch('research.services.rss_parser.requests.get', return_value=mock_response):
            result = self.service.fetch_feed('https://example.com/feed.xml')
        
        self.assertIn('error', result)
        self.assertEqual(len(result['entries']), 0)
    
    @patch('feedparser.parse')
    def test_fetch_feed_success(self, mock_parse):
        """Test successful feed parsing."""
        # Create a mock entry that behaves like a feedparser entry
        # feedparser entries support both dict-like access and attribute access
        class MockEntry:
            def __init__(self):
                self.link = 'https://example.com/article1'
                self.title = 'Article 1'
                self.summary = 'Summary 1'
                self.published_parsed = None
            
            def get(self, key, default=''):
                return getattr(self, key, default)
            
            def __contains__(self, key):
                return hasattr(self, key)
        
        mock_entry = MockEntry()
        
        # Mock feed
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': 'Test Feed'}
        mock_feed.entries = [mock_entry]
        mock_parse.return_value = mock_feed
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.is_redirect = False
        mock_response.is_permanent_redirect = False
        mock_response.headers = {}
        mock_response.iter_content.return_value = [b'<rss></rss>']
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda self, *args: None
        with patch.object(self.service, '_is_safe_url', return_value=True), patch('research.services.rss_parser.requests.get', return_value=mock_response):
            result = self.service.fetch_feed('https://example.com/feed.xml')
        
        self.assertIsNone(result['error'])
        self.assertEqual(result['feed_title'], 'Test Feed')
        self.assertEqual(len(result['entries']), 1)
        self.assertEqual(result['entries'][0]['title'], 'Article 1')


class GNewsServiceTests(TestCase):
    """Tests for GNewsService."""
    
    def test_is_configured_without_key(self):
        """Test service reports not configured without API key."""
        service = GNewsService(api_key=None)
        self.assertFalse(service.is_configured())
    
    def test_is_configured_with_key(self):
        """Test service reports configured with API key."""
        service = GNewsService(api_key='test_key')
        self.assertTrue(service.is_configured())
    
    def test_search_without_key_returns_error(self):
        """Test search without API key returns error."""
        service = GNewsService(api_key=None)
        result = service.search('test query')
        
        self.assertIn('error', result)
        self.assertIn('not configured', result['error'])
        self.assertEqual(len(result['entries']), 0)
    
    @patch('requests.get')
    def test_search_handles_auth_failure(self, mock_get):
        """Test handling of authentication failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        service = GNewsService(api_key='invalid_key')
        result = service.search('test query')
        
        self.assertIn('error', result)
        self.assertIn('authentication failed', result['error'].lower())
    
    @patch('requests.get')
    def test_search_handles_rate_limit(self, mock_get):
        """Test handling of rate limit."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response
        
        service = GNewsService(api_key='test_key')
        result = service.search('test query')
        
        self.assertIn('error', result)
        self.assertIn('rate limit', result['error'].lower())
    
    @patch('requests.get')
    def test_search_success(self, mock_get):
        """Test successful search."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'totalArticles': 1,
            'articles': [
                {
                    'title': 'Test Article',
                    'description': 'Test description',
                    'url': 'https://example.com/article',
                    'publishedAt': '2026-10-14T12:00:00Z',
                    'source': {
                        'name': 'Test Source',
                        'url': 'https://example.com'
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        service = GNewsService(api_key='test_key')
        result = service.search('test query', max_results=10, days=7)
        
        self.assertIsNone(result['error'])
        self.assertEqual(result['total_results'], 1)
        self.assertEqual(len(result['entries']), 1)
        self.assertEqual(result['entries'][0]['title'], 'Test Article')
        self.assertEqual(result['entries'][0]['entry_type'], 'gnews')


class RankingServiceTests(TestCase):
    """Tests for RankingService."""
    
    def setUp(self):
        self.service = RankingService()
    
    def test_weights_are_normalized(self):
        """Test that weights are normalized to sum to 1.0."""
        total = sum(self.service.weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)
    
    def test_canonicalize_url(self):
        """Test URL canonicalization."""
        # Remove tracking params
        url1 = 'https://example.com/page?utm_source=test&id=123'
        canonical1 = self.service._canonicalize_url(url1)
        self.assertNotIn('utm_source', canonical1)
        self.assertIn('id=123', canonical1)
        
        # Remove www
        url2 = 'https://www.example.com/page'
        canonical2 = self.service._canonicalize_url(url2)
        self.assertEqual(canonical2, 'https://example.com/page')
        
        # Remove fragment
        url3 = 'https://example.com/page#section'
        canonical3 = self.service._canonicalize_url(url3)
        self.assertNotIn('#', canonical3)
    
    def test_deduplication(self):
        """Test deduplication of entries with same canonical URL."""
        entries = [
            {
                'title': 'Article 1',
                'url': 'https://example.com/article?utm_source=twitter',
                'summary': 'Summary 1',
                'source_name': 'Source A',
                'published_date': timezone.now()
            },
            {
                'title': 'Article 1',
                'url': 'https://www.example.com/article?utm_campaign=test',
                'summary': 'Summary 1',
                'source_name': 'Source B',
                'published_date': timezone.now()
            },
            {
                'title': 'Article 2',
                'url': 'https://example.com/different',
                'summary': 'Summary 2',
                'source_name': 'Source C',
                'published_date': timezone.now()
            }
        ]
        
        result = self.service.deduplicate_and_rank(
            entries, 
            query='test',
            topics=['testing']
        )
        
        # Should have 2 unique articles
        self.assertEqual(len(result), 2)
        
        # First article should have source_count = 2
        article1 = [r for r in result if 'article' in r['canonical_url']][0]
        self.assertEqual(article1['source_count'], 2)
        self.assertEqual(len(article1['all_sources']), 2)
    
    def test_relevance_scoring(self):
        """Test relevance scoring."""
        entry = {
            'title': 'AI and Machine Learning Tutorial',
            'summary': 'A comprehensive guide to AI',
            'url': 'https://example.com/ai',
            'source_name': 'Tech Blog',
            'published_date': timezone.now()
        }
        
        scores = self.service._calculate_scores(
            entry,
            query='AI tutorial',
            topics=['machine learning'],
            freshness_days=7
        )
        
        # Should have high relevance (matches query and topics)
        self.assertGreater(scores['relevance'], 0.5)
    
    def test_freshness_scoring(self):
        """Test freshness scoring."""
        # Recent entry
        recent_entry = {
            'published_date': timezone.now() - timedelta(days=2),
            'title': 'Recent',
            'summary': 'Summary',
            'url': 'https://example.com/recent',
            'source_name': 'Source'
        }
        
        # Old entry
        old_entry = {
            'published_date': timezone.now() - timedelta(days=60),
            'title': 'Old',
            'summary': 'Summary',
            'url': 'https://example.com/old',
            'source_name': 'Source'
        }
        
        recent_scores = self.service._calculate_scores(recent_entry, '', [], 7)
        old_scores = self.service._calculate_scores(old_entry, '', [], 7)
        
        self.assertGreater(recent_scores['freshness'], old_scores['freshness'])
    
    def test_ranking_generates_rationale(self):
        """Test that ranking generates explanation."""
        entries = [
            {
                'title': 'Test Article',
                'summary': 'Test summary with keywords',
                'url': 'https://example.com/test',
                'source_name': 'Test Source',
                'published_date': timezone.now(),
                'author': 'Test Author'
            }
        ]
        
        result = self.service.deduplicate_and_rank(
            entries,
            query='test keywords',
            topics=['testing']
        )
        
        self.assertGreater(len(result), 0)
        self.assertIn('ranking_rationale', result[0])
        self.assertIsNotNone(result[0]['ranking_rationale'])



# ============================================================================
# VIEW TESTS
# ============================================================================

class ResearchProfileViewTests(TestCase):
    """Tests for research profile views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.profile = ResearchProfile.get_or_create_for_user(self.user)
    
    def test_profile_view_requires_login(self):
        """Test that profile view requires authentication."""
        self.client.logout()
        response = self.client.get(reverse('research:profile_view'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_profile_view_displays_profile(self):
        """Test that profile view displays user's profile."""
        response = self.client.get(reverse('research:profile_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research Profile')
        self.assertContains(response, 'developers and technology learners')
    
    def test_profile_edit_get(self):
        """Test that profile edit form loads correctly."""
        response = self.client.get(reverse('research:profile_edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Research Profile')
        self.assertContains(response, self.profile.audience)
    
    def test_profile_edit_post_updates_profile(self):
        """Test that profile edit form updates the profile."""
        response = self.client.post(reverse('research:profile_edit'), {
            'topics': 'machine learning, data science',
            'audience': 'data scientists',
            'content_goal': 'technical deep dives',
            'freshness_days': 14,
            'allow_older_sources': False,
            'language': 'en',
            'source_categories': ['news', 'research']
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after save
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.topics, ['machine learning', 'data science'])
        self.assertEqual(self.profile.audience, 'data scientists')
        self.assertEqual(self.profile.freshness_days, 14)
        self.assertFalse(self.profile.allow_older_sources)
    
    def test_profile_edit_validation(self):
        """Test that profile edit form validates input."""
        response = self.client.post(reverse('research:profile_edit'), {
            'topics': '',  # Invalid - empty
            'audience': 'test',
            'content_goal': 'test',
            'freshness_days': -1,  # Invalid - negative
            'language': 'en',
            'source_categories': []
        })
        
        self.assertEqual(response.status_code, 200)  # Re-render form with errors
        self.assertContains(response, 'At least one topic is required')


class ContentCreationRequestViewTests(TestCase):
    """Tests for content creation request views."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.profile = ResearchProfile.get_or_create_for_user(self.user)
    
    def test_request_new_get(self):
        """Test that request creation form loads with profile defaults."""
        response = self.client.get(reverse('research:request_new'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'New Research Request')
        self.assertContains(response, self.profile.audience)
    
    def test_request_new_post_creates_request(self):
        """Test that request creation form creates a request."""
        response = self.client.post(reverse('research:request_new'), {
            'topics': 'kubernetes, containers',
            'audience': 'DevOps engineers',
            'content_goal': 'practical tutorials',
            'freshness_days': 3,
            'allow_older_sources': True,
            'language': 'en',
            'source_categories': ['news', 'documentation'],
            'specific_query': 'kubernetes best practices'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect after creation
        
        request = ContentCreationRequest.objects.filter(user=self.user).first()
        self.assertIsNotNone(request)
        self.assertEqual(request.topics, ['kubernetes', 'containers'])
        self.assertEqual(request.specific_query, 'kubernetes best practices')
        self.assertEqual(request.status, 'configuring')
    
    def test_request_new_with_overrides(self):
        """Test that request overrides don't modify profile."""
        original_topics = self.profile.topics.copy()
        
        self.client.post(reverse('research:request_new'), {
            'topics': 'rust, systems programming',
            'audience': self.profile.audience,
            'content_goal': self.profile.content_goal,
            'freshness_days': 1,
            'language': 'en',
            'source_categories': ['news']
        })
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.topics, original_topics)
    
    def test_request_detail_displays_request(self):
        """Test that request detail view displays request info."""
        request = ContentCreationRequest.create_from_profile(
            self.user,
            overrides={'specific_query': 'test query'}
        )
        
        response = self.client.get(reverse('research:request_detail', args=[request.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Research Request')
        self.assertContains(response, 'test query')
    
    def test_request_detail_ownership_enforced(self):
        """Test that users can only view their own requests."""
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='pass123'
        )
        UserProfile.objects.create(user=other_user)
        other_profile = ResearchProfile.get_or_create_for_user(other_user)
        
        other_request = ContentCreationRequest.create_from_profile(other_user)
        
        response = self.client.get(reverse('research:request_detail', args=[other_request.pk]))
        self.assertEqual(response.status_code, 404)
    
    def test_request_list_displays_user_requests(self):
        """Test that request list shows only user's requests."""
        request1 = ContentCreationRequest.create_from_profile(self.user)
        request2 = ContentCreationRequest.create_from_profile(self.user)
        
        response = self.client.get(reverse('research:request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Request #{request1.pk}')
        self.assertContains(response, f'Request #{request2.pk}')


class ResearchExecutionViewTests(TestCase):
    """Tests for research execution views with mocked HTTP."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser@example.com',
            email='testuser@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
        self.client.login(username='testuser@example.com', password='testpass123')
        self.profile = ResearchProfile.get_or_create_for_user(self.user)
        self.request = ContentCreationRequest.create_from_profile(
            self.user,
            overrides={'specific_query': 'Django testing'}
        )
    
    @patch('research.views.GNewsService')
    @patch('research.views.RSSFeedService')
    def test_request_execute_success(self, mock_rss_class, mock_gnews_class):
        """Test successful research execution with mocked services."""
        # Mock RSS service
        mock_rss = MagicMock()
        mock_rss.fetch_feed.return_value = {
            'success': True,
            'entries': [
                {
                    'title': 'Django Testing Guide',
                    'summary': 'A comprehensive guide to testing',
                    'url': 'https://example.com/django-testing',
                    'source_name': 'Tech Blog',
                    'published_date': timezone.now(),
                    'author': 'Test Author'
                }
            ]
        }
        mock_rss_class.return_value = mock_rss
        
        # Mock GNews service
        mock_gnews = MagicMock()
        mock_gnews.search.return_value = {
            'success': True,
            'entries': [
                {
                    'title': 'Django 5.0 Released',
                    'summary': 'New features in Django',
                    'url': 'https://news.example.com/django-5',
                    'source_name': 'Tech News',
                    'published_date': timezone.now(),
                    'author': 'News Author'
                }
            ],
            'total_results': 1,
            'error': None
        }
        mock_gnews_class.return_value = mock_gnews
        
        response = self.client.post(reverse('research:request_execute', args=[self.request.pk]))
        
        self.assertEqual(response.status_code, 302)  # Redirect after execution
        
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'completed')
        
        # Check that research items were created
        research_items = Research.objects.filter(creation_request=self.request)
        self.assertGreater(research_items.count(), 0)
    
    @patch('research.views.GNewsService')
    @patch('research.views.RSSFeedService')
    def test_request_execute_partial_failure(self, mock_rss_class, mock_gnews_class):
        """Test research execution with partial failures."""
        # RSS succeeds
        mock_rss = MagicMock()
        mock_rss.fetch_feed.return_value = {
            'success': True,
            'entries': [
                {
                    'title': 'Test Article',
                    'summary': 'Test content',
                    'url': 'https://example.com/test',
                    'source_name': 'Test Source',
                    'published_date': timezone.now()
                }
            ]
        }
        mock_rss_class.return_value = mock_rss
        
        # GNews fails
        mock_gnews = MagicMock()
        mock_gnews.search.return_value = {
            'success': False,
            'error': 'API error'
        }
        mock_gnews_class.return_value = mock_gnews
        
        response = self.client.post(reverse('research:request_execute', args=[self.request.pk]))
        
        self.assertEqual(response.status_code, 302)
        
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'completed')  # Still completes with partial results
    
    @patch('research.views.GNewsService')
    @patch('research.views.RSSFeedService')
    def test_request_execute_complete_failure(self, mock_rss_class, mock_gnews_class):
        """Test research execution when all sources fail."""
        # Both services fail
        mock_rss = MagicMock()
        mock_rss.fetch_feed.return_value = {'success': False, 'error': 'RSS error'}
        mock_rss_class.return_value = mock_rss
        
        mock_gnews = MagicMock()
        mock_gnews.search.return_value = {'success': False, 'error': 'GNews error'}
        mock_gnews_class.return_value = mock_gnews
        
        response = self.client.post(reverse('research:request_execute', args=[self.request.pk]))
        
        self.assertEqual(response.status_code, 302)
        
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'failed')
    
    @patch('research.views.GNewsService')
    @patch('research.views.RSSFeedService')
    def test_request_execute_missing_optional_keys(self, mock_rss_class, mock_gnews_class):
        """Test that missing optional keys (e.g. error, entries) in service results don't raise KeyError."""
        mock_rss = MagicMock()
        # RSS result completely missing 'error' key
        mock_rss.fetch_feed.return_value = {
            'entries': [
                {
                    'title': 'Resilient Entry',
                    'summary': 'Summary of resilient entry',
                    'url': 'https://example.com/resilient',
                    'source_name': 'Resilient Source',
                    'published_date': timezone.now()
                }
            ]
        }
        mock_rss_class.return_value = mock_rss
        
        mock_gnews = MagicMock()
        # GNews result missing 'entries' and 'error' keys
        mock_gnews.search.return_value = {
            'total_results': 0
        }
        mock_gnews_class.return_value = mock_gnews
        
        response = self.client.post(reverse('research:request_execute', args=[self.request.pk]))
        self.assertEqual(response.status_code, 302)
        
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'completed')
        self.assertGreater(Research.objects.filter(creation_request=self.request).count(), 0)
    
    def test_research_select_toggle(self):
        """Test HTMX source selection toggle."""
        research = Research.objects.create(
            owner=self.user,
            creation_request=self.request,
            entry_type='rss',
            title='Test Article',
            url='https://example.com/test',
            canonical_url='https://example.com/test',
            source_name='Test Source',
            published_date=timezone.now(),
            overall_score=0.8
        )
        
        # Select the research item (with HTMX header)
        response = self.client.post(
            reverse('research:research_select', args=[research.pk]),
            {'action': 'select'},
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        
        research.refresh_from_db()
        self.assertTrue(research.is_selected)
        self.assertFalse(research.is_excluded)
        
        # Toggle to exclude
        response = self.client.post(
            reverse('research:research_select', args=[research.pk]),
            {'action': 'exclude'},
            HTTP_HX_REQUEST='true'
        )
        
        research.refresh_from_db()
        self.assertFalse(research.is_selected)
        self.assertTrue(research.is_excluded)
        
        # Toggle off
        response = self.client.post(
            reverse('research:research_select', args=[research.pk]),
            {'action': 'toggle'},
            HTTP_HX_REQUEST='true'
        )
        
        research.refresh_from_db()
        self.assertFalse(research.is_selected)
        self.assertFalse(research.is_excluded)
