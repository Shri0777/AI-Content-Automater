# Research Profile Design Specification

**Document:** `RESEARCH-PROFILE-DESIGN.md`  
**Project:** AI Content Automater V2  
**Iteration:** 2  
**Status:** Design Specification  
**Date:** 2026-10-14  
**V3 Requirement:** Editable profiles with per-request overrides

---

## 1. PURPOSE

This document specifies the design for user research profiles that save default preferences and allow per-request overrides for each content creation workflow.

**V3 Requirements Addressed:**
- User-editable research preferences
- Saved defaults for recurring content creation
- Per-request override capability
- Profile management UI in dashboard
- Pre-populated but editable content creation forms

---

## 2. USER WORKFLOW

### 2.1 Profile Setup (One-Time)

```
User logs in for first time
  ↓
ResearchProfile created automatically with sensible defaults
  ↓
User navigates to "Research Settings" in dashboard
  ↓
User edits profile:
  - Topics: ["AI", "software development", "cloud", "DevOps"]
  - Audience: "developers and technology learners"
  - Goal: "educational and informative"
  - Freshness: 7 days
  - Language: "en"
  - Categories: [documentation, news, blogs]
  ↓
Profile saved
```

### 2.2 Content Creation with Override

```
User clicks "Create New Content"
  ↓
Form pre-populated with profile defaults
  ↓
User sees note: "Starting from your saved profile. Edit below for this specific content."
  ↓
User modifies for THIS request:
  - Topics: Add "machine learning" 
  - Freshness: Change to 14 days
  - (other fields unchanged)
  ↓
User clicks "Start Research Collection"
  ↓
ContentCreationRequest created with MODIFIED values
  (profile defaults remain unchanged)
  ↓
Research collection uses request values, not profile values
```

### 2.3 Subsequent Content Creation

```
User creates another content piece
  ↓
Form again pre-populated with profile defaults
  (NOT with previous request's overrides)
  ↓
User can accept defaults or override again
```

---

## 3. DATA MODEL

### 3.1 ResearchProfile Model

**Purpose:** Store user's DEFAULT research preferences

**Relationship:** OneToOne with User

**Key Design Decisions:**
- Created automatically on first access (get_or_create pattern)
- Only one profile per user (not multiple "templates")
- Updated via profile settings page
- NOT modified during content creation workflow

```python
class ResearchProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Research preferences
    topics = models.JSONField(default=list)
    audience = models.CharField(max_length=200)
    content_goal = models.CharField(max_length=200)
    freshness_days = models.IntegerField(default=7)
    allow_older_sources = models.BooleanField(default=True)
    language = models.CharField(max_length=10, default="en")
    source_categories = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Default Values (V3 Requirements):**
```python
{
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
```

### 3.2 ContentCreationRequest Model

**Purpose:** Capture research preferences for THIS SPECIFIC content

**Relationship:** ForeignKey to User (many-to-one)

**Key Design Decisions:**
- Created at start of each content creation workflow
- Stores SNAPSHOT of preferences (may differ from profile)
- Tracks workflow state (configuring → researching → generating → completed)
- Links to collected Research items

```python
class ContentCreationRequest(models.Model):
    STATUS_CHOICES = [
        ('configuring', 'Configuring Research'),
        ('researching', 'Collecting Research'),
        ('generating', 'Generating Content'),
        ('reviewing', 'Under Review'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, null=True, blank=True)
    
    # Snapshot of preferences for THIS request
    topics = models.JSONField()
    audience = models.CharField(max_length=200)
    content_goal = models.CharField(max_length=200)
    freshness_days = models.IntegerField()
    allow_older_sources = models.BooleanField()
    language = models.CharField(max_length=10)
    source_categories = models.JSONField()
    
    # Optional request-specific query
    specific_query = models.TextField(null=True, blank=True)
    
    # Workflow state
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

**Creation Pattern:**
```python
# Create from profile with optional overrides
request = ContentCreationRequest.create_from_profile(
    user=user,
    overrides={'freshness_days': 14, 'topics': ['AI', 'ML']}
)
```

---

## 4. UI DESIGN

### 4.1 Profile Settings Page

**URL:** `/research/profile/`  
**Template:** `content/research_profile_edit.html`

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Research Profile Settings                       │
│                                                 │
│ These are your default research preferences.    │
│ They will be used for new content creation but  │
│ can be overridden for each specific request.    │
├─────────────────────────────────────────────────┤
│ Research Focus                                  │
│ ┌─────────────────────────────────────────────┐ │
│ │ Topics (JSON array):                        │ │
│ │ ["AI", "software development", "cloud"]     │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ Content Parameters                              │
│ Audience: [developers and technology learners] │
│ Goal: [educational and informative]             │
│ Language: [en]                                  │
├─────────────────────────────────────────────────┤
│ Source Preferences                              │
│ Freshness: [7] days                             │
│ ☑ Allow older sources for context              │
│                                                 │
│ Source Categories:                              │
│ ☑ Documentation  ☑ News  ☑ Blogs               │
│ ☐ Research Papers  ☐ Videos  ☐ Social          │
│ ☐ Government                                    │
├─────────────────────────────────────────────────┤
│ [Save Profile]  [Cancel]                        │
└─────────────────────────────────────────────────┘
```

**Validation:**
- Topics: Valid JSON array of strings, at least 1 topic
- Audience: 1-200 characters
- Goal: 1-200 characters
- Freshness: 1-365 days
- Language: Valid ISO 639-1 code
- Categories: At least 1 selected

**Form Behavior:**
- Pre-populated with current profile values
- JSON fields show formatted JSON for readability
- Checkbox list for source categories (not raw JSON)
- Real-time validation feedback
- Success message on save

### 4.2 Content Creation Start Page

**URL:** `/content/create/start/`  
**Template:** `content/content_creation_start.html`

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Configure Content Research                      │
│                                                 │
│ ⓘ Starting from your saved profile.            │
│   You can edit any settings below for this      │
│   specific content request.                     │
├─────────────────────────────────────────────────┤
│ Research Focus         [Editable]               │
│ ┌─────────────────────────────────────────────┐ │
│ │ Topics: ["AI", "software development"]      │ │
│ └─────────────────────────────────────────────┘ │
│ (Override your profile topics for this content) │
├─────────────────────────────────────────────────┤
│ Content Parameters     [Editable]               │
│ Audience: [developers and technology learners] │
│ Goal: [educational and informative]             │
│ Language: [en]                                  │
├─────────────────────────────────────────────────┤
│ Source Preferences     [Editable]               │
│ Freshness: [7] days                             │
│ ☑ Allow older sources                          │
│                                                 │
│ Source Categories:                              │
│ ☑ Documentation  ☑ News  ☑ Blogs               │
├─────────────────────────────────────────────────┤
│ Additional Options                              │
│ Specific Query (optional):                      │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Narrow the research scope...]              │ │
│ └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│ [Start Research Collection]                     │
│ <Edit Profile Defaults>                         │
└─────────────────────────────────────────────────┘
```

**Visual Cues:**
- Badge "[Editable]" on each section
- Alert box at top explaining override capability
- Link to profile settings for editing defaults
- All fields pre-filled but modifiable
- Different from profile page (request-specific context)

**Form Behavior:**
- Initial values come from ResearchProfile
- User edits create ContentCreationRequest with modified values
- Original profile remains unchanged
- Submit creates request and redirects to collection page

### 4.3 Research Results Page

**URL:** `/content/create/<request_id>/research/`  
**Template:** `content/content_research_collect.html`

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ Research Results                                │
├─────────────────────────────────────────────────┤
│ Quality Metrics                                 │
│ ┌──────────┬──────────┬──────────┐              │
│ │   45     │    38    │   0.82   │              │
│ │  Total   │  Fresh   │ Avg Rel  │              │
│ └──────────┴──────────┴──────────┘              │
├─────────────────────────────────────────────────┤
│ Research Configuration (This Request)            │
│ Topics: AI, machine learning                    │
│ Freshness: 14 days (overridden from 7)          │
│ Categories: Documentation, News, Blogs          │
│ <Edit Configuration>                            │
├─────────────────────────────────────────────────┤
│ Collected Items (sorted by relevance)           │
│                                                 │
│ [0.95] Understanding Transformers in ML         │
│ 🏷️ rss | Martin Fowler | 2024-10-10           │
│ Summary: Comprehensive guide to transformer...  │
│ [View Source →]                                 │
│                                                 │
│ [0.88] Latest Advances in AI Safety             │
│ 🏷️ gnews | Google News | 2024-10-12           │
│ Summary: New research on alignment techniques...│
│ [View Source →]                                 │
│                                                 │
│ ... (more items) ...                           │
├─────────────────────────────────────────────────┤
│ [Proceed to Content Generation]                 │
│ <Modify Parameters>  <Start Over>              │
└─────────────────────────────────────────────────┘
```

**Key Features:**
- Shows CURRENT request's parameters (not profile defaults)
- Indicates if any values were overridden
- Quick link to edit configuration (creates new request)
- Quality statistics at top
- Research items with provenance badges

---

## 5. OVERRIDE DETECTION

### 5.1 Visual Indicators

When displaying request configuration, show which values differ from profile:

```python
# In template context
def get_override_indicators(request, profile):
    """
    Return dict of fields that were overridden.
    """
    overrides = {}
    
    if request.topics != profile.topics:
        overrides['topics'] = {
            'profile': profile.topics,
            'request': request.topics
        }
    
    if request.freshness_days != profile.freshness_days:
        overrides['freshness_days'] = {
            'profile': profile.freshness_days,
            'request': request.freshness_days
        }
    
    # ... check other fields ...
    
    return overrides
```

**Display:**
```html
<p>
  Freshness: {{ request.freshness_days }} days
  {% if 'freshness_days' in overrides %}
    <span class="badge bg-warning">
      Overridden from {{ overrides.freshness_days.profile }}
    </span>
  {% endif %}
</p>
```

---

## 6. FORM INITIALIZATION LOGIC

### 6.1 Profile Edit Form

```python
# Simple: ModelForm bound to ResearchProfile instance
form = ResearchProfileForm(instance=profile)
```

### 6.2 Content Creation Form

```python
# Pre-populate from profile but not bound to it
profile = ResearchProfile.get_or_create_for_user(request.user)

form = ContentCreationRequestForm(initial={
    'topics': json.dumps(profile.topics),
    'audience': profile.audience,
    'content_goal': profile.content_goal,
    'freshness_days': profile.freshness_days,
    'allow_older_sources': profile.allow_older_sources,
    'language': profile.language,
    'source_categories': profile.source_categories,
})

# Form is NOT bound to profile instance
# User edits create ContentCreationRequest, not update profile
```

### 6.3 Edit Configuration After Collection

```python
# If user wants to modify parameters after seeing results
# Create NEW request with updated values
# Old request status changes to 'superseded'
# Research items remain linked to old request (audit trail)
```

---

## 7. DATABASE QUERIES

### 7.1 Get User's Profile

```python
# Efficient: OneToOne with select_related
user = User.objects.select_related('research_profile').get(pk=user_id)
profile = user.research_profile  # No extra query
```

### 7.2 Get User's Requests

```python
# List recent requests
requests = ContentCreationRequest.objects.filter(
    user=user
).order_by('-created_at')[:10]

# With research counts
requests = requests.annotate(
    research_count=Count('research_results')
)
```

### 7.3 Get Request with Research

```python
# Single request with all research items
request = ContentCreationRequest.objects.prefetch_related(
    'research_results'
).get(pk=request_id, user=user)

research_items = request.research_results.all()
```

---

## 8. TESTING STRATEGY

### 8.1 Model Tests

```python
def test_profile_auto_creation():
    """Profile created with defaults on first access."""
    user = create_test_user()
    profile = ResearchProfile.get_or_create_for_user(user)
    
    assert profile.topics == ['AI', 'software development', 'cloud', 'DevOps']
    assert profile.freshness_days == 7

def test_request_from_profile_no_overrides():
    """Request inherits all profile values."""
    profile = create_test_profile()
    request = ContentCreationRequest.create_from_profile(profile.user)
    
    assert request.topics == profile.topics
    assert request.freshness_days == profile.freshness_days

def test_request_from_profile_with_overrides():
    """Request applies overrides, profile unchanged."""
    profile = create_test_profile(freshness_days=7)
    request = ContentCreationRequest.create_from_profile(
        profile.user,
        overrides={'freshness_days': 14}
    )
    
    assert request.freshness_days == 14
    profile.refresh_from_db()
    assert profile.freshness_days == 7  # Unchanged
```

### 8.2 View Tests

```python
def test_profile_edit_updates_profile():
    """Editing profile page updates ResearchProfile."""
    # POST to /research/profile/
    # Assert profile.topics updated

def test_content_creation_start_creates_request():
    """Content creation form creates ContentCreationRequest."""
    # POST to /content/create/start/
    # Assert ContentCreationRequest created
    # Assert profile unchanged

def test_profile_not_modified_by_request_edits():
    """Content creation with overrides doesn't change profile."""
    # Create profile with topics=['A', 'B']
    # Create request with topics=['C', 'D']
    # Assert profile still has ['A', 'B']
```

### 8.3 Integration Tests

```python
def test_complete_override_workflow():
    """End-to-end: profile → override → research → content."""
    # 1. Create profile
    # 2. Start content creation with overrides
    # 3. Trigger research collection
    # 4. Verify research uses request values, not profile
    # 5. Create second content
    # 6. Verify form resets to profile defaults (not previous request)
```

---

## 9. FUTURE ENHANCEMENTS

### 9.1 Multiple Profile Templates (Iteration 4+)

Allow users to save multiple profile "templates":
- "Technical Blog" template
- "Marketing Content" template
- "Research Paper" template

User selects template when creating content, then can still override.

### 9.2 Profile Recommendations (Iteration 5+)

- Suggest topics based on user's content history
- Recommend source categories based on successful research
- Auto-adjust freshness based on content type

### 9.3 Saved Overrides (Iteration 4+)

- Remember user's common overrides
- Suggest overrides based on content title/topic
- Quick-select from recent override combinations

---

## 10. ACCEPTANCE CRITERIA

**Profile Management:**
- ✅ User can edit profile in dashboard
- ✅ Profile auto-created with sensible defaults
- ✅ Profile changes saved and persisted
- ✅ JSON validation for topics and categories

**Content Creation Workflow:**
- ✅ Form pre-populated with profile defaults
- ✅ User can override any field
- ✅ Overrides create ContentCreationRequest, not modify profile
- ✅ Request stores snapshot of preferences

**Research Collection:**
- ✅ Collection uses request preferences, not profile
- ✅ Results page shows request configuration
- ✅ Override indicators show what was changed

**Subsequent Usage:**
- ✅ Next content creation resets to profile defaults
- ✅ Previous request's overrides not carried forward
- ✅ User can view history of past requests

---

## 11. SECURITY

### 11.1 Authorization

- Users can only access their own profile
- Users can only create requests for themselves
- Users can only view their own requests

### 11.2 Input Validation

- Topics: Valid JSON, max 20 topics, each max 100 chars
- Audience: Max 200 chars, no HTML
- Goal: Max 200 chars, no HTML
- Freshness: 1-365 days (integer)
- Language: Valid ISO 639-1 code (2 chars)
- Categories: From predefined choices only

### 11.3 Data Privacy

- No sensitive data in profile (just preferences)
- Research results tied to user (owner isolation)
- Request history visible only to creator

---

## APPENDIX: Example JSON Structures

### Profile Topics JSON

```json
[
  "artificial intelligence",
  "machine learning",
  "cloud computing",
  "DevOps",
  "software architecture"
]
```

### Source Categories JSON

```json
[
  "documentation",
  "news",
  "blogs",
  "research_papers"
]
```

### Full Profile Example

```json
{
  "topics": ["AI", "ML", "cloud"],
  "audience": "developers",
  "content_goal": "educational",
  "freshness_days": 7,
  "allow_older_sources": true,
  "language": "en",
  "source_categories": ["news", "blogs", "documentation"]
}
```
