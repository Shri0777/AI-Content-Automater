# RSS/Atom and Google News Integration Design

**Document:** `RSS-GNEWS-INTEGRATION.md`  
**Project:** AI Content Automater V2  
**Iteration:** 2  
**Status:** Design Specification  
**Date:** 2026-10-14  
**V3 Requirement:** Free research sources

---

## 1. PURPOSE

This document specifies the technical design for integrating RSS/Atom feeds and Google News RSS as free research sources, replacing paid research provider APIs.

**V3 Requirements Addressed:**
- Free research sources (no API keys)
- Source provenance and attribution
- Quality scoring (relevance, recency, credibility)
- Deduplication
- Partial failure resilience

---

## 2. RSS/ATOM FEED INTEGRATION

### 2.1 Technology Choice

**Library:** `feedparser` 6.0.10  
**License:** BSD (permissive)  
**Rationale:** Mature, widely-used, handles both RSS 2.0 and Atom formats

### 2.2 Service Design

```python
# content/services/rss_parser.py

import feedparser
from datetime import datetime
from typing import List, Dict, Optional
from time import mktime

class RSSFeedService:
    """
    Parse RSS/Atom feeds into standardized research items.
    """
    
    def fetch_feed(self, feed_url: str, max_entries: int = 20) -> Dict:
        """
        Fetch and parse RSS/Atom feed.
        
        Returns:
            {
                'entries': List[Dict],  # Normalized entries
                'feed_title': str,
                'error': Optional[str]
            }
        """
        try:
            feed = feedparser.parse(feed_url)
            
            # Check for parse errors
            if feed.bozo:
                return {
                    'error': f'Feed parse error: {feed.bozo_exception}',
                    'entries': []
                }
            
            # Extract feed metadata
            feed_title = feed.feed.get('title', 'Unknown Feed')
            
            # Normalize entries
            entries = []
            for entry in feed.entries[:max_entries]:
                normalized = self._normalize_entry(entry, feed_title)
                if normalized:
                    entries.append(normalized)
            
            return {
                'entries': entries,
                'feed_title': feed_title
            }
            
        except Exception as e:
            return {
                'error': f'Feed fetch failed: {str(e)}',
                'entries': []
            }
    
    def _normalize_entry(self, entry, feed_title: str) -> Optional[Dict]:
        """
        Convert feedparser entry to standard format.
        """
        # Extract URL
        url = entry.get('link', '')
        if not url:
            return None  # Skip entries without URL
        
        # Extract dates
        published_date = self._parse_date(
            entry.get('published_parsed') or entry.get('updated_parsed')
        )
        
        # Extract content/summary
        summary = ''
        if hasattr(entry, 'summary'):
            summary = entry.summary
        elif hasattr(entry, 'description'):
            summary = entry.description
        elif hasattr(entry, 'content') and entry.content:
            summary = entry.content[0].get('value', '')
        
        # Clean HTML tags from summary
        summary = self._strip_html(summary)
        
        return {
            'title': entry.get('title', 'Untitled'),
            'summary': summary[:1000],  # Limit summary length
            'url': url,
            'source_name': feed_title,
            'author': entry.get('author', ''),
            'published_date': published_date,
        }
    
    def _parse_date(self, time_struct) -> Optional[datetime]:
        """
        Convert feedparser time struct to datetime.
        """
        if not time_struct:
            return None
        
        try:
            return datetime.fromtimestamp(mktime(time_struct))
        except (ValueError, TypeError):
            return None
    
    def _strip_html(self, html: str) -> str:
        """
        Remove HTML tags from text.
        """
        from html import unescape
        from re import sub
        
        # Remove HTML tags
        text = sub(r'<[^>]+>', '', html)
        # Decode HTML entities
        text = unescape(text)
        # Normalize whitespace
        text = sub(r'\s+', ' ', text).strip()
        
        return text
```

### 2.3 Default Feed Sources

```python
# content/services/default_feeds.py

DEFAULT_FEEDS = {
    'documentation': [
        {
            'name': 'Kubernetes Blog',
            'url': 'https://kubernetes.io/feed.xml',
            'category': 'documentation'
        },
        {
            'name': 'Docker Blog',
            'url': 'https://www.docker.com/blog/feed/',
            'category': 'documentation'
        },
        {
            'name': 'AWS What\'s New',
            'url': 'https://aws.amazon.com/about-aws/whats-new/recent/feed/',
            'category': 'documentation'
        },
    ],
    'blogs': [
        {
            'name': 'Martin Fowler',
            'url': 'https://martinfowler.com/feed.atom',
            'category': 'blog'
        },
        {
            'name': 'Cloudflare Blog',
            'url': 'https://blog.cloudflare.com/rss/',
            'category': 'blog'
        },
        {
            'name': 'AWS Blog',
            'url': 'https://aws.amazon.com/blogs/aws/feed/',
            'category': 'blog'
        },
    ],
}
```

---

## 3. GOOGLE NEWS INTEGRATION

### 3.1 Google News RSS URL Structure

**Base URL:** `https://news.google.com/rss/search`

**Parameters:**
- `q`: Search query (URL-encoded)
- `hl`: Language code (e.g., `en`, `es`, `fr`)
- `gl`: Country code (e.g., `US`, `GB`, `IN`)
- `ceid`: Combined country:language (e.g., `US:en`)

**Date Filtering:**
- Add `when:Xd` to query for last X days
- Example: `"artificial intelligence" when:7d` for last 7 days

### 3.2 Service Design

```python
# content/services/gnews_service.py

from urllib.parse import quote_plus
from .rss_parser import RSSFeedService

class GNewsService:
    """
    Query Google News via RSS (free, no API key).
    """
    
    BASE_URL = "https://news.google.com/rss/search"
    
    def __init__(self):
        self.rss_service = RSSFeedService()
    
    def search(
        self,
        query: str,
        language: str = 'en',
        country: str = 'US',
        max_results: int = 20,
        days_back: int = 7
    ) -> Dict:
        """
        Search Google News via RSS.
        
        Args:
            query: Search terms
            language: Language code (ISO 639-1)
            country: Country code (ISO 3166-1)
            max_results: Max articles to return
            days_back: Only articles from last N days
        
        Returns:
            Same structure as RSSFeedService.fetch_feed()
        """
        try:
            # Build query with date filter
            if days_back:
                query_with_date = f"{query} when:{days_back}d"
            else:
                query_with_date = query
            
            # Build URL
            url = self._build_url(
                query_with_date,
                language,
                country
            )
            
            # Use RSS service to parse
            result = self.rss_service.fetch_feed(url, max_entries=max_results)
            
            # Override source_name
            if 'entries' in result:
                for entry in result['entries']:
                    entry['source_name'] = 'Google News'
            
            return result
            
        except Exception as e:
            return {
                'error': f'Google News search failed: {str(e)}',
                'entries': []
            }
    
    def _build_url(
        self,
        query: str,
        language: str,
        country: str
    ) -> str:
        """
        Build Google News RSS URL.
        """
        params = {
            'q': quote_plus(query),
            'hl': language,
            'gl': country,
            'ceid': f"{country}:{language}"
        }
        
        return (
            f"{self.BASE_URL}"
            f"?q={params['q']}"
            f"&hl={params['hl']}"
            f"&gl={params['gl']}"
            f"&ceid={params['ceid']}"
        )
```

### 3.3 Rate Limiting

**Google News RSS:**
- No official rate limit
- Conservative approach: max 10 queries per content creation request
- Delay between queries: 1 second

```python
import time

class GNewsService:
    def __init__(self):
        self.rss_service = RSSFeedService()
        self.last_request_time = 0
        self.min_delay = 1.0  # seconds
    
    def search(self, ...):
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        
        # ... existing search logic ...
        
        self.last_request_time = time.time()
        return result
```

---

## 4. RESEARCH COLLECTION ORCHESTRATION

### 4.1 Collection Workflow

```
User creates ContentCreationRequest
  ↓
ResearchCollectionService.collect_research()
  ↓
For each topic in request.topics:
  ├─ GNewsService.search(topic, days_back=request.freshness_days)
  └─ For each RSS feed in enabled categories:
     └─ RSSFeedService.fetch_feed(feed_url)
  ↓
Aggregate all results
  ↓
Deduplicate by URL
  ↓
Filter by freshness (if !allow_older_sources)
  ↓
Calculate relevance scores
  ↓
Sort by relevance (desc)
  ↓
Save as Research objects
```

### 4.2 Deduplication

**Strategy:** URL-based (case-insensitive, normalized)

```python
def deduplicate(entries: List[Dict]) -> List[Dict]:
    """
    Remove duplicate entries by URL.
    """
    seen_urls = set()
    unique_entries = []
    
    for entry in entries:
        url = entry['url'].lower().rstrip('/')
        
        if url not in seen_urls:
            seen_urls.add(url)
            unique_entries.append(entry)
    
    return unique_entries
```

### 4.3 Relevance Scoring

**Algorithm:** Simple keyword matching (baseline)

```python
def calculate_relevance(entry: Dict, topics: List[str]) -> float:
    """
    Score 0-1 based on topic keyword matches.
    
    Future enhancements:
    - TF-IDF weighting
    - Title vs body weighting
    - Source credibility scoring
    """
    text = f"{entry['title']} {entry['summary']}".lower()
    
    matches = 0
    for topic in topics:
        if topic.lower() in text:
            matches += 1
    
    if not topics:
        return 0.5  # Neutral score
    
    # Normalize to 0-1
    return min(matches / len(topics), 1.0)
```

### 4.4 Error Handling

**Partial Failure Strategy:**
- Continue collection if some sources fail
- Log failures for user notification
- Return partial results + error list

```python
def collect_research(self, creation_request):
    results = []
    errors = []
    
    # GNews collection
    for topic in creation_request.topics:
        try:
            gnews_result = self.gnews_service.search(...)
            if 'error' in gnews_result:
                errors.append(f"GNews ({topic}): {gnews_result['error']}")
            else:
                results.extend(gnews_result['entries'])
        except Exception as e:
            errors.append(f"GNews ({topic}): {str(e)}")
            # Continue with other topics
    
    # RSS collection
    for feed_url in feeds:
        try:
            rss_result = self.rss_service.fetch_feed(...)
            if 'error' in rss_result:
                errors.append(f"RSS ({feed_url}): {rss_result['error']}")
            else:
                results.extend(rss_result['entries'])
        except Exception as e:
            errors.append(f"RSS ({feed_url}): {str(e)}")
            # Continue with other feeds
    
    return {
        'results': process_results(results),
        'errors': errors
    }
```

---

## 5. TESTING STRATEGY

### 5.1 Test Fixtures

**Sample RSS 2.0 Feed:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Tech Blog</title>
    <item>
      <title>Test Article Title</title>
      <description>Article summary here</description>
      <link>https://example.com/article</link>
      <author>John Doe</author>
      <pubDate>Mon, 14 Oct 2024 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

**Sample Atom Feed:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Documentation</title>
  <entry>
    <title>Test Doc Page</title>
    <summary>Page summary</summary>
    <link href="https://docs.example.com/page"/>
    <updated>2024-10-14T12:00:00Z</updated>
  </entry>
</feed>
```

### 5.2 Mocking Strategy

```python
import responses

@responses.activate
def test_rss_fetch():
    # Mock RSS feed response
    responses.add(
        responses.GET,
        'https://example.com/feed.xml',
        body=RSS_FIXTURE,
        status=200,
        content_type='application/rss+xml'
    )
    
    service = RSSFeedService()
    result = service.fetch_feed('https://example.com/feed.xml')
    
    assert result['entries']
    assert result['feed_title'] == 'Test Tech Blog'
```

### 5.3 Integration Tests

**Live Feed Test (Optional, slow):**
```python
@pytest.mark.integration
@pytest.mark.slow
def test_live_kubernetes_feed():
    """
    Test against real Kubernetes feed.
    Only run manually or in nightly builds.
    """
    service = RSSFeedService()
    result = service.fetch_feed('https://kubernetes.io/feed.xml')
    
    assert not result.get('error')
    assert result['entries']
```

---

## 6. FUTURE ENHANCEMENTS

### 6.1 User-Managed Feeds

**Iteration 3+:**
- RSSFeedSource model (user can add custom feeds)
- Feed discovery (auto-detect feeds on websites)
- Feed health monitoring (detect broken feeds)

### 6.2 Advanced Scoring

**Iteration 4+:**
- TF-IDF relevance
- Source credibility scoring (based on domain authority)
- User feedback loop (thumbs up/down affects future scoring)

### 6.3 Content Extraction

**Iteration 4+:**
- Full article extraction from URLs (beyond RSS summary)
- Readability scoring
- Automatic summarization

---

## 7. DEPENDENCIES

### 7.1 Python Packages

```txt
# requirements/base.txt additions
feedparser==6.0.10
```

### 7.2 Testing Packages

```txt
# requirements/development.txt additions
responses==0.24.1  # HTTP mocking
```

### 7.3 System Dependencies

None (pure Python)

---

## 8. SECURITY CONSIDERATIONS

### 8.1 URL Validation

```python
from urllib.parse import urlparse

def validate_feed_url(url: str) -> bool:
    """
    Validate feed URL before fetching.
    """
    parsed = urlparse(url)
    
    # Only HTTP(S)
    if parsed.scheme not in ['http', 'https']:
        return False
    
    # No localhost/private IPs (prevent SSRF)
    if parsed.hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
        return False
    
    return True
```

### 8.2 Content Sanitization

```python
def sanitize_summary(html: str) -> str:
    """
    Strip HTML and limit length.
    """
    # Remove all HTML tags
    text = strip_html(html)
    
    # Limit length
    max_length = 1000
    if len(text) > max_length:
        text = text[:max_length] + '...'
    
    return text
```

### 8.3 Rate Limiting

- Enforce delays between requests
- Limit max entries per feed
- Timeout for slow feeds (30 seconds)

---

## 9. MONITORING AND LOGGING

### 9.1 Metrics to Track

- Successful feed fetches vs failures
- Average fetch time per feed
- Average entries per feed
- Deduplication rate
- User-reported broken feeds

### 9.2 Error Logging

```python
import logging

logger = logging.getLogger(__name__)

def fetch_feed(self, feed_url):
    try:
        # ... fetch logic ...
    except Exception as e:
        logger.error(
            f"RSS feed fetch failed: {feed_url}",
            exc_info=True,
            extra={
                'feed_url': feed_url,
                'error_type': type(e).__name__
            }
        )
        return {'error': str(e)}
```

---

## APPENDIX A: EXAMPLE GOOGLE NEWS QUERIES

```python
# News about AI in last 7 days
"https://news.google.com/rss/search?q=artificial%20intelligence%20when:7d&hl=en&gl=US&ceid=US:en"

# Multiple keywords
"https://news.google.com/rss/search?q=kubernetes%20docker%20when:14d&hl=en&gl=US&ceid=US:en"

# Specific site
"https://news.google.com/rss/search?q=site:aws.amazon.com%20when:30d&hl=en&gl=US&ceid=US:en"
```

---

## APPENDIX B: FEED PARSER ALTERNATIVES EVALUATED

**Considered:**
1. `feedparser` ✅ SELECTED
   - Pros: Mature, handles both RSS/Atom, good error handling
   - Cons: Not actively maintained (but stable)

2. `atoma`
   - Pros: Modern, type hints
   - Cons: Less mature, fewer features

3. `python-feedgen`
   - Pros: Can also generate feeds
   - Cons: Overkill for parsing-only use case

**Decision:** feedparser for stability and compatibility
