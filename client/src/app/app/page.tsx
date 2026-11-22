"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink, ErrorNote, Loading, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen, timeAgo } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Credential, Plan, Post, PostSlot, SocialAccount } from "@/lib/types";

type Overview = {
  credentials: Credential[];
  accounts: SocialAccount[];
  plans: Plan[];
  waiting: Post[];
  recent: Post[];
  upcoming: (PostSlot & { planName: string })[];
};

async function loadOverview(): Promise<Overview> {
  const [credentials, accounts, plans, waiting, recent] = await Promise.all([
    api.credentials(),
    api.accounts(),
    api.plans(),
    api.posts("awaiting_approval"),
    api.posts(),
  ]);
  const slotLists = await Promise.all(
    plans.filter((plan) => !plan.paused).map(async (plan) => {
      const slots = await api.upcoming(plan.id);
      return slots.map((slot) => ({ ...slot, planName: plan.name }));
    }),
  );
  const upcoming = slotLists
    .flat()
    .sort((a, b) => a.publish_at.localeCompare(b.publish_at))
    .slice(0, 5);
  return { credentials, accounts, plans, waiting: waiting.results, recent: recent.results.slice(0, 5), upcoming };
}

function SetupSteps({ overview }: { overview: Overview }) {
  const kinds = overview.credentials.map((credential) => credential.kind);
  const steps = [
    { done: kinds.includes("text") && kinds.includes("image"), label: "Add your text and image AI keys", href: "/app/keys" },
    { done: overview.accounts.length > 0, label: "Connect a social account", href: "/app/accounts" },
    { done: overview.plans.length > 0, label: "Create a plan: topics, times and where to post", href: "/app/plans/new" },
  ];
  if (steps.every((step) => step.done)) return null;
  return (
    <section aria-labelledby="setup" className="mt-10 bg-mist p-6 sm:p-8">
      <h2 id="setup" className="text-title text-ink">
        Three steps before your first post
      </h2>
      <ol className="mt-6 flex flex-col gap-px bg-ink/15">
        {steps.map((step, index) => (
          <li key={step.href} className="flex items-center justify-between gap-4 bg-mist py-4">
            <span className={step.done ? "text-body/60 line-through" : "text-ink"}>
              {index + 1}. {step.label}
            </span>
            {step.done ? (
              <span className="text-ok">Done</span>
            ) : (
              <Link href={step.href} className="shrink-0 text-signal underline-offset-4 hover:underline">
                Do this
              </Link>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

function PostRow({ post }: { post: Post }) {
  return (
    <li>
      <Link
        href={`/app/posts/${post.id}`}
        className="flex flex-col gap-1 border-b border-ink/10 py-4 hover:bg-mist/40 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
      >
        <span>
          <span className="text-ink">{post.topic_name ?? "Post"}</span>
          <span className="text-body/80"> for {post.plan_name}</span>
        </span>
        <span className="flex items-center gap-3 text-sm">
          <span className="text-body/70">{timeAgo(post.updated_at)}</span>
          <StatusBadge status={post.status} />
        </span>
      </Link>
    </li>
  );
}

export default function OverviewPage() {
  const { user } = useSession();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    loadOverview().then(setOverview).catch(setError);
  }, []);

  return (
    <>
      <PageHeader
        title="Overview"
        intro="What needs you now, and what is coming up."
        action={<ButtonLink href="/app/plans/new">New plan</ButtonLink>}
      />
      <ErrorNote error={error} />
      {!overview && !error && <div className="mt-10"><Loading /></div>}
      {overview && (
        <>
          <SetupSteps overview={overview} />
          <div className="mt-12 grid gap-12 xl:grid-cols-2">
            <section aria-labelledby="waiting">
              <h2 id="waiting" className="border-b border-ink/30 pb-3 text-title text-ink">
                Waiting for you
              </h2>
              {overview.waiting.length === 0 ? (
                <p className="py-4">Nothing needs your approval right now.</p>
              ) : (
                <ul>{overview.waiting.map((post) => <PostRow key={post.id} post={post} />)}</ul>
              )}
            </section>
            <section aria-labelledby="upcoming">
              <h2 id="upcoming" className="border-b border-ink/30 pb-3 text-title text-ink">
                Coming up
              </h2>
              {overview.upcoming.length === 0 ? (
                <p className="py-4">No scheduled posts. Give a plan some posting times to see them here.</p>
              ) : (
                <ul>
                  {overview.upcoming.map((slot) => (
                    <li key={slot.id} className="flex justify-between gap-4 border-b border-ink/10 py-4">
                      <span className="text-ink">{slot.planName}</span>
                      <span className="text-right tabular-nums">{formatWhen(slot.publish_at, user?.timezone)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
          <section aria-labelledby="recent" className="mt-12">
            <div className="flex items-baseline justify-between border-b border-ink/30 pb-3">
              <h2 id="recent" className="text-title text-ink">
                Recent posts
              </h2>
              <Link href="/app/posts" className="underline-offset-4 hover:underline">
                All posts
              </Link>
            </div>
            {overview.recent.length === 0 ? (
              <p className="py-4">No posts yet. Open a plan and choose “Make a post now” to see one being made.</p>
            ) : (
              <ul>{overview.recent.map((post) => <PostRow key={post.id} post={post} />)}</ul>
            )}
          </section>
        </>
      )}
    </>
  );
}
