"""
Research ranking and deduplication service.

Implements:
- URL canonicalization for deduplication
- Configurable multi-factor scoring (relevance, freshness, quality, corroboration)
- Explainable ranking rationale
"""
import urllib.parse
import re
from datetime import datetime, timedelta
from typing import List, Dict, Set
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RankingService:
    """
    Rank and deduplicate research results with explainable scoring.
    """
    
    # Default ranking weights (configurable)
    DEFAULT_WEIGHTS = {
        'relevance': 0.35,   # Relevance to query/topics
        'quality': 0.25,     # Source quality/credibility
        'freshness': 0.20,   # Recency
        'educational': 0.15, # Educational value
        'corroboration': 0.05  # Independent corroboration
    }
    
    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize ranking service.
        
        Args:
            weights: Custom ranking weights (uses defaults if not provided)
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._validate_weights()
    
    def _validate_weights(self):
        """Ensure weights sum to approximately 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(f'Ranking weights sum to {total:.2f}, not 1.0. Normalizing.')
            # Normalize
            for key in self.weights:
                self.weights[key] /= total
    
    def deduplicate_and_rank(self, entries: List[Dict], 
                             query: str = '', 
                             topics: List[str] = None,
                             freshness_days: int = 7) -> List[Dict]:
        """
        Deduplicate entries by canonical URL and rank by composite score.
        
        Args:
            entries: List of normalized research entries
            query: Original search query
            topics: List of topic keywords
            freshness_days: Freshness window in days
        
        Returns:
            List of deduplicated and ranked entries with scores
        """
        if not entries:
            return []
        
        topics = topics or []
        
        # Step 1: Canonicalize URLs and group duplicates
        canonical_groups = self._group_by_canonical_url(entries)
        
        # Step 2: For each canonical URL, pick the best entry and track provenance
        deduplicated = []
        for canonical_url, group in canonical_groups.items():
            # Use the entry with the most complete information
            best_entry = self._select_best_entry(group)
            
            # Add canonical URL
            best_entry['canonical_url'] = canonical_url
            
            # Track all sources for this URL (provenance)
            best_entry['source_count'] = len(group)
            best_entry['all_sources'] = [
                {
                    'source_name': e.get('source_name'),
                    'source_url': e.get('source_url'),
                    'entry_type': e.get('entry_type')
                }
                for e in group
            ]
            
            deduplicated.append(best_entry)
        
        # Step 3: Calculate scores for each entry
        scored_entries = []
        for entry in deduplicated:
            scores = self._calculate_scores(entry, query, topics, freshness_days)
            
            # Add individual scores
            entry['relevance_score'] = scores['relevance']
            entry['freshness_score'] = scores['freshness']
            entry['quality_score'] = scores['quality']
            entry['educational_score'] = scores['educational']
            entry['corroboration_score'] = scores['corroboration']
            
            # Calculate composite score
            entry['overall_score'] = (
                scores['relevance'] * self.weights['relevance'] +
                scores['quality'] * self.weights['quality'] +
                scores['freshness'] * self.weights['freshness'] +
                scores['educational'] * self.weights['educational'] +
                scores['corroboration'] * self.weights['corroboration']
            )
            
            # Generate rationale
            entry['ranking_rationale'] = self._generate_rationale(entry, scores)
            
            scored_entries.append(entry)
        
        # Step 4: Sort by overall score (descending)
        scored_entries.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return scored_entries
    
    def _group_by_canonical_url(self, entries: List[Dict]) -> Dict[str, List[Dict]]:
        """Group entries by canonical URL."""
        groups = defaultdict(list)
        
        for entry in entries:
            url = entry.get('url', '')
            canonical = self._canonicalize_url(url)
            groups[canonical].append(entry)
        
        return groups
    
    def _canonicalize_url(self, url: str) -> str:
        """
        Normalize URL for deduplication.
        
        - Lowercase scheme and domain
        - Remove fragment (#)
        - Remove common tracking parameters
        - Normalize path (remove trailing slash for non-root)
        """
        if not url:
            return ''
        
        try:
            parsed = urllib.parse.urlparse(url)
            
            # Lowercase scheme and netloc
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Remove www. prefix
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Clean path
            path = parsed.path
            # Remove trailing slash except for root
            if path != '/' and path.endswith('/'):
                path = path.rstrip('/')
            
            # Parse and filter query parameters
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # Remove common tracking parameters
            tracking_params = {
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'ref', 'source', '_ga', 'mc_cid', 'mc_eid'
            }
            clean_params = {
                k: v for k, v in query_params.items() 
                if k not in tracking_params
            }
            
            # Rebuild query string (sorted for consistency)
            clean_query = urllib.parse.urlencode(
                sorted(clean_params.items()), 
                doseq=True
            )
            
            # Rebuild URL without fragment
            canonical = urllib.parse.urlunparse((
                scheme,
                netloc,
                path,
                parsed.params,
                clean_query,
                ''  # No fragment
            ))
            
            return canonical
            
        except Exception as e:
            logger.warning(f'Failed to canonicalize URL {url}: {e}')
            return url
    
    def _select_best_entry(self, group: List[Dict]) -> Dict:
        """
        Select the best entry from a group of duplicates.
        Prefers entries with more complete information.
        """
        def score_completeness(entry):
            score = 0
            if entry.get('summary'):
                score += 2
            if entry.get('author'):
                score += 1
            if entry.get('published_date'):
                score += 1
            if entry.get('source_name'):
                score += 1
            return score
        
        # Sort by completeness, return best
        sorted_group = sorted(group, key=score_completeness, reverse=True)
        return sorted_group[0].copy()
    
    def _calculate_scores(self, entry: Dict, query: str, 
                          topics: List[str], freshness_days: int) -> Dict[str, float]:
        """
        Calculate individual factor scores (0-1 scale).
        """
        scores = {}
        
        # Relevance score (keyword matching)
        scores['relevance'] = self._calculate_relevance(entry, query, topics)
        
        # Freshness score (recency)
        scores['freshness'] = self._calculate_freshness(entry, freshness_days)
        
        # Quality score (source credibility indicators)
        scores['quality'] = self._calculate_quality(entry)
        
        # Educational value (heuristics for educational content)
        scores['educational'] = self._calculate_educational_value(entry)
        
        # Corroboration score (multiple independent sources)
        scores['corroboration'] = self._calculate_corroboration(entry)
        
        return scores
    
    def _calculate_relevance(self, entry: Dict, query: str, topics: List[str]) -> float:
        """Score relevance to query and topics (0-1)."""
        text = (entry.get('title', '') + ' ' + entry.get('summary', '')).lower()
        
        # Combine query and topics
        keywords = []
        if query:
            keywords.extend(query.lower().split())
        keywords.extend([t.lower() for t in topics])
        
        if not keywords:
            return 0.5  # No keywords to match against
        
        # Count keyword matches
        matches = sum(1 for kw in keywords if kw in text)
        
        # Normalize by number of keywords
        relevance = min(matches / len(keywords), 1.0)
        
        return relevance
    
    def _calculate_freshness(self, entry: Dict, freshness_days: int) -> float:
        """Score based on recency (0-1)."""
        published_date = entry.get('published_date')
        
        if not published_date:
            return 0.3  # Unknown date gets low score
        
        # Make published_date timezone-aware if it's naive
        if published_date.tzinfo is None:
            from django.utils import timezone
            published_date = timezone.make_aware(published_date)
        
        from django.utils import timezone
        now = timezone.now()
        age_days = (now - published_date).days
        
        if age_days < 0:
            # Future date (error), treat as very fresh
            return 1.0
        
        if age_days <= freshness_days:
            # Within freshness window: linear decay
            score = 1.0 - (age_days / freshness_days) * 0.3
            return max(score, 0.7)
        else:
            # Outside window: exponential decay
            normalized_age = (age_days - freshness_days) / 30.0
            score = 0.7 * (0.5 ** normalized_age)
            return max(score, 0.0)
    
    def _calculate_quality(self, entry: Dict) -> float:
        """
        Score source quality based on available indicators.
        """
        score = 0.5  # Baseline
        
        # Has author attribution
        if entry.get('author'):
            score += 0.1
        
        # Has publication date
        if entry.get('published_date'):
            score += 0.1
        
        # Longer summary suggests more substantial content
        summary_len = len(entry.get('summary', ''))
        if summary_len > 200:
            score += 0.1
        elif summary_len > 100:
            score += 0.05
        
        # Source category indicators
        category = entry.get('category', '')
        if category in ('documentation', 'research_papers'):
            score += 0.15
        elif category in ('news', 'blogs'):
            score += 0.05
        
        # Multiple sources (corroboration indicator)
        if entry.get('source_count', 1) > 1:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_educational_value(self, entry: Dict) -> float:
        """Score educational value using heuristics."""
        score = 0.5  # Baseline
        
        text = (entry.get('title', '') + ' ' + entry.get('summary', '')).lower()
        
        # Educational keywords
        edu_keywords = [
            'tutorial', 'guide', 'how to', 'learn', 'beginner',
            'introduction', 'explained', 'overview', 'fundamentals',
            'best practices', 'examples', 'documentation'
        ]
        
        matches = sum(1 for kw in edu_keywords if kw in text)
        if matches > 0:
            score += min(matches * 0.1, 0.3)
        
        # Source category
        category = entry.get('category', '')
        if category in ('documentation', 'research_papers'):
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_corroboration(self, entry: Dict) -> float:
        """Score based on corroboration from independent sources."""
        source_count = entry.get('source_count', 1)
        
        if source_count <= 1:
            return 0.0
        elif source_count == 2:
            return 0.5
        elif source_count == 3:
            return 0.75
        else:
            return 1.0
    
    def _generate_rationale(self, entry: Dict, scores: Dict[str, float]) -> str:
        """Generate human-readable ranking rationale."""
        parts = []
        
        # Relevance
        if scores['relevance'] >= 0.7:
            parts.append('Highly relevant to query')
        elif scores['relevance'] >= 0.4:
            parts.append('Moderately relevant')
        else:
            parts.append('Low relevance')
        
        # Freshness
        if scores['freshness'] >= 0.7:
            parts.append('recent content')
        elif scores['freshness'] >= 0.3:
            parts.append('moderately recent')
        else:
            parts.append('older content')
        
        # Quality
        if scores['quality'] >= 0.7:
            parts.append('high-quality source')
        elif scores['quality'] >= 0.5:
            parts.append('reputable source')
        
        # Educational
        if scores['educational'] >= 0.7:
            parts.append('strong educational value')
        
        # Corroboration
        source_count = entry.get('source_count', 1)
        if source_count > 1:
            parts.append(f'corroborated by {source_count} sources')
        
        return '; '.join(parts).capitalize() + '.'
