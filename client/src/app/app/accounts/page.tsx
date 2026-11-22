"use client";

import { useCallback, useEffect, useState } from "react";

import { BufferConnect } from "@/components/BufferConnect";
import { DirectConnect } from "@/components/DirectConnect";
import { Button, Empty, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Platform, SocialAccount } from "@/lib/types";

function AccountRow({ account, onRemoved }: { account: SocialAccount; onRemoved: () => void }) {
  const { user } = useSession();
  const [busy, setBusy] = useState(false);
  async function remove() {
    if (!window.confirm(`Disconnect ${account.display_name}? Posts will stop going there.`)) return;
    setBusy(true);
    await api.unlink(account.id).catch(() => undefined);
    onRemoved();
  }
  return (
    <li className="flex flex-col gap-2 border-b border-ink/10 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-ink">{account.display_name}</p>
        {account.status === "active" ? (
          account.link_expires_at && <p className="text-sm">Connected until {formatWhen(account.link_expires_at, user?.timezone)}</p>
        ) : (
          <p className="text-sm text-caution">Needs reconnecting{account.last_error ? `: ${account.last_error}` : ""}</p>
        )}
      </div>
      <Button variant="quiet" busy={busy} onClick={remove} className="self-start px-0 sm:self-auto">Disconnect</Button>
    </li>
  );
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[] | null>(null);
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [demoBusy, setDemoBusy] = useState(false);

  const load = useCallback(() => {
    api.accounts().then(setAccounts).catch(setError);
    api.platforms().then(setPlatforms).catch(setError);
  }, []);

  useEffect(load, [load]);

  const demo = platforms.find((platform) => platform.platform === "demo");
  const direct = platforms.filter((platform) => platform.link_method === "oauth");

  async function linkDemo() {
    setDemoBusy(true);
    await api.linkDemo().catch(setError);
    setDemoBusy(false);
    load();
  }

  return (
    <>
      <PageHeader title="Social accounts" intro="Where your posts go. Connect Buffer with your own key, or a platform directly." />
      <ErrorNote error={error} />
      <div className="mt-10 grid gap-14 xl:grid-cols-2">
        <section aria-labelledby="connected">
          <h2 id="connected" className="border-b border-ink/30 pb-2 text-title text-ink">Connected</h2>
          {!accounts && <div className="py-4"><Loading /></div>}
          {accounts?.length === 0 && <div className="mt-4"><Empty title="Nothing connected yet"><p>Connect Buffer to post to the networks you use there.</p></Empty></div>}
          {accounts && accounts.length > 0 && (
            <ul>{accounts.map((account) => <AccountRow key={account.id} account={account} onRemoved={load} />)}</ul>
          )}
        </section>
        <div className="flex flex-col gap-12">
          <section aria-labelledby="buffer">
            <h2 id="buffer" className="mb-4 border-b border-ink/30 pb-2 text-title text-ink">Buffer</h2>
            <BufferConnect onLinked={load} />
          </section>
          {direct.length > 0 && (
            <section aria-labelledby="direct">
              <h2 id="direct" className="border-b border-ink/30 pb-2 text-title text-ink">Connect directly</h2>
              <p className="mt-3">Each platform only lets a registered app post for you, so you set up your own app once, then connect.</p>
              <ul>{direct.map((platform) => <DirectConnect key={platform.platform} platform={platform} onChange={load} />)}</ul>
            </section>
          )}
          {demo?.ready && (
            <section aria-labelledby="demo">
              <h2 id="demo" className="border-b border-ink/30 pb-2 text-title text-ink">Demo network</h2>
              <p className="mt-3">A pretend account that records posts without sending them anywhere. Demo mode only.</p>
              <Button variant="secondary" className="mt-4" busy={demoBusy} onClick={linkDemo}>Add a demo account</Button>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
