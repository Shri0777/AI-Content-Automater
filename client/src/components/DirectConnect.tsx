"use client";

/*
 * Connect X, LinkedIn or a Facebook Page directly. These platforms only let
 * an app registered with them ask for permission to post, so the user first
 * creates their own developer app, registers our callback address in it, and
 * saves the app's id and secret here (the secret is stored encrypted). Then
 * "Connect" sends them to the platform to approve.
 */

import { useState } from "react";

import { Button, ErrorNote, Field, fieldErrors } from "@/components/ui";
import { api } from "@/lib/api";
import type { Platform } from "@/lib/types";

type Guide = { site: string; siteName: string; steps: string[]; idLabel: string; secretLabel: string; note?: string };

const GUIDES: Record<string, Guide> = {
  x: {
    site: "https://docs.x.com/fundamentals/developer-apps",
    siteName: "X developer apps guide",
    steps: [
      "In the X developer portal, create a project and an app.",
      "In the app's user authentication settings, turn on OAuth 2.0, choose “Web App” and “Read and write”.",
      "Add the callback address below exactly as shown.",
      "Copy the OAuth 2.0 Client ID and Client Secret into the fields here.",
    ],
    idLabel: "OAuth 2.0 Client ID",
    secretLabel: "Client Secret",
  },
  linkedin: {
    site: "https://www.linkedin.com/developers/apps",
    siteName: "LinkedIn developer apps",
    steps: [
      "Create an app (LinkedIn asks for a company page to attach it to).",
      "On the Products tab, add “Sign In with LinkedIn using OpenID Connect” and “Share on LinkedIn”.",
      "On the Auth tab, add the callback address below as an authorized redirect URL.",
      "Copy the Client ID and Primary Client Secret into the fields here.",
    ],
    idLabel: "Client ID",
    secretLabel: "Primary Client Secret",
  },
  facebook: {
    site: "https://developers.facebook.com/apps",
    siteName: "Meta for Developers",
    steps: [
      "Create an app that uses Facebook Login.",
      "In Facebook Login settings, add the callback address below to Valid OAuth Redirect URIs.",
      "In App settings, Basic, copy the App ID and App Secret into the fields here.",
    ],
    idLabel: "App ID",
    secretLabel: "App Secret",
    note: "Until Meta reviews your app, only people with a role on it (you) can connect.",
  },
};

function CallbackAddress({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(url).catch(() => undefined);
    setCopied(true);
  }
  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm">Callback address</span>
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 break-all bg-mist px-3 py-2.5 text-sm text-ink">{url}</code>
        <Button type="button" variant="secondary" onClick={copy}>{copied ? "Copied" : "Copy"}</Button>
      </div>
      {url.includes("localhost") && (
        <p className="text-sm">
          X asks for 127.0.0.1 instead of localhost when testing on your own computer. If it refuses this
          address, set PUBLIC_API_URL=http://127.0.0.1:8000 in .env and restart the API.
        </p>
      )}
    </div>
  );
}

function AppForm({ platform, guide, onSaved, onCancel }: { platform: Platform; guide: Guide; onSaved: () => void; onCancel?: () => void }) {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await api.savePlatformApp(platform.platform, String(form.get("client_id")).trim(), String(form.get("client_secret")).trim());
      onSaved();
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <ol className="flex list-decimal flex-col gap-1.5 pl-5">
        {guide.steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
      <a href={guide.site} target="_blank" rel="noreferrer" className="self-start text-signal underline underline-offset-4">
        Open {guide.siteName}
      </a>
      {platform.callback_url && <CallbackAddress url={platform.callback_url} />}
      <Field label={guide.idLabel} name="client_id" id={`${platform.platform}-client-id`} autoComplete="off" required maxLength={255} errors={fieldErrors(error, "client_id")} />
      <Field label={guide.secretLabel} name="client_secret" id={`${platform.platform}-client-secret`} type="password" autoComplete="new-password" required maxLength={500} errors={fieldErrors(error, "client_secret")} />
      {guide.note && <p className="text-sm">{guide.note}</p>}
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <Button type="submit" busy={busy}>Save app</Button>
        {onCancel && <Button type="button" variant="quiet" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

export function DirectConnect({ platform, onChange }: { platform: Platform; onChange: () => void }) {
  const guide = GUIDES[platform.platform];
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      const { authorization_url } = await api.startLink(platform.platform);
      window.location.assign(authorization_url);
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  async function removeApp() {
    if (!window.confirm(`Remove your ${platform.name} app? Accounts connected through it will need connecting again.`)) return;
    await api.deletePlatformApp(platform.platform).catch(setError);
    onChange();
  }

  const showForm = guide && (editing || (!platform.ready && open));
  return (
    <li className="flex flex-col gap-4 border-b border-ink/10 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-ink">{platform.name}</p>
          <p className="text-sm">
            {platform.app_saved ? "Using your developer app" : platform.ready ? "Using this server's app" : "Needs your developer app"}
          </p>
        </div>
        {platform.ready && !editing ? (
          <Button variant="secondary" busy={busy} onClick={connect}>Connect</Button>
        ) : (
          !showForm && guide && <Button variant="secondary" onClick={() => setOpen(true)}>Set up</Button>
        )}
      </div>
      {platform.app_saved && !editing && (
        <div className="flex gap-4 text-sm">
          <button type="button" className="min-h-11 underline-offset-4 hover:underline" onClick={() => setEditing(true)}>Replace app</button>
          <button type="button" className="min-h-11 text-danger underline-offset-4 hover:underline" onClick={removeApp}>Remove app</button>
        </div>
      )}
      {showForm && (
        <AppForm
          platform={platform}
          guide={guide}
          onSaved={() => { setEditing(false); setOpen(false); onChange(); }}
          onCancel={() => { setEditing(false); setOpen(false); }}
        />
      )}
      <ErrorNote error={error} />
    </li>
  );
}
