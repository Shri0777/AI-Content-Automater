from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class ResearchProfile(models.Model):
    """
    User's research preferences - saved defaults.
    Can be overridden per content-creation request.
    
    V3 Requirement: Editable in dashboard for every content request.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='research_profile'
    )
    
    # Topics (stored as JSON list of keywords)
    topics = models.JSONField(
        default=list,
        help_text="Default research topics (e.g., ['AI', 'software development', 'cloud', 'DevOps'])"
    )
    
    # Audience
    audience = models.CharField(
        max_length=200,
        default="developers and technology learners",
        help_text="Target audience for content"
    )
    
    # Content goal
    content_goal = models.CharField(
        max_length=200,
        default="educational and informative",
        help_text="Purpose of generated content"
    )
    
    # Freshness preference
    freshness_days = models.IntegerField(
        default=7,
        help_text="Prefer content from last N days"
    )
    allow_older_sources = models.BooleanField(
        default=True,
        help_text="Allow older sources for context and background"
    )
    
    # Language
    language = models.CharField(
        max_length=10,
        default="en",
        help_text="Research and content language code"
    )
    
    # Source categories (JSON list of enabled categories)
    source_categories = models.JSONField(
        default=list,
        help_text="Enabled source types"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'research_profile'
        verbose_name = 'Research Profile'
        verbose_name_plural = 'Research Profiles'
    
    def __str__(self):
        return f"Research Profile for {self.user.email}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """
        Get existing profile or create with V3 defaults.
        """
        profile, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'topics': ['AI', 'software development', 'cloud', 'DevOps'],
                'audience': 'developers and technology learners',
                'content_goal': 'educational and informative',
                'freshness_days': 7,
                'allow_older_sources': True,
                'language': 'en',
                'source_categories': [
                    'documentation',
                    'news',
                    'blogs',
                    'research_papers',
                    'videos',
                    'social',
                    'government'
                ]
            }
        )
        return profile


class ContentCreationRequest(models.Model):
    """
    Tracks a content creation workflow with research preferences.
    Captures user's choices for THIS specific request.
    Can differ from their saved profile defaults.
    
    V3 Requirement: Per-request overrides of saved defaults.
    """
    STATUS_CHOICES = [
        ('configuring', 'Configuring Research'),
        ('researching', 'Collecting Research'),
        ('generating', 'Generating Content'),
        ('reviewing', 'Under Review'),
        ('completed', 'Completed'),
        ('partial', 'Partially Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='content_requests'
    )
    
    # Import Content model reference
    content = models.ForeignKey(
        'content.Content',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='creation_request'
    )
    
    # Research preferences for THIS request (snapshot at creation time)
    topics = models.JSONField(help_text="Topics for this request")
    audience = models.CharField(max_length=200)
    content_goal = models.CharField(max_length=200)
    freshness_days = models.IntegerField()
    allow_older_sources = models.BooleanField(default=True)
    language = models.CharField(max_length=10)
    source_categories = models.JSONField()
    
    # Additional request-specific parameters
    specific_query = models.TextField(
        null=True,
        blank=True,
        help_text="Optional: Specific research query or focus"
    )
    
    # Workflow state
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='configuring'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Actionable failure or partial success message"
    )
    error_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Error classification category"
    )
    retry_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of research collection retry attempts"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'content_creation_request'
        verbose_name = 'Content Creation Request'
        verbose_name_plural = 'Content Creation Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Request {self.pk} for {self.user.email} - {self.status}"
    
    @classmethod
    def create_from_profile(cls, user, content=None, overrides=None):
        """
        Create request from user's profile with optional overrides.
        
        Args:
            user: User creating the request
            content: Optional Content object to associate
            overrides: Dict of fields to override from profile defaults
        
        Returns:
            ContentCreationRequest instance
        """
        profile = ResearchProfile.get_or_create_for_user(user)
        
        data = {
            'user': user,
            'content': content,
            'topics': profile.topics,
            'audience': profile.audience,
            'content_goal': profile.content_goal,
            'freshness_days': profile.freshness_days,
            'allow_older_sources': profile.allow_older_sources,
            'language': profile.language,
            'source_categories': profile.source_categories,
        }
        
        # Apply overrides if provided
        if overrides:
            data.update(overrides)
        
        return cls.objects.create(**data)


class Research(models.Model):
    """
    Research items from RSS/Atom feeds and GNews.
    
    V3 Approach:
    - RSS/Atom: Parse feeds from configured sources
    - GNews: Query Google News RSS (with API key)
    - No paid external providers
    """
    ENTRY_TYPE_CHOICES = [
        ('rss', 'RSS/Atom Feed'),
        ('gnews', 'Google News'),
        ('manual', 'Manual Entry'),
    ]
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='research_items',
        db_index=True
    )
    
    # Link to creation request (if part of automated research)
    creation_request = models.ForeignKey(
        ContentCreationRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='research_results'
    )
    
    entry_type = models.CharField(
        max_length=20,
        choices=ENTRY_TYPE_CHOICES,
        default='rss'
    )
    
    # Core fields
    title = models.CharField(max_length=500)
    summary = models.TextField(
        help_text='Article summary or description'
    )
    url = models.URLField(
        max_length=2000,
        help_text='Source article URL'
    )
    
    # Canonical URL for deduplication
    canonical_url = models.URLField(
        max_length=2000,
        db_index=True,
        help_text='Normalized URL for duplicate detection'
    )
    
    # Provenance (V3 requirement: source attribution)
    source_name = models.CharField(
        max_length=200,
        help_text='Publication or source name'
    )
    author = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Original publication date',
        db_index=True
    )
    
    # Quality metadata (V3 requirement: relevance, credibility)
    relevance_score = models.FloatField(
        default=0.0,
        help_text='0-1 score for relevance to research query'
    )
    freshness_score = models.FloatField(
        default=0.0,
        help_text='0-1 score based on recency'
    )
    quality_score = models.FloatField(
        default=0.0,
        help_text='0-1 score for source quality/credibility'
    )
    overall_score = models.FloatField(
        default=0.0,
        db_index=True,
        help_text='Composite score for ranking'
    )
    
    category = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Source category (documentation, news, blog, etc.)'
    )
    
    # Selection state
    is_selected = models.BooleanField(
        default=False,
        help_text='User selected this research for content generation'
    )
    is_excluded = models.BooleanField(
        default=False,
        help_text='User explicitly excluded this research'
    )
    
    # User annotations
    notes = models.TextField(
        null=True,
        blank=True,
        help_text='User notes about this research item'
    )
    
    # Ranking rationale (explainability)
    ranking_rationale = models.TextField(
        null=True,
        blank=True,
        help_text='Explanation of why this scored as it did'
    )
    
    # Timestamps
    collected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'research'
        verbose_name = 'Research Item'
        verbose_name_plural = 'Research Items'
        ordering = ['-overall_score', '-collected_at']
        indexes = [
            models.Index(fields=['owner', 'collected_at']),
            models.Index(fields=['entry_type']),
            models.Index(fields=['creation_request']),
            models.Index(fields=['published_date']),
            models.Index(fields=['canonical_url']),
            models.Index(fields=['-overall_score']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.source_name})"
    
    def is_fresh(self, days=7):
        """Check if research is within freshness window."""
        if not self.published_date:
            return False
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.published_date >= cutoff


class ResearchContentAssociation(models.Model):
    """
    Evidence-to-content traceability link connecting research findings to generated content.
    Tracks citations, relevance notes, and supporting claims.
    """
    research = models.ForeignKey(
        Research,
        on_delete=models.CASCADE,
        related_name='content_associations',
        db_index=True
    )
    content = models.ForeignKey(
        'content.Content',
        on_delete=models.CASCADE,
        related_name='research_associations',
        db_index=True
    )
    content_version = models.ForeignKey(
        'content.ContentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='evidence_associations',
        help_text='Specific content version this evidence was cited in'
    )
    associated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    associated_at = models.DateTimeField(auto_now_add=True)
    relevance_note = models.TextField(
        null=True,
        blank=True,
        help_text='Why this research is relevant or excerpt cited'
    )
    citation_index = models.PositiveIntegerField(
        default=1,
        help_text='Citation reference number [1], [2], etc.'
    )

    class Meta:
        db_table = 'research_content_association'
        ordering = ['citation_index', '-associated_at']
        indexes = [
            models.Index(fields=['research', 'content']),
            models.Index(fields=['content', 'associated_at']),
        ]

    def __str__(self):
        return f"{self.research.title} → {self.content.title} ([{self.citation_index}])"

