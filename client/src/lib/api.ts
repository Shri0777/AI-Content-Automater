/*
 * Every call to the backend goes through this file.
 *
 * - The short-lived access token is kept in memory only (never in
 *   localStorage), as ADR-009 asks. The long-lived refresh token is an
 *   httpOnly cookie the browser sends to /auth/refresh/ by itself.
 * - When a request gets 401, the token is refreshed once and the request
 *   is tried again.
 * - Errors come back in one shape ({status, code, title, detail, errors}),
 *   turned into an ApiError the pages can show.
 */

import type {
  BufferChannel,
  Credential,
  LimitUsage,
  Notification,
  Page,
  Plan,
  Platform,
  PlatformApp,
  Post,
  PostDetail,
  PostSlot,
  Publication,
  ScheduleRule,
  SocialAccount,
  Summary,
  Topic,
  TopicCatalogue,
  User,
} from "@/lib/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;
let refreshing: Promise<LoginResult | null> | null = null;

export type LoginResult = { access: string; user: User };

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string[]>;

  constructor(status: number, code: string, detail: string, fields = {}) {
    super(detail);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

/** Ask for a new access token with the refresh cookie; null if logged out. */
export function refreshSession(): Promise<LoginResult | null> {
  if (refreshing === null) {
    refreshing = fetch(`${API_URL}/auth/refresh/`, {
      method: "POST",
      credentials: "include",
      // The backend only honours the cookie with this header: a form on
      // another website cannot add it.
      headers: { "X-Requested-By": "ai-content-automator" },
    })
      .then(async (response) => {
        if (!response.ok) {
          setAccessToken(null);
          return null;
        }
        const result = (await response.json()) as LoginResult;
        setAccessToken(result.access);
        return result;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const problem = await response.json();
    return new ApiError(
      response.status,
      problem.code ?? "error",
      problem.detail ?? "Something went wrong.",
      problem.errors ?? {},
    );
  } catch {
    return new ApiError(response.status, "error", "The server sent an unexpected answer.");
  }
}

async function request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "offline", "Could not reach the server. Is the backend running?");
  }
  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return request<T>(method, path, body, false);
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Fetch an image that needs the login token; return a local object URL. */
export async function fetchImageUrl(path: string): Promise<string> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    credentials: "include",
  });
  if (!response.ok) throw await toApiError(response);
  return URL.createObjectURL(await response.blob());
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});

export const api = {
  register: (email: string, password: string, invite_code: string) =>
    post<User & { recovery_codes: string[] }>("/auth/register/", { email, password, invite_code }),
  login: (email: string, password: string) =>
    post<LoginResult>("/auth/login/", { email, password }),
  logout: () =>
    fetch(`${API_URL}/auth/logout/`, {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-By": "ai-content-automator" },
    }),
  recover: (email: string, recovery_code: string, new_password: string) =>
    post<{ detail: string; recovery_codes_left: number }>("/auth/recover/", {
      email,
      recovery_code,
      new_password,
    }),
  newRecoveryCodes: (password: string) =>
    post<{ recovery_codes: string[] }>("/auth/recovery-codes/", { password }),

  me: () => get<User>("/me/"),
  updateMe: (timezone: string) => request<User>("PATCH", "/me/", { timezone }),
  summary: () => get<Summary>("/me/summary/"),
  usage: () => get<{ tier: string; limits: LimitUsage[] }>("/me/usage/"),

  credentials: () => get<Credential[]>("/credentials/"),
  saveCredential: (details: Record<string, string>) => post<Credential>("/credentials/", details),
  testCredential: (id: string) => post<Credential>(`/credentials/${id}/test/`),
  deleteCredential: (id: string) => request<void>("DELETE", `/credentials/${id}/`),

  accounts: () => get<SocialAccount[]>("/social/accounts/"),
  platforms: () => get<Platform[]>("/social/platforms/"),
  bufferChannels: (api_key: string) =>
    post<BufferChannel[]>("/social/buffer/channels/", { api_key }),
  linkBuffer: (api_key: string, channel_ids: string[]) =>
    post<SocialAccount[]>("/social/link/buffer/", { api_key, channel_ids }),
  linkDemo: () => post<SocialAccount>("/social/link/demo/"),
  platformApps: () => get<PlatformApp[]>("/social/apps/"),
  savePlatformApp: (platform: string, client_id: string, client_secret: string) =>
    request<PlatformApp>("PUT", `/social/apps/${platform}/`, { client_id, client_secret }),
  deletePlatformApp: (platform: string) => request<void>("DELETE", `/social/apps/${platform}/`),
  startLink: (platform: string) =>
    post<{ authorization_url: string }>(`/social/link/${platform}/start/`),
  unlink: (id: string) => request<void>("DELETE", `/social/accounts/${id}/`),

  topicCatalogue: () => get<TopicCatalogue>("/news/topics/"),
  plans: () => get<Plan[]>("/plans/"),
  plan: (id: string) => get<Plan>(`/plans/${id}/`),
  createPlan: (details: PlanInput) => post<Plan>("/plans/", details),
  deletePlan: (id: string) => request<void>("DELETE", `/plans/${id}/`),
  pausePlan: (id: string) => post<Plan>(`/plans/${id}/pause/`),
  resumePlan: (id: string) => post<Plan>(`/plans/${id}/resume/`),
  replaceSchedule: (id: string, schedule_rules: ScheduleRule[]) =>
    request<Plan>("PUT", `/plans/${id}/schedule/`, { schedule_rules }),
  upcoming: (id: string) => get<PostSlot[]>(`/plans/${id}/upcoming/`),
  generateNow: (id: string) => post<PostDetail>(`/plans/${id}/generate-now/`),

  posts: (status = "") => get<Page<Post>>(status ? `/posts/?status=${status}` : "/posts/"),
  postPage: (url: string) => get<Page<Post>>(url.replace(API_URL, "")),
  post: (id: string) => get<PostDetail>(`/posts/${id}/`),
  editPost: (id: string, headline: string, caption: string, points: string[]) =>
    request<PostDetail>("PATCH", `/posts/${id}/`, { headline, caption, points }),
  approve: (id: string) => post<PostDetail>(`/posts/${id}/approve/`),
  reject: (id: string) => post<PostDetail>(`/posts/${id}/reject/`),
  resolvePublication: (id: string, outcome: "published" | "not_published") =>
    post<Publication>(`/publications/${id}/resolve/`, { outcome }),

  notifications: (unreadOnly = false) =>
    get<Page<Notification>>(unreadOnly ? "/notifications/?unread=true" : "/notifications/"),
  markRead: (id: string) => post<Notification>(`/notifications/${id}/read/`),
  markAllRead: () => post<{ marked_read: number }>("/notifications/read-all/"),
};

export type PlanInput = {
  name: string;
  requirements: string;
  approval_mode: "manual" | "auto";
  ai_artwork_enabled?: boolean;
  brand_colour?: string;
  lead_time_minutes: number;
  max_lateness_minutes: number;
  on_missed_approval: "expire" | "hold";
  topics: Topic[];
  account_ids: string[];
  schedule_rules: ScheduleRule[];
};
