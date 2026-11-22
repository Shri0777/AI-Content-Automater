/*
 * The five stages a post passes through before it reaches you, as one line
 * that fills up. It is real information (where this post is right now), so
 * the fill animates only when the stage changes.
 */

import { PIPELINE, STATUS_LABELS } from "@/lib/format";
import type { PostStatus } from "@/lib/types";

const DONE_AFTER_PIPELINE: PostStatus[] = ["approved", "publishing", "published", "rejected", "expired"];

function stageIndex(status: PostStatus): number {
  if (status === "correcting") return PIPELINE.indexOf("reviewing");
  if (DONE_AFTER_PIPELINE.includes(status)) return PIPELINE.length;
  return PIPELINE.indexOf(status);
}

export function PipelineTrack({ status }: { status: PostStatus }) {
  const reached = stageIndex(status);
  if (reached < 0) return null;
  return (
    <ol className="grid grid-cols-5 gap-1" aria-label="Progress of this post">
      {PIPELINE.map((stage, index) => {
        const done = index < reached || (index === reached && stage === "awaiting_approval");
        const current = index === reached && !done;
        return (
          <li key={stage} className="flex flex-col gap-2">
            <span className="relative block h-1 overflow-hidden bg-mist">
              {(done || current) && (
                <span
                  key={`${stage}-${done}`}
                  className={`fill absolute inset-0 ${done ? "bg-ink" : "bg-signal/60"}`}
                />
              )}
            </span>
            <span
              className={`text-xs sm:text-sm ${current ? "text-ink" : "text-body/70"}`}
              aria-current={current ? "step" : undefined}
            >
              {STATUS_LABELS[stage]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
