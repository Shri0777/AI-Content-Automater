"use client";

/*
 * Your own AI keys: one text model (writes and checks posts) and one image
 * model (paints the artwork). Keys are sent once, stored encrypted, and
 * only their last four characters are ever shown again.
 */

import { useCallback, useEffect, useState } from "react";

import { Button, ErrorNote, Field, fieldErrors, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Credential, CredentialKind } from "@/lib/types";

type Provider = { value: string; label: string; needsKey: boolean; urlHint?: string; modelHint: string; models?: string[] };

const PROVIDERS: Record<"text" | "image", Provider[]> = {
  text: [
    {
      value: "anthropic",
      label: "Anthropic Claude",
      needsKey: true,
      modelHint: "The model ID, with dashes: claude-sonnet-5-5, not claude-sonnet-5.5.",
      models: ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"],
    },
    {
      value: "openai_compatible",
      label: "OpenAI-compatible (OpenAI, OpenRouter, Groq, Ollama…)",
      needsKey: false,
      urlHint: "Leave empty for OpenAI. Groq: https://api.groq.com/openai/v1. OpenRouter: https://openrouter.ai/api/v1",
      modelHint: "The model ID exactly as your provider lists it, prefix included. Groq: openai/gpt-oss-120b, not gpt-oss-120b.",
    },
    { value: "demo", label: "Demo (no key, canned text)", needsKey: false, modelHint: "" },
  ],
  image: [
    { value: "fal", label: "fal", needsKey: true, modelHint: "For example fal-ai/flux/schnell" },
    {
      value: "nvidia_flux",
      label: "NVIDIA FLUX",
      needsKey: true,
      modelHint:
        "The API's model ID: black-forest-labs/flux.1-dev. Not the page address (…/flux_1-dev) and not your key's name.",
      models: ["black-forest-labs/flux.1-dev"],
    },
    {
      value: "openai_compatible",
      label: "OpenAI-compatible images",
      needsKey: false,
      urlHint: "Leave empty for OpenAI.",
      modelHint: "The image model name your provider lists",
    },
    { value: "demo", label: "Demo (no key, generated shapes)", needsKey: false, modelHint: "" },
  ],
};

const STATUS_TEXT: Record<Credential["status"], string> = {
  unverified: "Not checked yet",
  verified: "Working",
  invalid: "The provider refused this key",
};

/** "unverified" after a check means the check failed for a reason other than the key. */
function statusOf(credential: Credential): { text: string; tone: string } {
  if (credential.status === "verified") return { text: STATUS_TEXT.verified, tone: "text-ok" };
  if (credential.status === "invalid") return { text: STATUS_TEXT.invalid, tone: "text-danger" };
  if (credential.last_checked_at) return { text: "The test failed", tone: "text-danger" };
  return { text: STATUS_TEXT.unverified, tone: "text-caution" };
}

function SavedKey({ credential, onChange }: { credential: Credential; onChange: () => void }) {
  const { user } = useSession();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  async function run(name: string, action: () => Promise<unknown>) {
    setBusy(name);
    setError(null);
    await action().catch(setError);
    setBusy("");
    onChange();
  }
  const { text, tone } = statusOf(credential);
  return (
    <div className="bg-mist p-5">
      <p className="text-ink">
        {credential.adapter}
        {credential.model_name && `, ${credential.model_name}`}
      </p>
      <p className="text-sm">{credential.key_hint ? `Key ending ${credential.key_hint}` : "No key"}{credential.base_url && `, ${credential.base_url}`}</p>
      <p className={`mt-2 ${tone}`}>
        {text}
        {credential.last_checked_at && <span className="text-sm text-body">, checked {formatWhen(credential.last_checked_at, user?.timezone)}</span>}
      </p>
      {credential.last_error && <p className="mt-1 text-sm text-danger">{credential.last_error}</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" busy={busy === "test"} onClick={() => run("test", () => api.testCredential(credential.id))}>Test connection</Button>
        <Button variant="quiet" busy={busy === "delete"} onClick={() => run("delete", () => api.deleteCredential(credential.id))}>Remove</Button>
      </div>
      <div className="mt-3"><ErrorNote error={error} /></div>
    </div>
  );
}

function KeyForm({ kind, replacing, onSaved }: { kind: "text" | "image"; replacing: boolean; onSaved: () => void }) {
  const [adapter, setAdapter] = useState(PROVIDERS[kind][0].value);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const provider = PROVIDERS[kind].find((item) => item.value === adapter) ?? PROVIDERS[kind][0];

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const details: Record<string, string> = { kind, adapter };
      for (const name of ["model_name", "base_url", "api_key"]) {
        const value = String(form.get(name) ?? "").trim();
        if (value) details[name] = value;
      }
      await api.saveCredential(details);
      event.currentTarget?.reset();
      onSaved();
    } catch (caught) {
      setError(caught);
    }
    setBusy(false);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <label className="flex flex-col gap-1.5 text-sm">
        Provider
        <select value={adapter} onChange={(event) => setAdapter(event.target.value)} className="min-h-11 w-full min-w-0 border border-ink/25 px-2 text-base text-ink">
          {PROVIDERS[kind].map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </label>
      {adapter !== "demo" && (
        <>
          <Field
            label="Model"
            name="model_name"
            autoComplete="off"
            id={`${kind}-model`}
            required
            list={provider.models ? `${kind}-model-options` : undefined}
            hint={provider.modelHint}
            errors={fieldErrors(error, "model_name")}
          />
          {provider.models && (
            <datalist id={`${kind}-model-options`}>
              {provider.models.map((model) => <option key={model} value={model} />)}
            </datalist>
          )}
          <Field label={provider.needsKey ? "API key" : "API key (if your provider needs one)"} name="api_key" id={`${kind}-key`} type="password" autoComplete="new-password" required={provider.needsKey} errors={fieldErrors(error, "api_key")} />
          {provider.urlHint !== undefined && (
            <Field label="Address (optional)" name="base_url" id={`${kind}-url`} type="url" autoComplete="off" placeholder="https://" hint={provider.urlHint} errors={fieldErrors(error, "base_url")} />
          )}
        </>
      )}
      <ErrorNote error={error} />
      <Button type="submit" busy={busy} className="self-start">{replacing ? "Replace key" : "Save key"}</Button>
    </form>
  );
}

const KINDS: { kind: "text" | "image"; title: string; text: string }[] = [
  { kind: "text", title: "Text model", text: "Chooses articles, writes the caption and image prompt, and checks the post." },
  { kind: "image", title: "Image model", text: "Paints the artwork. The headline is drawn on afterwards, so it is always spelled right." },
];

export default function KeysPage() {
  const [credentials, setCredentials] = useState<Credential[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => api.credentials().then(setCredentials).catch(setError), []);
  useEffect(() => { load(); }, [load]);

  const find = (kind: CredentialKind) => credentials?.find((credential) => credential.kind === kind);

  return (
    <>
      <PageHeader title="AI keys" intro="Your own models do the work and your own keys pay for it. Keys are stored encrypted and never shown again." />
      <ErrorNote error={error} />
      {!credentials && !error && <div className="mt-8"><Loading /></div>}
      {credentials && (
        <div className="mt-10 grid gap-14 xl:grid-cols-2">
          {KINDS.map(({ kind, title, text }) => {
            const saved = find(kind);
            return (
              <section key={kind} aria-labelledby={`${kind}-title`} className="flex flex-col gap-6">
                <div className="border-b border-ink/30 pb-2">
                  <h2 id={`${kind}-title`} className="text-title text-ink">{title}</h2>
                  <p className="mt-1">{text}</p>
                </div>
                {saved && <SavedKey credential={saved} onChange={load} />}
                <KeyForm kind={kind} replacing={Boolean(saved)} onSaved={load} />
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
