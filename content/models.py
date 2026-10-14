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
            'pending_review': ['approved', 'draft'],
            'approved': ['published'],
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
    def create_initial_version(cls, content, created_by, content_text=''):
        """
        Create the first version for a new content item.
        """
        return cls.objects.create(
            content=content,
            version_number=1,
            content_text=content_text,
            created_by=created_by
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
