"use client";

/* The detail panels of one post: review, versions, steps and publications. */

import { useState } from "react";

import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import type { GenerationStep, PostVersion, Publication, Review } from "@/lib/types";

const SCORE_NAMES: Record<string, string> = {
  grounding: "Backed by the article",
  relevance: "Fits what you asked for",
  clarity: "Clear",
  tone: "Tone",
  safety: "Safe to post",
  shareability: "Worth sending to a colleague",
};

const VERDICTS: Record<Review["verdict"], string> = {
  pass: "Passed the check",
  revise: "Needs changes",
  reject: "Should not be posted",
};

export function ReviewPanel({ review, yourWords = false }: { review: Review | null; yourWords?: boolean }) {
  if (!review) return <p>{yourWords ? "These are your own words, so the AI did not check them again." : "Not checked yet."}</p>;
  return (
    <div>
      <p className={`text-title ${review.verdict === "pass" ? "text-ok" : review.verdict === "reject" ? "text-danger" : "text-caution"}`}>
        {VERDICTS[review.verdict]}
      </p>
      <dl className="mt-4 flex flex-col gap-2">
        {Object.entries(SCORE_NAMES).map(([key, label]) => {
          const score = review.scores[key] ?? 0;
          return (
            <div key={key} className="grid grid-cols-[1fr_auto] items-center gap-4">
              <dt>{label}</dt>
              <dd className="flex items-center gap-2" aria-label={`${score} out of 5`}>
                <span className="flex gap-0.5" aria-hidden="true">
                  {[1, 2, 3, 4, 5].map((point) => (
                    <span key={point} className={`h-3 w-3 ${point <= score ? "bg-ink" : "bg-mist"}`} />
                  ))}
                </span>
                <span className="w-4 text-right text-ink tabular-nums">{score}</span>
              </dd>
            </div>
          );
        })}
      </dl>
      {review.issues.length > 0 && (
        <ul className="mt-6 flex flex-col gap-3">
          {review.issues.map((issue, index) => (
            <li key={index} className={`border-l-2 pl-3 ${issue.severity === "minor" ? "border-caution" : "border-danger"}`}>
              <p className="text-ink">{issue.problem}</p>
              {issue.fix_instruction && <p className="text-sm">Fix: {issue.fix_instruction}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Versions({ versions }: { versions: PostVersion[] }) {
  if (versions.length < 2) return null;
  return (
    <ol className="flex flex-col gap-px bg-ink/15">
      {versions.map((version) => (
        <li key={version.number} className="bg-paper py-3">
          <p className="text-ink">
            Version {version.number}: {version.headline}
          </p>
          <p className="text-sm">
            {version.review
              ? `${VERDICTS[version.review.verdict]}, ${Object.values(version.review.scores).reduce((a, b) => a + b, 0)} of 30`
              : version.edited_by_user
                ? "Your own words"
                : "Not checked"}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function Steps({ steps }: { steps: GenerationStep[] }) {
  if (steps.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-lg text-left text-sm">
        <thead className="text-body/80">
          <tr className="border-b border-ink/20">
            <th className="py-2 font-normal">Stage</th>
            <th className="py-2 font-normal">Result</th>
            <th className="py-2 font-normal">Time</th>
            <th className="py-2 font-normal">Models</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((step, index) => (
            <tr key={index} className="border-b border-ink/10 align-top">
              <td className="py-2 text-ink">{step.stage}</td>
              <td className={`py-2 ${step.succeeded ? "text-ok" : "text-danger"}`}>
                {step.succeeded ? "Done" : step.error || "Failed"}
              </td>
              <td className="py-2 tabular-nums">{step.duration_ms} ms</td>
              <td className="py-2 break-all">{step.providers || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PUBLICATION_TEXT: Record<Publication["status"], string> = {
  publishing: "Sending",
  published: "Posted",
  failed: "Not posted",
  ambiguous: "Not confirmed",
};

function UnconfirmedActions({ publication, onSettled }: { publication: Publication; onSettled: () => void }) {
  const [busy, setBusy] = useState(false);
  async function settle(outcome: "published" | "not_published") {
    setBusy(true);
    await api.resolvePublication(publication.id, outcome).catch(() => undefined);
    setBusy(false);
    onSettled();
  }
  return (
    <div className="mt-3">
      <p className="text-sm">
        The platform took this post but never answered, so it was not sent again. Check{" "}
        {publication.account_name ?? "the account"} and tell us what you see.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" busy={busy} onClick={() => settle("published")}>
          It is live
        </Button>
        <Button variant="secondary" busy={busy} onClick={() => settle("not_published")}>
          It did not post
        </Button>
      </div>
    </div>
  );
}

export function Publications({ publications, onChange, timeZone }: { publications: Publication[]; onChange: () => void; timeZone?: string }) {
  if (publications.length === 0) return null;
  return (
    <ul className="flex flex-col gap-px bg-ink/15">
      {publications.map((publication) => (
        <li key={publication.id} className="bg-paper py-3">
          <p className="flex flex-wrap justify-between gap-2">
            <span className="text-ink">{publication.account_name ?? "Removed account"}</span>
            <span className={publication.status === "published" ? "text-ok" : publication.status === "failed" ? "text-danger" : "text-caution"}>
              {PUBLICATION_TEXT[publication.status]}
              {publication.published_at && `, ${formatWhen(publication.published_at, timeZone)}`}
            </span>
          </p>
          {publication.error && publication.status === "failed" && <p className="text-sm">{publication.error}</p>}
          {publication.status === "ambiguous" && <UnconfirmedActions publication={publication} onSettled={onChange} />}
        </li>
      ))}
    </ul>
  );
}
