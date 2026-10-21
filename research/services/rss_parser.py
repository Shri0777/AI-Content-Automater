"""
RSS/Atom feed parsing service with SSRF protection and error handling.
"""
import feedparser
import requests
import urllib.parse
import socket
import ipaddress
from datetime import datetime
from typing import List, Dict, Optional
from time import mktime
import logging

logger = logging.getLogger(__name__)


class RSSFeedService:
    """
    Parse RSS/Atom feeds into standardized research items.
    Includes SSRF protection and comprehensive error handling.
    """
    
    # SSRF protection: blocked IP ranges
    BLOCKED_IP_RANGES = [
        ipaddress.IPv4Network('0.0.0.0/8'),        # Current network
        ipaddress.IPv4Network('10.0.0.0/8'),       # Private
        ipaddress.IPv4Network('127.0.0.0/8'),      # Loopback
        ipaddress.IPv4Network('169.254.0.0/16'),   # Link-local
        ipaddress.IPv4Network('172.16.0.0/12'),    # Private
        ipaddress.IPv4Network('192.168.0.0/16'),   # Private
        ipaddress.IPv4Network('224.0.0.0/4'),      # Multicast
        ipaddress.IPv4Network('240.0.0.0/4'),      # Reserved
    ]
    
    def __init__(self, timeout=10, max_entries=50):
        """
        Initialize RSS parser.
        
        Args:
            timeout: Request timeout in seconds
            max_entries: Maximum entries to process per feed
        """
        self.timeout = timeout
        self.max_entries = max_entries
    
    def fetch_feed(self, feed_url: str, category: str = 'news') -> Dict:
        """
        Fetch and parse RSS/Atom feed with security checks.
        
        Args:
            feed_url: URL of the RSS/Atom feed
            category: Source category for categorization
        
        Returns:
            {
                'entries': List[Dict],  # Normalized entries
                'feed_title': str,
                'feed_url': str,
                'error': Optional[str]
            }
        """
        try:
            # Fetch ourselves rather than letting feedparser follow arbitrary redirects.
            # Each redirect is revalidated and redirects/body size are bounded.
            current_url = feed_url
            response = None
            for redirect_count in range(4):
                if not self._is_safe_url(current_url):
                    return {
                        'entries': [], 'feed_title': '', 'feed_url': feed_url,
                        'error': 'Feed URL or redirect blocked by outbound network security.'
                    }
                response = requests.get(
                    current_url,
                    timeout=(min(self.timeout, 5), self.timeout),
                    allow_redirects=False,
                    stream=True,
                    headers={'User-Agent': 'AI-Content-Automater/2.0', 'Connection': 'close'},
                )
                if response.is_redirect or response.is_permanent_redirect:
                    location = response.headers.get('Location')
                    response.close()
                    if not location or redirect_count >= 3:
                        return {'entries': [], 'feed_title': '', 'feed_url': feed_url, 'error': 'Feed redirect limit exceeded.'}
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue
                break
            if response is None:
                return {'entries': [], 'feed_title': '', 'feed_url': feed_url, 'error': 'Feed could not be fetched.'}
            with response:
                if response.status_code >= 400:
                    return {'entries': [], 'feed_title': '', 'feed_url': feed_url,
                            'error': f'HTTP {response.status_code}: {self._http_error_message(response.status_code)}'}
                chunks, total_bytes = [], 0
                for chunk in response.iter_content(chunk_size=16384):
                    total_bytes += len(chunk)
                    if total_bytes > 2 * 1024 * 1024:
                        return {'entries': [], 'feed_title': '', 'feed_url': feed_url, 'error': 'Feed response exceeded the 2 MiB size limit.'}
                    chunks.append(chunk)
                feed = feedparser.parse(b''.join(chunks))
            
            # Check for HTTP errors
            if hasattr(feed, 'status') and feed.status is not None:
                try:
                    if feed.status >= 400:
                        return {
                            'entries': [],
                            'feed_title': '',
                            'feed_url': feed_url,
                            'error': f'HTTP {feed.status}: {self._http_error_message(feed.status)}'
                        }
                except (TypeError, AttributeError):
                    # Status attribute exists but isn't comparable (e.g., Mock in tests)
                    pass
            
            # Check for parse errors (feedparser sets bozo flag on issues)
            if hasattr(feed, 'bozo') and feed.bozo:
                bozo_exception = getattr(feed, 'bozo_exception', None)
                # Some bozo exceptions are non-fatal (e.g., character encoding issues)
                # Log but continue if we got some entries
                if bozo_exception and not feed.entries:
                    error_msg = str(bozo_exception)
                    logger.warning(f'Feed parse error for {feed_url}: {error_msg}')
                    return {
                        'entries': [],
                        'feed_title': '',
                        'feed_url': feed_url,
                        'error': f'Feed parse error: {error_msg}'
                    }
            
            # Extract feed metadata
            feed_info = getattr(feed, 'feed', {})
            feed_title = feed_info.get('title', 'Unknown Feed')
            
            # Normalize entries
            entries = []
            for entry in feed.entries[:self.max_entries]:
                normalized = self._normalize_entry(entry, feed_title, feed_url, category)
                if normalized:
                    entries.append(normalized)
            
            return {
                'entries': entries,
                'feed_title': feed_title,
                'feed_url': feed_url,
                'error': None
            }
            
        except socket.timeout:
            return {
                'entries': [],
                'feed_title': '',
                'feed_url': feed_url,
                'error': f'Request timed out after {self.timeout} seconds'
            }
        except Exception as e:
            logger.exception(f'Failed to fetch feed {feed_url}')
            return {
                'entries': [],
                'feed_title': '',
                'feed_url': feed_url,
                'error': f'Feed fetch failed: {str(e)}'
            }
    
    def _normalize_entry(self, entry, feed_title: str, feed_url: str, category: str) -> Optional[Dict]:
        """
        Convert feedparser entry to standard format.
        
        Returns None if entry is invalid (missing required fields).
        """
        # Extract URL (required)
        url = entry.get('link', '').strip()
        if not url:
            return None  # Skip entries without URL
        
        # Extract title (required)
        title = entry.get('title', '').strip()
        if not title:
            title = 'Untitled'
        
        # Extract summary/description
        summary = ''
        if 'summary' in entry:
            summary = entry.summary
        elif 'description' in entry:
            summary = entry.description
        elif 'content' in entry and entry.content:
            # Some feeds use content instead of summary
            summary = entry.content[0].get('value', '')
        
        # Strip HTML tags from summary (feedparser may leave them)
        summary = self._strip_html(summary)
        
        # Truncate summary to reasonable length
        if len(summary) > 500:
            summary = summary[:497] + '...'
        
        # Extract dates
        published_date = self._parse_date(entry.get('published_parsed')) or \
                         self._parse_date(entry.get('updated_parsed'))
        
        # Extract author
        author = None
        if 'author' in entry:
            author = entry.author
        elif 'author_detail' in entry:
            author = entry.author_detail.get('name')
        
        # Source name defaults to feed title
        source_name = feed_title
        
        return {
            'title': title,
            'summary': summary,
            'url': url,
            'source_name': source_name,
            'source_url': feed_url,
            'author': author,
            'published_date': published_date,
            'category': category,
            'entry_type': 'rss',
        }
    
    def _parse_date(self, time_struct) -> Optional[datetime]:
        """Parse feedparser time struct to datetime."""
        if not time_struct:
            return None
        try:
            return datetime.fromtimestamp(mktime(time_struct))
        except (TypeError, ValueError, OverflowError):
            return None
    
    def _strip_html(self, text: str) -> str:
        """Simple HTML tag removal."""
        if not text:
            return ''
        
        # Basic tag stripping (feedparser usually handles this, but be safe)
        import re
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        return text.strip()
    
    def _is_safe_url(self, url: str) -> bool:
        """Allow only public HTTP(S) destinations and reject every non-global DNS answer."""
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname:
                return False
            if parsed.username or parsed.password:
                return False
            hostname = parsed.hostname.rstrip('.').lower()
            if hostname in {'localhost', 'metadata.google.internal', 'metadata.internal'} or hostname.endswith(('.local', '.internal')):
                return False
            try:
                literal = ipaddress.ip_address(hostname)
                addresses = [literal]
            except ValueError:
                infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme.lower() == 'https' else 80), type=socket.SOCK_STREAM)
                addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
            if not addresses:
                return False
            # Fail closed if any DNS answer is private, reserved, loopback, or otherwise non-public.
            return all(address.is_global and not address.is_multicast and not address.is_unspecified for address in addresses)
        except (ValueError, OSError, socket.gaierror):
            return False
        except Exception:
            logger.warning('RSS URL validation failed; request blocked.')
            return False

    def _http_error_message(self, status_code: int) -> str:
        """Human-readable HTTP error message."""
        messages = {
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found',
            410: 'Gone',
            429: 'Too Many Requests',
            500: 'Internal Server Error',
            502: 'Bad Gateway',
            503: 'Service Unavailable',
            504: 'Gateway Timeout',
        }
        return messages.get(status_code, 'Error')
