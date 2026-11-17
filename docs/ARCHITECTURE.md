# Architecture

Four diagrams of how the backend fits together. They are written in
Mermaid, so GitHub draws them from plain text, and the post lifecycle is
generated from the code's own transition table (`studio/statuses.py`);
`tests/test_architecture_doc.py` fails if the two ever disagree.

For the reasoning behind each choice, see
[design/system-design.md](../design/system-design.md) and the decision
records in [design/decisions.md](../design/decisions.md).

## 1. The system

```mermaid
flowchart LR
    client["Frontend or Swagger UI"] -->|HTTPS, JWT| web["web<br/>Django REST API"]
    web --> db[("PostgreSQL<br/>source of truth")]
    web --> redis[("Redis<br/>job queue + cache")]
    beat["beat<br/>timetable"] -->|every minute / hour| redis
    redis --> worker["worker<br/>makes posts"]
    redis --> wpub["worker-publish<br/>publishes on time"]
    worker --> db
    wpub --> db
    worker -->|checked connections| ai["AI models<br/>(the user's own keys)"]
    worker -->|checked connections| news["News feeds<br/>(RSS, Hacker News)"]
    wpub -->|checked connections| social["Buffer, X,<br/>LinkedIn, Facebook"]
```

- **PostgreSQL holds every state** (slots, posts, publications), so a
  restart loses nothing: Celery only runs the work (ADR-002).
- **Two worker queues:** a burst of posts being made never delays a post
  that is due to go out.
- **Every outside connection** goes through `core/safe_network.py`, which
  refuses private addresses at the moment of connecting (SSRF and DNS
  rebinding protection).

## 2. One scheduled post, end to end

```mermaid
sequenceDiagram
    participant B as beat
    participant D as dispatcher
    participant W as worker
    participant AI as user's AI models
    participant U as user
    participant P as worker-publish
    participant S as social platform
    B->>D: every minute
    D->>D: skip slots too late to post (one notice)
    D->>D: claim due slots (SKIP LOCKED + 5-min lease)
    D->>W: start post
    W->>AI: rate a shortlist of 5 articles
    W->>AI: write headline and caption
    W->>AI: write image prompt, make artwork
    W->>W: put headline on artwork (Pillow)
    W->>AI: review the post
    W->>W: verdict by fixed rules, correct up to 2 times
    alt auto-post gate opens (clean pass)
        W->>W: approved
    else gate closed
        W->>U: notification: please approve
        U->>W: approve (or edit, reject)
    end
    B->>P: at publish_at
    P->>S: publish once per account (idempotency key)
    alt no answer from the platform
        P->>P: mark ambiguous, never re-send
        P->>U: please confirm whether it went out
    end
```

## 3. A post's life

Generated from `ALLOWED_TRANSITIONS` in `studio/statuses.py`.

```mermaid
stateDiagram-v2
    [*] --> researching
    researching --> drafting
    researching --> skipped
    researching --> failed
    drafting --> imaging
    drafting --> failed
    imaging --> reviewing
    imaging --> failed
    reviewing --> correcting
    reviewing --> awaiting_approval
    reviewing --> approved
    reviewing --> failed
    correcting --> reviewing
    correcting --> failed
    awaiting_approval --> approved
    awaiting_approval --> rejected
    awaiting_approval --> expired
    approved --> publishing
    approved --> failed
    publishing --> published
    publishing --> failed
    published --> [*]
    rejected --> [*]
    expired --> [*]
    skipped --> [*]
    failed --> [*]
```

- `skipped`: no article was good enough; nothing is posted rather than filler.
- `reviewing → approved` happens only when the auto-post gate opens.
- `expired`: a scheduled post nobody approved in time (plans set to "expire").

## 4. The main tables

```mermaid
erDiagram
    USER ||--o{ PROVIDER_CREDENTIAL : "owns (encrypted keys)"
    USER ||--o{ SOCIAL_ACCOUNT : "links (encrypted tokens)"
    USER ||--o{ CONTENT_PLAN : owns
    CONTENT_PLAN ||--o{ TOPIC : follows
    CONTENT_PLAN ||--o{ SCHEDULE_RULE : "posts at"
    CONTENT_PLAN }o--o{ SOCIAL_ACCOUNT : "posts to"
    SCHEDULE_RULE ||--o{ POST_SLOT : "becomes"
    POST_SLOT ||--o| POST : "starts"
    TOPIC ||--o{ POST : about
    ARTICLE ||--o{ POST : "source of"
    ARTICLE ||--o{ ARTICLE_USE : "used by plan"
    POST ||--o{ POST_VERSION : "versions"
    POST_VERSION ||--o| REVIEW : "reviewed by"
    POST ||--o{ GENERATION_STEP : "audit trail"
    POST ||--o{ PUBLICATION : "sent as"
    SOCIAL_ACCOUNT ||--o{ PUBLICATION : "to"
    USER ||--o{ NOTIFICATION : receives
```

- `POST_SLOT` is unique per plan and time, and a post belongs to at most one
  slot, so a slot can never produce two posts.
- `PUBLICATION.idempotency_key` is unique per post, version and account, so
  the same post is never sent twice to the same account.
- `ARTICLE` is shared by every user who follows the same topic.
