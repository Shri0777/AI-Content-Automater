"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { cleanRules, ScheduleEditor } from "@/components/ScheduleEditor";
import { Button, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Plan, PostSlot, ScheduleRule } from "@/lib/types";

function ScheduleSection({ plan, onSaved }: { plan: Plan; onSaved: (plan: Plan) => void }) {
  const { user } = useSession();
  const [rules, setRules] = useState<ScheduleRule[]>(plan.schedule_rules);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api.replaceSchedule(plan.id, cleanRules(rules)));
      setSaved(true);
    } catch (caught) {
      setError(caught);
    }
    setBusy(false);
  }

  return (
    <section aria-labelledby="schedule">
      <h2 id="schedule" className="mb-4 border-b border-ink/30 pb-2 text-title text-ink">When to post</h2>
      <ScheduleEditor rules={rules} onChange={(changed) => { setRules(changed); setSaved(false); }} defaultTimezone={user?.timezone ?? "UTC"} />
      <div className="mt-4 flex items-center gap-4">
        <Button busy={busy} onClick={save}>Save posting times</Button>
        <span aria-live="polite" className="text-ok">{saved ? "Saved" : ""}</span>
      </div>
      <div className="mt-3"><ErrorNote error={error} /></div>
    </section>
  );
}

function Actions({ plan, onChange }: { plan: Plan; onChange: (plan: Plan) => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);

  async function run(name: string, action: () => Promise<void>) {
    setBusy(name);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(caught);
    }
    setBusy("");
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button busy={busy === "now"} disabled={plan.paused} onClick={() => run("now", async () => { const post = await api.generateNow(plan.id); router.push(`/app/posts/${post.id}`); })}>
          Make a post now
        </Button>
        <Button variant="secondary" busy={busy === "pause"} onClick={() => run("pause", async () => onChange(plan.paused ? await api.resumePlan(plan.id) : await api.pausePlan(plan.id)))}>
          {plan.paused ? "Resume plan" : "Pause plan"}
        </Button>
        <Button
          variant="danger"
          busy={busy === "delete"}
          onClick={() => {
            if (window.confirm(`Delete “${plan.name}” and every post made for it?`)) {
              run("delete", async () => { await api.deletePlan(plan.id); router.push("/app/plans"); });
            }
          }}
        >
          Delete plan
        </Button>
      </div>
      <ErrorNote error={error} />
    </div>
  );
}

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useSession();
  const [plan, setPlan] = useState<Plan | null>(null);
  const [slots, setSlots] = useState<PostSlot[]>([]);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    api.plan(id).then(setPlan).catch(setError);
    api.upcoming(id).then(setSlots).catch(() => setSlots([]));
  }, [id]);

  useEffect(load, [load]);

  function changed(updated: Plan) {
    setPlan(updated);
    api.upcoming(updated.id).then(setSlots).catch(() => setSlots([]));
  }

  if (error) return <ErrorNote error={error} />;
  if (!plan) return <Loading />;

  return (
    <>
      <Link href="/app/plans" className="underline-offset-4 hover:underline">All plans</Link>
      <div className="mt-6">
        <PageHeader title={plan.name} intro={plan.requirements || undefined} />
      </div>
      <div className="mt-8"><Actions plan={plan} onChange={changed} /></div>
      {plan.paused && <p className="mt-6 border-l-2 border-caution pl-3 text-caution">This plan is paused: no posts are made until you resume it.</p>}
      <div className="mt-12 grid gap-12 xl:grid-cols-[1fr_22rem]">
        <ScheduleSection plan={plan} onSaved={changed} />
        <div className="flex flex-col gap-10">
          <section aria-labelledby="next">
            <h2 id="next" className="border-b border-ink/30 pb-2 text-title text-ink">Next posts</h2>
            {slots.length === 0 ? (
              <p className="py-3">Nothing scheduled.</p>
            ) : (
              <ul>
                {slots.slice(0, 8).map((slot) => (
                  <li key={slot.id} className="flex justify-between border-b border-ink/10 py-2.5 tabular-nums">
                    <span className="text-ink">{formatWhen(slot.publish_at, user?.timezone)}</span>
                    {slot.post && <Link href={`/app/posts/${slot.post}`} className="underline-offset-4 hover:underline">Open</Link>}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-labelledby="details">
            <h2 id="details" className="border-b border-ink/30 pb-2 text-title text-ink">Details</h2>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt>Topics</dt>
              <dd className="text-ink">{plan.topics.map((topic) => topic.name).join(", ")}</dd>
              <dt>Posts to</dt>
              <dd className="text-ink">{plan.accounts.map((account) => account.display_name).join(", ") || "No accounts"}</dd>
              <dt>Approval</dt>
              <dd className="text-ink">{plan.approval_mode === "auto" ? `On its own when clean (score ${plan.auto_post_min_score}+ of 30)` : "Asks you first"}</dd>
              <dt>Made</dt>
              <dd className="text-ink">{plan.lead_time_minutes} min before its time</dd>
              <dt>AI label</dt>
              <dd className="text-ink">{plan.ai_label_enabled ? `“${plan.ai_label_text}”` : "Off"}</dd>
              <dt>Cover</dt>
              <dd className="text-ink">{plan.ai_artwork_enabled ? "AI artwork above the headline" : "Plain type, no AI image"}</dd>
              <dt>Colour</dt>
              <dd className="flex items-center gap-2 text-ink">
                <span className="inline-block h-4 w-4 border border-ink/30" style={{ backgroundColor: plan.brand_colour }} aria-hidden="true" />
                {plan.brand_colour}
              </dd>
            </dl>
          </section>
        </div>
      </div>
    </>
  );
}
