/*
 * The shapes the API sends and receives, copied from schema/openapi.yaml
 * (the saved API contract). Keep them in step when the API changes.
 */

export type User = {
  id: string;
  email: string;
  timezone: string;
  tier: string;
  date_joined: string;
};

export type Summary = {
  unread_notifications: number;
  posts_awaiting_approval: number;
  accounts_needing_attention: number;
};

export type LimitUsage = {
  resource: string;
  description: string;
  period: string;
  applies_to: string;
  limit: number;
  used: number;
  resets_at: string | null;
};

export type CredentialKind = "text" | "image" | "news";

export type Credential = {
  id: string;
  kind: CredentialKind;
  adapter: string;
  model_name: string;
  base_url: string;
  key_hint: string;
  status: "unverified" | "verified" | "invalid";
  last_checked_at: string | null;
  last_error: string;
  updated_at: string;
};

export type SocialAccount = {
  id: string;
  platform: "demo" | "buffer" | "x" | "linkedin" | "facebook";
  network: string;
  display_name: string;
  status: "active" | "needs_reauth" | "revoked";
  last_error: string;
  link_expires_at: string | null;
  created_at: string;
};

export type Platform = {
  platform: string;
  name: string;
  link_method: "oauth" | "api_key" | "demo";
  ready: boolean;
  /** X, LinkedIn, Facebook: did you save your own developer app? */
  app_saved: boolean;
  /** X, LinkedIn, Facebook: the address to register in your developer app. */
  callback_url: string | null;
};

export type PlatformApp = { platform: string; client_id: string; updated_at: string };

export type BufferChannel = { id: string; name: string; network: string };

/** A built-in topic key such as "ai_news", "custom" for a new topic of your own, or "custom-<id>" once saved. */
export type Topic = { id?: string; name: string; preset: string; search_words?: string; instructions?: string };

export type TopicChoice = { key: string; label: string; category: string; description: string };

export type TopicCatalogue = { categories: string[]; topics: TopicChoice[] };

export type ScheduleRule = {
  id?: string;
  days_of_week: number[];
  times: string[];
  timezone?: string;
};

export type Plan = {
  id: string;
  name: string;
  requirements: string;
  approval_mode: "manual" | "auto";
  ai_label_enabled: boolean;
  ai_label_text: string;
  /** AI artwork on the cover slide (off by default; needs an image key). */
  ai_artwork_enabled: boolean;
  /** The slides' background colour, "#RRGGBB". */
  brand_colour: string;
  paused: boolean;
  lead_time_minutes: number;
  max_lateness_minutes: number;
  on_missed_approval: "expire" | "hold";
  auto_post_min_score: number;
  topics: Topic[];
  accounts: SocialAccount[];
  schedule_rules: ScheduleRule[];
  created_at: string;
};

export type PostSlot = {
  id: string;
  publish_at: string;
  generate_at: string;
  status: "waiting" | "claimed" | "started" | "skipped";
  post: string | null;
};

export type PostStatus =
  | "researching"
  | "drafting"
  | "imaging"
  | "reviewing"
  | "correcting"
  | "awaiting_approval"
  | "approved"
  | "publishing"
  | "published"
  | "rejected"
  | "expired"
  | "skipped"
  | "failed";

export type Post = {
  id: string;
  plan: string;
  plan_name: string;
  topic_name: string | null;
  scheduled_for: string | null;
  status: PostStatus;
  status_reason: string;
  demo_mode: boolean;
  created_at: string;
  updated_at: string;
};

export type Review = {
  scores: Record<string, number>;
  /** "major" comes from the app's own checks (a slide with too many words). */
  issues: { severity: "minor" | "major" | "blocker"; problem: string; fix_instruction: string }[];
  verdict: "pass" | "revise" | "reject";
};

export type PostVersion = {
  number: number;
  headline: string;
  caption: string;
  image_prompt: string;
  /** 3 to 5 key points, one slide each. */
  points: string[];
  /** The one number that matters, shown big on its own slide ({} if none). */
  figure: {
    value?: string;
    label?: string;
    compare?: { label: string; amount: number; display: string }[];
  };
  /** A sentence copied word for word from the article ({} if none). */
  quote: { text?: string; speaker?: string };
  /** Why it matters, on the closing slide. */
  takeaway: string;
  slide_count: number;
  /** True for your own wording, saved with "Edit the wording" (never re-checked). */
  edited_by_user: boolean;
  review: Review | null;
};

export type GenerationStep = {
  stage: string;
  succeeded: boolean;
  duration_ms: number;
  error: string;
  providers: string;
  prompt_versions: string;
  input_tokens: number;
  output_tokens: number;
  created_at: string;
};

export type Publication = {
  id: string;
  account_name: string | null;
  platform: string | null;
  status: "publishing" | "published" | "failed" | "ambiguous";
  external_id: string;
  error: string;
  demo_mode: boolean;
  published_at: string | null;
  resolved_by: "" | "platform" | "user";
};

export type PostDetail = Post & {
  article: {
    title: string;
    url: string;
    source_name: string;
    published_at: string;
  } | null;
  poster_url: string | null;
  /** The final version's slides, cover first (empty for posts made before slides). */
  slide_urls: string[];
  /** The number of the version shown and published (best-reviewed, or your edit). */
  final_version: number | null;
  versions: PostVersion[];
  steps: GenerationStep[];
  publications: Publication[];
};

export type Notification = {
  id: string;
  kind: string;
  title: string;
  message: string;
  related_type: string;
  related_id: string | null;
  created_at: string;
  read_at: string | null;
};

export type Page<T> = { next: string | null; previous: string | null; results: T[] };
