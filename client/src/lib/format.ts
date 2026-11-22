/* Plain-language labels and dates, in one place so every screen agrees. */

import type { PostStatus } from "@/lib/types";

export const STATUS_LABELS: Record<PostStatus, string> = {
  researching: "Finding an article",
  drafting: "Writing",
  imaging: "Making the poster",
  reviewing: "Checking",
  correcting: "Fixing what the check found",
  awaiting_approval: "Waiting for you",
  approved: "Approved",
  publishing: "Publishing",
  published: "Published",
  rejected: "Rejected",
  expired: "Expired",
  skipped: "Skipped",
  failed: "Failed",
};

/** The five stages a post goes through before it reaches you, in order. */
export const PIPELINE: PostStatus[] = [
  "researching",
  "drafting",
  "imaging",
  "reviewing",
  "awaiting_approval",
];


export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function formatWhen(iso: string | null, timeZone?: string): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

export function timeAgo(iso: string): string {
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(seconds) < 60) return rtf.format(-seconds, "second");
  if (Math.abs(seconds) < 3600) return rtf.format(-Math.round(seconds / 60), "minute");
  if (Math.abs(seconds) < 86400) return rtf.format(-Math.round(seconds / 3600), "hour");
  return rtf.format(-Math.round(seconds / 86400), "day");
}

/** Statuses that mean "still working on it", so the page should refresh. */
export function isInProgress(status: PostStatus): boolean {
  return ["researching", "drafting", "imaging", "reviewing", "correcting", "publishing"].includes(
    status,
  );
}
