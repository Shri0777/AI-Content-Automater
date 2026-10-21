"""
Google News (GNews) integration service.
Uses GNews API with proper error handling, rate limiting, and authentication.
"""
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GNewsService:
    """
    GNews API integration for research collection.
    
    Handles:
    - Authentication with API key
    - Rate limiting
    - Error handling (auth failures, quotas, timeouts)
    - Result normalization
    """
    
    BASE_URL = 'https://gnews.io/api/v4/search'
    
    def __init__(self, api_key: Optional[str] = None, timeout=10):
        """
        Initialize GNews service.
        
        Args:
            api_key: GNews API key (from environment)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
    
    def is_configured(self) -> bool:
        """Check if service is properly configured with API key."""
        return bool(self.api_key)
    
    def search(self, query: str, language: str = 'en', 
               max_results: int = 10, days: int = 7) -> Dict:
        """
        Search Google News for articles.
        
        Args:
            query: Search query
            language: Language code (e.g., 'en')
            max_results: Maximum results to return (API限制 max 10 for free tier)
            days: Look back this many days
        
        Returns:
            {
                'entries': List[Dict],  # Normalized entries
                'total_results': int,
                'error': Optional[str]
            }
        """
        if not self.is_configured():
            return {
                'entries': [],
                'total_results': 0,
                'error': 'GNews API key not configured. Set GNEWS_API_KEY environment variable.'
            }
        
        # Enforce rate limiting
        self._rate_limit()
        
        try:
            # Build request parameters
            params = {
                'q': query,
                'lang': language,
                'max': min(max_results, 10),  # Free tier limit
                'apikey': self.api_key,
            }
            
            # Add date range if specified
            if days > 0:
                from_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
                params['from'] = from_date
            
            # Make request
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
                headers={'User-Agent': 'AI-Content-Automater/2.0'}
            )
            
            # Check for HTTP errors
            if response.status_code == 401:
                return {
                    'entries': [],
                    'total_results': 0,
                    'error': 'GNews API authentication failed. Check your API key.'
                }
            elif response.status_code == 403:
                return {
                    'entries': [],
                    'total_results': 0,
                    'error': 'GNews API access forbidden. Verify API key permissions.'
                }
            elif response.status_code == 429:
                return {
                    'entries': [],
                    'total_results': 0,
                    'error': 'GNews API rate limit exceeded. Try again later.'
                }
            elif response.status_code >= 400:
                return {
                    'entries': [],
                    'total_results': 0,
                    'error': f'GNews API error: HTTP {response.status_code}'
                }
            
            # Parse response
            response.raise_for_status()
            data = response.json()
            
            # Handle API-level errors
            if 'errors' in data:
                error_messages = ', '.join(data['errors'])
                return {
                    'entries': [],
                    'total_results': 0,
                    'error': f'GNews API error: {error_messages}'
                }
            
            # Extract articles
            articles = data.get('articles', [])
            total_results = data.get('totalArticles', len(articles))
            
            # Normalize entries
            entries = []
            for article in articles:
                normalized = self._normalize_article(article)
                if normalized:
                    entries.append(normalized)
            
            return {
                'entries': entries,
                'total_results': total_results,
                'error': None
            }
            
        except requests.Timeout:
            return {
                'entries': [],
                'total_results': 0,
                'error': f'GNews API request timed out after {self.timeout} seconds'
            }
        except requests.RequestException:
            # requests exceptions may include the complete URL with apikey query param.
            logger.warning('GNews API request failed (%s).', 'request_error')
            return {
                'entries': [],
                'total_results': 0,
                'error': 'GNews API request failed. Check network connectivity and API configuration.'
            }
        except Exception:
            logger.error('Unexpected error in GNews search (%s).', 'internal_error')
            return {
                'entries': [],
                'total_results': 0,
                'error': 'Unexpected error while searching GNews.'
            }
    
    def _normalize_article(self, article: Dict) -> Optional[Dict]:
        """
        Normalize GNews article to standard format.
        
        Returns None if article is invalid.
        """
        # Extract required fields
        url = article.get('url', '').strip()
        title = article.get('title', '').strip()
        
        if not url or not title:
            return None  # Skip invalid articles
        
        # Extract optional fields
        description = article.get('description', '').strip()
        
        # Truncate description
        if len(description) > 500:
            description = description[:497] + '...'
        
        # Parse published date
        published_date = None
        published_at = article.get('publishedAt')
        if published_at:
            try:
                # GNews returns ISO 8601 format
                published_date = datetime.fromisoformat(
                    published_at.replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                pass
        
        # Extract source
        source_info = article.get('source', {})
        source_name = source_info.get('name', 'Google News')
        source_url = source_info.get('url', '')
        
        # Extract author (if available)
        author = None
        
        # Extract image (for potential future use)
        image_url = article.get('image')
        
        return {
            'title': title,
            'summary': description,
            'url': url,
            'source_name': source_name,
            'source_url': source_url,
            'author': author,
            'published_date': published_date,
            'image_url': image_url,
            'category': 'news',
            'entry_type': 'gnews',
        }
    
    def _rate_limit(self):
        """
        Enforce rate limiting between requests.
        Simple time-based throttling.
        """
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
