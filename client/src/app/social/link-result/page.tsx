"use client";

/*
 * Where X, LinkedIn or Facebook send the user back after "Connect"
 * (the backend redirects here with ?platform=&result=&reason=).
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const REASONS: Record<string, string> = {
  link_failed: "The approval link was old or already used. Try connecting again.",
  quota_exceeded: "You have reached your limit of connected accounts.",
  platform_not_ready: "This platform is not set up on this server yet.",
  platform_error: "The platform refused or did not answer. Try again in a moment.",
};

function Result() {
  const params = useSearchParams();
  const platform = params.get("platform") ?? "the platform";
  const result = params.get("result");
  const reason = params.get("reason") ?? "";
  const title =
    result === "linked" ? `Connected to ${platform}` : result === "cancelled" ? "Connection cancelled" : `Could not connect ${platform}`;
  const text =
    result === "linked"
      ? "Your account is ready. Add it to a plan to start posting there."
      : result === "cancelled"
        ? "Nothing was connected."
        : REASONS[reason] ?? "Something went wrong. Try connecting again.";
  return (
    <>
      <h1 className="text-headline text-ink">{title}</h1>
      <p className="mt-4 text-lg">{text}</p>
      <Link href="/app/accounts" className="mt-8 inline-flex bg-signal px-6 py-3 text-paper hover:bg-ink">
        Back to social accounts
      </Link>
    </>
  );
}

export default function LinkResultPage() {
  return (
    <main className="mx-auto max-w-xl px-4 py-24">
      <Suspense fallback={null}>
        <Result />
      </Suspense>
    </main>
  );
}
