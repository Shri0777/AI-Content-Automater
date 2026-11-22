"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button, Empty, ErrorNote, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen, timeAgo } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Page, Post } from "@/lib/types";

const FILTERS = [
  { status: "", label: "All" },
  { status: "awaiting_approval", label: "Waiting for you" },
  { status: "approved", label: "Approved" },
  { status: "published", label: "Published" },
  { status: "failed", label: "Failed" },
  { status: "skipped", label: "Skipped" },
];

export default function PostsPage() {
  const { user } = useSession();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState<Page<Post> | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    api.posts(filter).then(setPage).catch(setError);
  }, [filter]);

  function choose(status: string) {
    setPage(null);
    setFilter(status);
  }

  async function loadMore() {
    if (!page?.next) return;
    setLoadingMore(true);
    const more = await api.postPage(page.next).catch((caught) => {
      setError(caught);
      return null;
    });
    if (more) setPage({ ...more, results: [...page.results, ...more.results] });
    setLoadingMore(false);
  }

  return (
    <>
      <PageHeader title="Posts" intro="Every post your plans have made, newest first." />
      <div role="group" aria-label="Show posts" className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.status}
            type="button"
            aria-pressed={filter === item.status}
            onClick={() => choose(item.status)}
            className={`min-h-11 border px-4 transition-colors ${
              filter === item.status ? "border-ink bg-ink text-paper" : "border-ink/25 text-ink hover:border-ink"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="mt-8">
        <ErrorNote error={error} />
        {!page && !error && <Loading />}
        {page && page.results.length === 0 && (
          <Empty title="No posts here yet">
            <p>Open a plan and choose “Make a post now”, or wait for its next scheduled time.</p>
          </Empty>
        )}
        {page && page.results.length > 0 && (
          <ul className="border-t border-ink/30">
            {page.results.map((post) => (
              <li key={post.id}>
                <Link
                  href={`/app/posts/${post.id}`}
                  className="grid gap-1 border-b border-ink/10 py-4 hover:bg-mist/40 sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-6"
                >
                  <span>
                    <span className="text-ink">{post.topic_name ?? "Post"}</span>
                    <span className="text-body/80"> for {post.plan_name}</span>
                    {post.status_reason && (
                      <span className="mt-1 block text-sm text-body/80">{post.status_reason}</span>
                    )}
                  </span>
                  <span className="text-sm tabular-nums">
                    {post.scheduled_for ? `Posts ${formatWhen(post.scheduled_for, user?.timezone)}` : timeAgo(post.created_at)}
                  </span>
                  <StatusBadge status={post.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
        {page?.next && (
          <Button variant="secondary" className="mt-6" busy={loadingMore} onClick={loadMore}>
            Show more
          </Button>
        )}
      </div>
    </>
  );
}
