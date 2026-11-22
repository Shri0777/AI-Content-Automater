"use client";

/*
 * Connect Buffer in two steps: paste your own Buffer API key, then choose
 * which of your Buffer channels to post to. The key is sent to our server,
 * stored encrypted, and never shown again.
 */

import { useState } from "react";

import { Button, ErrorNote, Field } from "@/components/ui";
import { api } from "@/lib/api";
import type { BufferChannel, SocialAccount } from "@/lib/types";

export function BufferConnect({ onLinked }: { onLinked: (accounts: SocialAccount[]) => void }) {
  const [apiKey, setApiKey] = useState("");
  const [channels, setChannels] = useState<BufferChannel[] | null>(null);
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function findChannels(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const found = await api.bufferChannels(apiKey);
      setChannels(found);
      setChosen(found.map((channel) => channel.id));
    } catch (caught) {
      setError(caught);
    }
    setBusy(false);
  }

  async function connect() {
    setBusy(true);
    setError(null);
    try {
      onLinked(await api.linkBuffer(apiKey, chosen));
      setApiKey("");
      setChannels(null);
    } catch (caught) {
      setError(caught);
    }
    setBusy(false);
  }

  if (channels) {
    return (
      <div className="flex flex-col gap-4">
        <p>Choose the Buffer channels to post to:</p>
        {channels.map((channel) => (
          <label key={channel.id} className="flex items-center gap-3 border border-ink/20 p-3">
            <input
              type="checkbox"
              checked={chosen.includes(channel.id)}
              onChange={() => setChosen(chosen.includes(channel.id) ? chosen.filter((id) => id !== channel.id) : [...chosen, channel.id])}
              className="size-5 accent-signal"
            />
            <span className="text-ink">{channel.name}</span>
            <span className="text-sm">{channel.network}</span>
          </label>
        ))}
        <ErrorNote error={error} />
        <div className="flex gap-2">
          <Button busy={busy} disabled={chosen.length === 0} onClick={connect}>
            Connect {chosen.length} channel{chosen.length === 1 ? "" : "s"}
          </Button>
          <Button variant="quiet" onClick={() => setChannels(null)}>Back</Button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={findChannels} className="flex flex-col gap-4">
      <Field
        label="Your Buffer API key"
        name="buffer_key"
        type="password"
        autoComplete="new-password"
        required
        value={apiKey}
        onChange={(event) => setApiKey(event.target.value)}
        hint="In Buffer: Settings, then API, then create a key."
      />
      <ErrorNote error={error} />
      <Button type="submit" busy={busy} className="self-start">Find my channels</Button>
    </form>
  );
}
