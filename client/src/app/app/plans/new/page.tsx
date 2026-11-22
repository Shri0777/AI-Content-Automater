"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { cleanRules, ScheduleEditor } from "@/components/ScheduleEditor";
import { TopicPicker } from "@/components/TopicPicker";
import { Button, ErrorNote, Field, fieldErrors, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ScheduleRule, SocialAccount, Topic, TopicCatalogue } from "@/lib/types";

function Choice({ name, value, checked, onChange, title, hint, type = "checkbox" }: { name: string; value: string; checked: boolean; onChange: () => void; title: string; hint?: string; type?: "checkbox" | "radio" }) {
  return (
    <label className={`flex cursor-pointer gap-3 border p-4 transition-colors ${checked ? "border-ink bg-mist/60" : "border-ink/20 hover:border-ink/50"}`}>
      <input type={type} name={name} value={value} checked={checked} onChange={onChange} className="mt-1 size-5 accent-signal" />
      <span>
        <span className="block text-ink">{title}</span>
        {hint && <span className="block text-sm">{hint}</span>}
      </span>
    </label>
  );
}

export default function NewPlanPage() {
  const router = useRouter();
  const { user } = useSession();
  const [accounts, setAccounts] = useState<SocialAccount[] | null>(null);
  const [catalogue, setCatalogue] = useState<TopicCatalogue | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [accountIds, setAccountIds] = useState<string[]>([]);
  const [mode, setMode] = useState<"manual" | "auto">("manual");
  const [artwork, setArtwork] = useState(false);
  const [colour, setColour] = useState("#0E1634");
  const [rules, setRules] = useState<ScheduleRule[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.topicCatalogue().then(setCatalogue).catch(setError);
  }, []);

  useEffect(() => {
    api.accounts().then((found) => {
      setAccounts(found);
      setAccountIds(found.filter((account) => account.status === "active").map((account) => account.id));
    }).catch(setError);
  }, []);

  function toggle<T>(list: T[], item: T): T[] {
    return list.includes(item) ? list.filter((current) => current !== item) : [...list, item];
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const plan = await api.createPlan({
        name: String(form.get("name")),
        requirements: String(form.get("requirements")),
        approval_mode: mode,
        ai_artwork_enabled: artwork,
        brand_colour: colour.toUpperCase(),
        lead_time_minutes: Number(form.get("lead_time_minutes")),
        max_lateness_minutes: Number(form.get("max_lateness_minutes")),
        on_missed_approval: form.get("on_missed_approval") === "hold" ? "hold" : "expire",
        topics,
        account_ids: accountIds,
        schedule_rules: cleanRules(rules),
      });
      router.push(`/app/plans/${plan.id}`);
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  if (!accounts) return <Loading />;

  return (
    <>
      <PageHeader title="New plan" intro="What to post about, where, and when." />
      {accounts.length === 0 ? (
        <p className="mt-8 text-lg">
          First <Link href="/app/accounts" className="text-signal underline underline-offset-4">connect a social account</Link>: a plan needs somewhere to post.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="mt-10 flex max-w-3xl flex-col gap-12">
          <section className="flex flex-col gap-6">
            <Field label="Plan name" name="name" required maxLength={100} placeholder="Weekday tech news" errors={fieldErrors(error, "name")} />
            <label className="flex flex-col gap-1.5">
              <span className="text-sm">What you want (the AI follows this when choosing and writing)</span>
              <textarea name="requirements" rows={3} placeholder="Short, friendly posts for junior developers. No hype." className="border border-body/40 p-3 text-ink outline-none focus:border-signal" />
            </label>
          </section>
          <section aria-labelledby="topics-title" className="flex flex-col gap-3">
            <h2 id="topics-title" className="text-title text-ink">Topics</h2>
            {catalogue ? <TopicPicker catalogue={catalogue} topics={topics} onChange={setTopics} /> : <Loading />}
          </section>
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-3 text-title text-ink">Post to</legend>
            {accounts.map((account) => (
              <Choice key={account.id} name="accounts" value={account.id} checked={accountIds.includes(account.id)} onChange={() => setAccountIds(toggle(accountIds, account.id))} title={account.display_name} hint={account.status === "active" ? undefined : "Needs reconnecting"} />
            ))}
          </fieldset>
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-3 text-title text-ink">Approval</legend>
            <Choice type="radio" name="mode" value="manual" checked={mode === "manual"} onChange={() => setMode("manual")} title="Ask me before every post" />
            <Choice type="radio" name="mode" value="auto" checked={mode === "auto"} onChange={() => setMode("auto")} title="Post on its own when the check is spotless" hint="Anything less than a clean pass still waits for you." />
          </fieldset>
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-3 text-title text-ink">Look</legend>
            <p className="text-sm">
              Each post is a set of slides: a cover, the key number, one slide per point and a closing slide.
            </p>
            <label className="flex flex-wrap items-center gap-3">
              <input type="color" name="brand_colour" value={colour} onChange={(event) => setColour(event.target.value)} className="h-11 w-14 cursor-pointer border border-ink/25 bg-paper" />
              <span>
                <span className="block text-ink">Slide colour</span>
                <span className="block text-sm">Text colours are picked from it so they always stay readable.</span>
              </span>
            </label>
            <Choice name="ai_artwork" value="on" checked={artwork} onChange={() => setArtwork(!artwork)} title="Add AI artwork to the cover" hint="Off by default: readers trust posts less when they look AI-made. Needs an image key." />
          </fieldset>
          <section>
            <h2 className="mb-4 text-title text-ink">When to post</h2>
            <ScheduleEditor rules={rules} onChange={setRules} defaultTimezone={user?.timezone ?? "UTC"} />
          </section>
          <details>
            <summary className="min-h-11 cursor-pointer py-2 text-ink">Timing details</summary>
            <div className="mt-4 grid gap-6 sm:grid-cols-2">
              <Field label="Start making a post (minutes before its time)" name="lead_time_minutes" type="number" min={15} max={1440} defaultValue={60} />
              <Field label="Skip a post this late (minutes)" name="max_lateness_minutes" type="number" min={5} max={240} defaultValue={30} />
              <label className="flex flex-col gap-1.5 text-sm">
                If you have not approved a post by its time
                <select name="on_missed_approval" className="min-h-11 w-full min-w-0 border border-ink/25 px-2 text-ink">
                  <option value="expire">Drop it (old news loses value)</option>
                  <option value="hold">Keep it and post when I approve</option>
                </select>
              </label>
            </div>
          </details>
          <ErrorNote error={error} />
          <Button type="submit" busy={busy} disabled={topics.length === 0 || accountIds.length === 0} className="self-start">
            Create plan
          </Button>
        </form>
      )}
    </>
  );
}
