"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PipelineTrack } from "@/components/PipelineTrack";
import { PosterImage } from "@/components/PosterImage";
import { SlideGallery } from "@/components/SlideGallery";
import { Publications, ReviewPanel, Steps, Versions } from "@/components/PostParts";
import { Button, ErrorNote, Loading, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen, isInProgress } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { PostDetail, PostVersion } from "@/lib/types";

/** The version that is shown and will be published, as the API says. */
function shownVersion(post: PostDetail): PostVersion | undefined {
  return post.versions.find((version) => version.number === post.final_version);
}

/** True while the post may change soon: being made, or approved and due. */
function changesSoon(post: PostDetail): boolean {
  if (isInProgress(post.status)) return true;
  const due = !post.scheduled_for || new Date(post.scheduled_for).getTime() <= Date.now();
  return post.status === "approved" && due;
}

function EditForm({ post, version, onSaved, onCancel }: { post: PostDetail; version: PostVersion; onSaved: (post: PostDetail) => void; onCancel: () => void }) {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const points = String(form.get("points"))
        .split("\n")
        .map((point) => point.trim())
        .filter(Boolean);
      onSaved(await api.editPost(post.id, String(form.get("headline")), String(form.get("caption")), points));
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm">Headline (on the poster)</span>
        <input name="headline" defaultValue={version.headline} maxLength={90} className="border-b border-body/50 py-2 text-xl text-ink outline-none focus:border-signal" />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm">Key points, one slide each (one per line, up to 5)</span>
        <textarea name="points" defaultValue={version.points.join("\n")} rows={5} className="border border-body/40 p-3 text-ink outline-none focus:border-signal" />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm">Caption</span>
        <textarea name="caption" defaultValue={version.caption} rows={8} maxLength={3000} required className="border border-body/40 p-3 text-ink outline-none focus:border-signal" />
      </label>
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button type="submit" busy={busy}>Save my version</Button>
        <Button type="button" variant="quiet" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

function Decision({ post, onChange }: { post: PostDetail; onChange: (post: PostDetail) => void }) {
  const [busy, setBusy] = useState<"" | "approve" | "reject">("");
  const [error, setError] = useState<unknown>(null);
  async function decide(choice: "approve" | "reject") {
    setBusy(choice);
    setError(null);
    try {
      onChange(choice === "approve" ? await api.approve(post.id) : await api.reject(post.id));
    } catch (caught) {
      setError(caught);
    }
    setBusy("");
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button busy={busy === "approve"} onClick={() => decide("approve")}>
          {post.scheduled_for ? "Approve for its time" : "Approve and post"}
        </Button>
        <Button variant="danger" busy={busy === "reject"} onClick={() => decide("reject")}>
          Reject
        </Button>
      </div>
      <ErrorNote error={error} />
    </div>
  );
}

export default function PostPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useSession();
  const [post, setPost] = useState<PostDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => api.post(id).then(setPost).catch(setError), [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!post || !changesSoon(post)) return;
    const timer = setTimeout(load, 3000);
    return () => clearTimeout(timer);
  }, [post, load]);

  if (error) return <ErrorNote error={error} />;
  if (!post) return <Loading />;
  const version = shownVersion(post);

  return (
    <article>
      <Link href="/app/posts" className="underline-offset-4 hover:underline">
        All posts
      </Link>
      <header className="mt-6 flex flex-col gap-4 border-b border-ink/20 pb-6">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={post.status} />
          {post.demo_mode && <span className="text-sm">Demo mode: made from fictional demo news</span>}
        </div>
        <h1 className="max-w-4xl text-headline text-ink">{version?.headline ?? `${post.topic_name ?? "Post"} for ${post.plan_name}`}</h1>
        <p>
          {post.plan_name}
          {post.scheduled_for && `, posts ${formatWhen(post.scheduled_for, user?.timezone)}`}
        </p>
        <PipelineTrack status={post.status} />
        {post.status_reason && <p className="text-ink">{post.status_reason}</p>}
      </header>

      <div className="mt-10 grid gap-12 lg:grid-cols-[minmax(0,26rem)_1fr]">
        <div className="flex flex-col gap-6">
          {post.slide_urls.length > 0 ? (
            <>
              <SlideGallery key={post.versions.length} slideUrls={post.slide_urls} headline={version?.headline ?? "Post"} />
              <details>
                <summary className="min-h-11 cursor-pointer py-2 text-ink">The one image for X, Facebook and Buffer</summary>
                <div className="mt-2">
                  <PosterImage postId={post.id} version={post.versions.length} alt={`Square image: ${version?.headline ?? "Poster"}`} />
                </div>
              </details>
            </>
          ) : post.poster_url ? (
            <PosterImage postId={post.id} version={post.versions.length} alt={version?.headline ?? "Poster"} />
          ) : (
            <div className="aspect-square bg-mist" />
          )}
          {post.article && (
            <p className="text-sm">
              Based on{" "}
              <a href={post.article.url} target="_blank" rel="noreferrer" className="text-ink underline underline-offset-4">
                {post.article.title}
              </a>{" "}
              ({post.article.source_name})
            </p>
          )}
        </div>
        <div className="flex flex-col gap-10">
          {version && !editing && (
            <section aria-label="Caption">
              {version.points.length > 0 && (
                <ol className="mb-6 flex flex-col gap-2 border-l-2 border-signal pl-4">
                  {version.points.map((point, index) => (
                    <li key={index} className="flex gap-3 text-ink">
                      <span className="text-signal tabular-nums">{index + 1}</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ol>
              )}
              {(version.figure?.value || version.quote?.text || version.takeaway) && (
                <dl className="mb-6 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                  {version.figure?.value && (
                    <>
                      <dt>Figure</dt>
                      <dd className="text-ink">
                        <span className="font-semibold">{version.figure.value}</span> {version.figure.label}
                      </dd>
                    </>
                  )}
                  {version.quote?.text && (
                    <>
                      <dt>Quote</dt>
                      <dd className="text-ink">
                        “{version.quote.text}”{version.quote.speaker && ` — ${version.quote.speaker}`}
                      </dd>
                    </>
                  )}
                  {version.takeaway && (
                    <>
                      <dt>Takeaway</dt>
                      <dd className="text-ink">{version.takeaway}</dd>
                    </>
                  )}
                </dl>
              )}
              <p className="whitespace-pre-line text-lg text-ink">{version.caption}</p>
              {post.status === "awaiting_approval" && (
                <Button variant="quiet" className="mt-2 px-0" onClick={() => setEditing(true)}>
                  Edit the wording
                </Button>
              )}
            </section>
          )}
          {version && editing && (
            <EditForm post={post} version={version} onCancel={() => setEditing(false)} onSaved={(saved) => { setPost(saved); setEditing(false); }} />
          )}
          {post.status === "awaiting_approval" && !editing && <Decision post={post} onChange={setPost} />}
          <section aria-labelledby="check">
            <h2 id="check" className="border-b border-ink/30 pb-2 text-title text-ink">The check</h2>
            <div className="mt-4"><ReviewPanel review={version?.review ?? null} yourWords={version?.edited_by_user} /></div>
          </section>
          {post.publications.length > 0 && (
            <section aria-labelledby="where">
              <h2 id="where" className="border-b border-ink/30 pb-2 text-title text-ink">Where it went</h2>
              <div className="mt-2"><Publications publications={post.publications} onChange={load} timeZone={user?.timezone} /></div>
            </section>
          )}
          {post.versions.length > 1 && (
            <section aria-labelledby="versions">
              <h2 id="versions" className="border-b border-ink/30 pb-2 text-title text-ink">Versions</h2>
              <div className="mt-2"><Versions versions={post.versions} /></div>
            </section>
          )}
          <details className="group">
            <summary className="min-h-11 cursor-pointer py-2 text-ink">How it was made (step log)</summary>
            <div className="mt-2"><Steps steps={post.steps} /></div>
          </details>
        </div>
      </div>
    </article>
  );
}
