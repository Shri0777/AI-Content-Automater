from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Content(models.Model):
    """
    Main content entity representing a piece of content through its lifecycle.
    Each content item is owned by a user and progresses through lifecycle states.
    """
    LIFECYCLE_CHOICES = [
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved'),
        ('ready_to_publish', 'Ready to Publish'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='contents',
        db_index=True
    )
    title = models.CharField(max_length=255)
    topic = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Internal notes or instructions for this content'
    )
    lifecycle_state = models.CharField(
        max_length=50,
        choices=LIFECYCLE_CHOICES,
        default='draft',
        db_index=True
    )
    current_version = models.ForeignKey(
        'ContentVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'content'
        verbose_name = 'Content'
        verbose_name_plural = 'Contents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_lifecycle_state_display()})"

    def can_transition_to(self, new_state):
        """
        Validate if transition from current state to new state is allowed.
        Implements lifecycle state machine rules.
        """
        # Define valid state transitions
        valid_transitions = {
            'draft': ['in_progress'],
            'in_progress': ['pending_review', 'draft'],
            'pending_review': ['approved', 'draft', 'in_progress'],
            'approved': ['ready_to_publish', 'published', 'in_progress', 'draft'],
            'ready_to_publish': ['published', 'approved', 'in_progress'],
            'published': ['archived'],
            'archived': [],  # Terminal state
        }

        return new_state in valid_transitions.get(self.lifecycle_state, [])

    def transition_to(self, new_state):
        """
        Transition content to a new lifecycle state with validation.
        """
        if not self.can_transition_to(new_state):
            raise ValidationError(
                f"Cannot transition from {self.lifecycle_state} to {new_state}"
            )
        self.lifecycle_state = new_state
        self.save(update_fields=['lifecycle_state', 'updated_at'])

    def get_status_info(self):
        """
        Return comprehensive status information for API responses and UI.

        TASK-048: Enhanced status information including:
        - Current lifecycle state
        - Version counts
        - Available transitions
        - Timestamps
        """
        versions = self.versions.all()

        return {
            'lifecycle_state': self.lifecycle_state,
            'lifecycle_state_display': self.get_lifecycle_state_display(),
            'current_version_number': self.current_version.version_number if self.current_version else None,
            'version_count': versions.count(),
            'last_state_change_at': self.updated_at,
            'available_transitions': self._get_available_transitions(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def _get_available_transitions(self):
        """
        Return list of valid next states from current state.

        Used by get_status_info() to show available transitions in UI.
        """
        valid_transitions = {
            'draft': ['in_progress'],
            'in_progress': ['pending_review', 'draft'],
            'pending_review': ['approved', 'draft', 'in_progress'],
            'approved': ['ready_to_publish', 'published', 'in_progress', 'draft'],
            'ready_to_publish': ['published', 'approved', 'in_progress'],
            'published': ['archived'],
            'archived': [],  # Terminal state
        }
        return valid_transitions.get(self.lifecycle_state, [])


class ContentVersion(models.Model):
    """
    Immutable version history for content.
    Each version represents a snapshot of content text at a point in time.
    """
    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name='versions',
        db_index=True
    )
    version_number = models.IntegerField()
    content_text = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='content_versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    change_summary = models.TextField(
        null=True,
        blank=True,
        help_text='Description of changes in this version'
    )
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = 'content_version'
        verbose_name = 'Content Version'
        verbose_name_plural = 'Content Versions'
        ordering = ['-version_number']
        unique_together = [['content', 'version_number']]
        indexes = [
            models.Index(fields=['content', 'created_at']),
        ]

    def __str__(self):
        return f"{self.content.title} v{self.version_number}"

    @classmethod
    def create_initial_version(cls, content, created_by, content_text='', change_summary=''):
        """
        Create the first version for a new content item.
        """
        return cls.objects.create(
            content=content,
            version_number=1,
            content_text=content_text,
            created_by=created_by,
            change_summary=change_summary
        )

    @classmethod
    def create_next_version(cls, content, created_by, content_text, change_summary=''):
        """
        Create a new version by incrementing the version number.
        """
        latest_version = content.versions.order_by('-version_number').first()
        next_number = (latest_version.version_number + 1) if latest_version else 1

        return cls.objects.create(
            content=content,
            version_number=next_number,
            content_text=content_text,
            created_by=created_by,
            change_summary=change_summary
        )


class ContentReview(models.Model):
    """
    Automated AI Quality Review record for a specific ContentVersion.

    Implements mandatory two-stage review (FR-007, FR-009, BR-002) and tracks
    relevance, evidence traceability, factual consistency, clarity, and actionable findings.
    """
    STAGE_CHOICES = [
        (1, 'Stage 1: Initial Quality Review'),
        (2, 'Stage 2: Post-Correction Review'),
    ]
    STATUS_CHOICES = [
        ('passed', 'Passed'),
        ('needs_revision', 'Needs Revision'),
        ('failed', 'Failed'),
    ]

    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.CASCADE,
        related_name='reviews',
        db_index=True
    )
    stage = models.PositiveSmallIntegerField(
        choices=STAGE_CHOICES,
        default=1,
        help_text='Review stage (1=initial, 2=post-correction)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='needs_revision',
        db_index=True
    )
    score = models.FloatField(
        default=0.0,
        help_text='Overall quality score (0.0 to 1.0)'
    )

    # Rating dimensions
    relevance_rating = models.CharField(max_length=50, default='Medium')
    evidence_support_rating = models.CharField(max_length=50, default='Medium')
    factual_consistency_rating = models.CharField(max_length=50, default='Medium')
    clarity_rating = models.CharField(max_length=50, default='Medium')

    # Structured findings
    findings = models.JSONField(
        default=list,
        blank=True,
        help_text='List of actionable review findings'
    )
    unsupported_claims = models.JSONField(
        default=list,
        blank=True,
        help_text='List of assertions lacking source evidence'
    )
    summary = models.TextField(
        help_text='Executive summary of the review findings'
    )

    # Provider metadata
    reviewed_by_provider = models.CharField(max_length=100, default='ai')
    model_name = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'content_review'
        ordering = ['content_version', 'stage', '-created_at']
        indexes = [
            models.Index(fields=['content_version', 'stage']),
        ]

    def __str__(self):
        return f"{self.content_version} - Stage {self.stage} ({self.status})"


class PublishingPreparation(models.Model):
    """
    Prepares approved and validated content versions for publication to target platforms (Phase 5).
    Enforces final validation gates, platform character constraints, and attribution formatting.
    """
    STATUS_CHOICES = [
        ('prepared', 'Prepared'),
        ('invalidated', 'Invalidated'),
        ('failed', 'Validation Failed'),
    ]

    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name='publishing_preparations',
        db_index=True
    )
    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.CASCADE,
        related_name='publishing_preparations',
        db_index=True
    )
    prepared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='prepared_publications'
    )
    prepared_at = models.DateTimeField(auto_now_add=True)
    target_platforms = models.JSONField(
        default=list,
        help_text="Target platform identifiers (e.g. ['twitter', 'linkedin', 'generic'])"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='prepared',
        db_index=True
    )
    prepared_payload = models.JSONField(
        default=dict,
        help_text="Platform-specific formatted text, metadata, and character counts"
    )
    validation_results = models.JSONField(
        default=dict,
        help_text="Results of final validation checks"
    )
    invalidation_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason why this preparation was invalidated"
    )

    class Meta:
        db_table = 'content_publishing_preparation'
        ordering = ['-prepared_at']
        verbose_name = 'Publishing Preparation'
        verbose_name_plural = 'Publishing Preparations'

    def __str__(self):
        return f"Preparation for {self.content.title} v{self.content_version.version_number} ({self.status})"


class WorkflowAuditLog(models.Model):
    """
    Immutable audit trail of security-sensitive and workflow-significant events (FR-021).
    Tracks transitions, actor, timestamps, and actionable failure/success details.
    """
    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_index=True
    )
    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_actions'
    )
    event_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Event classification (e.g. state_transition, approval, validation_failed, publishing_prepared)"
    )
    from_state = models.CharField(max_length=50, null=True, blank=True)
    to_state = models.CharField(max_length=50, null=True, blank=True)
    message = models.TextField(help_text="Descriptive summary of the event")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'workflow_audit_log'
        ordering = ['-created_at']
        verbose_name = 'Workflow Audit Log'
        verbose_name_plural = 'Workflow Audit Logs'

    def __str__(self):
        actor = self.user.email if self.user else 'System'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.event_type} by {actor}"


class ContentPublication(models.Model):
    """
    Durable record of scheduling and publishing operations through Buffer (Phase 6).
    Enforces idempotency, gate validation, explicit statuses, and auditability.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('publishing', 'Publishing'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
        ('failed', 'Failed'),
        ('ambiguous', 'Outcome Unknown / Reconciliation Required'),
        ('cancelled', 'Cancelled'),
    ]
    MODE_CHOICES = [
        ('immediate', 'Immediate Publication'),
        ('scheduled', 'Scheduled Publication'),
    ]

    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name='publications',
        db_index=True
    )
    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.CASCADE,
        related_name='publications',
        db_index=True
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='publications'
    )
    provider = models.CharField(max_length=50, default='buffer')
    profile_id = models.CharField(max_length=100, db_index=True, help_text="Buffer social channel / profile ID")
    profile_service = models.CharField(max_length=50, null=True, blank=True, help_text="Social service (e.g. twitter, linkedin)")
    profile_name = models.CharField(max_length=150, null=True, blank=True, help_text="Formatted username / handle")
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default='immediate'
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(
        max_length=128,
        db_index=True,
        unique=True,
        help_text="Idempotency token preventing duplicate submissions"
    )
    external_post_id = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_index=True,
        help_text="External Buffer update ID"
    )
    payload_text = models.TextField(help_text="Exact text submitted to Buffer")
    error_message = models.TextField(null=True, blank=True)
    error_type = models.CharField(max_length=50, null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    response_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'content_publication'
        ordering = ['-created_at']
        verbose_name = 'Content Publication'
        verbose_name_plural = 'Content Publications'
        indexes = [
            models.Index(fields=['content', 'status']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        target = f"{self.profile_service or 'social'} ({self.profile_name or self.profile_id})"
        return f"Publication of {self.content.title} v{self.content_version.version_number} to {target} [{self.status}]"


class Campaign(models.Model):
    """
    Recurring content generation campaign.

    Implements FR-030 and FR-031 for scheduled, recurring content campaigns.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    topic = models.CharField(max_length=500)
    generation_instructions = models.TextField()
    research_instructions = models.TextField(blank=True)
    target_platforms = models.JSONField(default=list)
    publish_immediately = models.BooleanField(default=False)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='weekly')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_execution = models.DateTimeField(null=True, blank=True, db_index=True)
    execution_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failure_count = models.PositiveIntegerField(default=0)
    last_executed = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'campaign'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['owner', 'status']), models.Index(fields=['status', 'next_execution'])]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"


class CampaignExecution(models.Model):
    """Individual execution record for a campaign."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('researching', 'Researching'),
        ('generating', 'Generating'),
        ('reviewing', 'Reviewing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='executions')
    scheduled_time = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    content = models.ForeignKey(Content, null=True, blank=True, on_delete=models.SET_NULL, related_name='campaign_executions')
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=50, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    execution_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'campaign_execution'
        ordering = ['-scheduled_time']
        indexes = [models.Index(fields=['campaign', 'status']), models.Index(fields=['status', 'scheduled_time'])]

    def __str__(self):
        return f"{self.campaign.name} - {self.scheduled_time.date()} ({self.status})"


class Notification(models.Model):
    """
    User notification for workflow events, approvals, and failures (FR-038).
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('generation_success', 'Content Generation Successful'),
        ('generation_failure', 'Content Generation Failed'),
        ('review_needs_revision', 'Review Needs Revision'),
        ('review_passed', 'Review Passed'),
        ('approval_required', 'Approval Required'),
        ('publishing_success', 'Publishing Successful'),
        ('publishing_failure', 'Publishing Failed'),
        ('publishing_partial', 'Publishing Partially Successful'),
        ('campaign_execution_success', 'Campaign Execution Successful'),
        ('campaign_execution_failure', 'Campaign Execution Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', db_index=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Context links
    content = models.ForeignKey(Content, null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')
    campaign = models.ForeignKey('Campaign', null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')

    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(max_length=50, default='pending')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title} for {self.user.email} ({self.get_notification_type_display()})"


class NotificationPreference(models.Model):
    """
    User preferences for notification delivery (FR-038.4).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')

    # Per-type preferences
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)

    # Specific notification type overrides (JSON field for flexibility)
    type_preferences = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preference'

    def __str__(self):
        return f"Notification preferences for {self.user.email}"


class Media(models.Model):
    """
    Media file associated with content for social publishing (FR-039).
    """
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='media', db_index=True)
    content = models.ForeignKey(Content, null=True, blank=True, on_delete=models.SET_NULL, related_name='media')

    # File storage
    file = models.FileField(upload_to='media/%Y/%m/', max_length=255)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text='Size in bytes')
    mime_type = models.CharField(max_length=100)

    # Validation status
    is_validated = models.BooleanField(default=False)
    validation_errors = models.TextField(blank=True)

    # Image metadata (from PIL/Pillow if image)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'media'
        ordering = ['-created_at']
        verbose_name_plural = 'Media'

    def __str__(self):
        return f"{self.file_name} ({self.owner.email})"


class PublicationMetrics(models.Model):
    """
    Analytics metrics for published content (FR-011).
    Stores operational metrics and platform engagement where available.
    """
    publication = models.ForeignKey(ContentPublication, on_delete=models.CASCADE, related_name='metrics', db_index=True)
    platform = models.CharField(max_length=50, db_index=True)

    # Operational metrics (always available)
    published_at = models.DateTimeField()

    # Platform engagement metrics (where API provides them)
    impressions = models.IntegerField(null=True, blank=True, help_text='Number of times content was displayed')
    engagements = models.IntegerField(null=True, blank=True, help_text='Total engagements (likes, shares, comments)')
    clicks = models.IntegerField(null=True, blank=True, help_text='Number of link clicks')

    # Collection metadata
    collected_at = models.DateTimeField(auto_now=True)
    collection_status = models.CharField(max_length=50, default='available')

    class Meta:
        db_table = 'publication_metrics'
        ordering = ['-published_at']
        verbose_name_plural = 'Publication Metrics'

    def __str__(self):
        return f"Metrics for {self.publication.content.title} on {self.platform}"
