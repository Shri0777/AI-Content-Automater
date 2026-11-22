"use client";

import { useEffect, useMemo, useState } from "react";

import { RecoveryCodes } from "@/components/RecoveryCodes";
import { Button, ErrorNote, Field, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { LimitUsage } from "@/lib/types";

function TimezoneSetting() {
  const { user } = useSession();
  const zones = useMemo(() => (typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC"]), []);
  const [zone, setZone] = useState(user?.timezone ?? "UTC");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function save() {
    setError(null);
    try {
      await api.updateMe(zone);
      setSaved(true);
    } catch (caught) {
      setError(caught);
    }
  }
  return (
    <section aria-labelledby="tz" className="flex flex-col gap-4">
      <h2 id="tz" className="border-b border-ink/30 pb-2 text-title text-ink">Your timezone</h2>
      <p>Used for daily limits and for showing times. Each plan&apos;s posting times keep their own timezone.</p>
      <select aria-labelledby="tz" value={zone} onChange={(event) => { setZone(event.target.value); setSaved(false); }} className="min-h-11 w-full min-w-0 max-w-sm border border-ink/25 px-2 text-ink">
        {zones.map((name) => <option key={name}>{name}</option>)}
      </select>
      <div className="flex items-center gap-4">
        <Button onClick={save}>Save timezone</Button>
        <span aria-live="polite" className="text-ok">{saved ? "Saved. Reload to see times in it." : ""}</span>
      </div>
      <ErrorNote error={error} />
    </section>
  );
}

function UsageTable() {
  const [limits, setLimits] = useState<LimitUsage[] | null>(null);
  useEffect(() => { api.usage().then((usage) => setLimits(usage.limits)).catch(() => setLimits([])); }, []);
  if (!limits) return <Loading />;
  const counted = limits.filter((limit) => limit.period !== "setting");
  return (
    <section aria-labelledby="usage">
      <h2 id="usage" className="border-b border-ink/30 pb-2 text-title text-ink">Free plan limits</h2>
      <ul className="mt-2">
        {counted.map((limit) => {
          const share = limit.limit ? Math.min(1, limit.used / limit.limit) : 0;
          return (
            <li key={limit.resource} className="border-b border-ink/10 py-3">
              <div className="flex justify-between gap-4">
                <span className="text-ink">{limit.description}</span>
                <span className="tabular-nums">{limit.used} of {limit.limit}{limit.period === "day" ? " today" : ""}</span>
              </div>
              <div className="mt-2 h-1 bg-mist" aria-hidden="true">
                <div className={`h-1 ${share >= 1 ? "bg-danger" : "bg-ink"}`} style={{ width: `${share * 100}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function NewRecoveryCodes() {
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.newRecoveryCodes(String(new FormData(event.currentTarget).get("password")));
      setCodes(result.recovery_codes);
    } catch (caught) {
      setError(caught);
    }
    setBusy(false);
  }
  return (
    <section aria-labelledby="codes" className="flex flex-col gap-4">
      <h2 id="codes" className="border-b border-ink/30 pb-2 text-title text-ink">Recovery codes</h2>
      {codes ? (
        <RecoveryCodes codes={codes} doneLabel="Done" onDone={() => setCodes(null)} />
      ) : (
        <form onSubmit={handleSubmit} className="flex max-w-md flex-col gap-4">
          <p>Make a new set if you have used most of yours. Your old codes stop working.</p>
          <Field label="Your password" name="password" id="confirm-password" type="password" autoComplete="current-password" required />
          <ErrorNote error={error} />
          <Button type="submit" busy={busy} className="self-start">Make new codes</Button>
        </form>
      )}
    </section>
  );
}

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="mt-10 grid gap-14 xl:grid-cols-2">
        <div className="flex flex-col gap-14">
          <TimezoneSetting />
          <NewRecoveryCodes />
        </div>
        <UsageTable />
      </div>
    </>
  );
}
