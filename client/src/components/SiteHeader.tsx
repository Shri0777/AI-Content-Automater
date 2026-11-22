"use client";

import Link from "next/link";

import { useSession } from "@/lib/session";

/** The public pages' header: the name, and sign-in or the way back into the app. */
export function SiteHeader({ onDark = false }: { onDark?: boolean }) {
  const { status } = useSession();
  const text = onDark ? "text-paper" : "text-ink";
  return (
    <header className={`relative z-10 flex items-center justify-between px-4 py-5 sm:px-8 ${text}`}>
      <Link href="/" className="text-lg tracking-tight">
        AI Content Automator
      </Link>
      <nav aria-label="Account" className="flex items-center gap-2 sm:gap-4">
        {status === "signed-in" ? (
          <Link href="/app" className="bg-signal px-4 py-2.5 text-paper hover:bg-paper hover:text-ink">
            Open the app
          </Link>
        ) : (
          <>
            <Link href="/login" className="px-3 py-2.5 underline-offset-4 hover:underline">
              Sign in
            </Link>
            <Link href="/register" className="bg-signal px-4 py-2.5 text-paper hover:bg-paper hover:text-ink">
              Create account
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
