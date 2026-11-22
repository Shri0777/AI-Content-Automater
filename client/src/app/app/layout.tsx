"use client";

/*
 * The signed-in part of the site: a sidebar (a menu button on phones), and a
 * guard that sends anyone not signed in to the sign-in page. The badges poll
 * the cheap /me/summary/ endpoint every 30 seconds.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Summary } from "@/lib/types";

const NAV = [
  { href: "/app", label: "Overview" },
  { href: "/app/posts", label: "Posts" },
  { href: "/app/plans", label: "Plans" },
  { href: "/app/accounts", label: "Social accounts" },
  { href: "/app/keys", label: "AI keys" },
  { href: "/app/notifications", label: "Notifications" },
  { href: "/app/settings", label: "Settings" },
];

function badgeFor(href: string, summary: Summary | null): number {
  if (!summary) return 0;
  if (href === "/app/posts") return summary.posts_awaiting_approval;
  if (href === "/app/notifications") return summary.unread_notifications;
  if (href === "/app/accounts") return summary.accounts_needing_attention;
  return 0;
}

function NavLinks({ summary, onNavigate }: { summary: Summary | null; onNavigate: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="flex flex-col">
      {NAV.map((item) => {
        const active = item.href === "/app" ? pathname === "/app" : pathname.startsWith(item.href);
        const badge = badgeFor(item.href, summary);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`flex items-center justify-between border-l-2 px-4 py-2.5 transition-colors ${
                active ? "border-signal text-ink" : "border-transparent text-body hover:text-ink"
              }`}
            >
              {item.label}
              {badge > 0 && (
                <span className="min-w-6 bg-signal px-1.5 text-center text-sm text-paper tabular-nums">
                  {badge}
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { status, user, signOut } = useSession();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (status === "signed-out") router.replace("/login");
  }, [status, router]);

  useEffect(() => {
    if (status !== "signed-in") return;
    const load = () => api.summary().then(setSummary).catch(() => undefined);
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [status, pathname]);

  if (status !== "signed-in") {
    return (
      <div className="p-8">
        <Loading label="Checking your session" />
      </div>
    );
  }

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[16rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-paper focus:p-3">
        Skip to content
      </a>
      <div className="flex items-center justify-between border-b border-ink/15 px-4 py-3 lg:hidden">
        <Link href="/app" className="text-ink">
          AI Content Automator
        </Link>
        <button
          type="button"
          aria-expanded={menuOpen}
          aria-controls="app-nav"
          onClick={() => setMenuOpen(!menuOpen)}
          className="min-h-11 border border-ink/30 px-4 text-ink"
        >
          {menuOpen ? "Close" : "Menu"}
        </button>
      </div>
      <aside
        id="app-nav"
        className={`${menuOpen ? "block" : "hidden"} border-b border-ink/15 bg-paper lg:sticky lg:top-0 lg:block lg:h-dvh lg:border-r lg:border-b-0`}
      >
        <div className="flex h-full flex-col py-6">
          <Link href="/app" className="hidden px-4 pb-8 text-lg tracking-tight text-ink lg:block">
            AI Content Automator
          </Link>
          <nav aria-label="Main">
            <NavLinks summary={summary} onNavigate={() => setMenuOpen(false)} />
          </nav>
          <div className="mt-auto border-t border-ink/15 px-4 pt-4 text-sm">
            <p className="truncate text-ink" title={user?.email}>
              {user?.email}
            </p>
            <button
              type="button"
              onClick={() => signOut().then(() => router.push("/"))}
              className="mt-2 min-h-11 underline-offset-4 hover:text-ink hover:underline"
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <main id="main" className="px-4 py-8 sm:px-8 lg:px-12 lg:py-12">
        {children}
      </main>
    </div>
  );
}
