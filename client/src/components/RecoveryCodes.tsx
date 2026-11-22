"use client";

import { useState } from "react";

import { Button } from "@/components/ui";

/** Shows new recovery codes once, with a way to copy them all. */
export function RecoveryCodes({ codes, onDone, doneLabel }: { codes: string[]; onDone: () => void; doneLabel: string }) {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  async function copyAll() {
    await navigator.clipboard.writeText(codes.join("\n"));
    setCopied(true);
  }

  return (
    <div>
      <p className="text-lg">
        These codes reset your password if you forget it. There is no email reset, and they are
        shown only now. Each works once.
      </p>
      <ol className="mt-6 grid grid-cols-2 gap-px bg-ink/15">
        {codes.map((code) => (
          <li key={code} className="bg-paper px-3 py-2.5 text-lg tracking-wide text-ink tabular-nums">
            {code}
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" onClick={copyAll}>
          {copied ? "Copied" : "Copy all codes"}
        </Button>
        <span aria-live="polite" className="sr-only">
          {copied ? "Codes copied to the clipboard" : ""}
        </span>
      </div>
      <label className="mt-8 flex items-start gap-3">
        <input
          type="checkbox"
          checked={saved}
          onChange={(event) => setSaved(event.target.checked)}
          className="mt-1 size-5 accent-signal"
        />
        <span>I have saved these codes somewhere safe.</span>
      </label>
      <Button type="button" className="mt-6 w-full" disabled={!saved} onClick={onDone}>
        {doneLabel}
      </Button>
    </div>
  );
}
