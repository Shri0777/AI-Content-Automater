"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button, Empty, ErrorNote, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Notification } from "@/lib/types";

const RELATED_PATHS: Record<string, string> = {
  post: "/app/posts/",
  contentplan: "/app/plans/",
};

const RELATED_PAGES: Record<string, string> = {
  socialaccount: "/app/accounts",
  providercredential: "/app/keys",
};

function NotificationRow({ notification, onRead }: { notification: Notification; onRead: () => void }) {
  const unread = notification.read_at === null;
  const base = RELATED_PATHS[notification.related_type];
  const href = base && notification.related_id ? `${base}${notification.related_id}` : RELATED_PAGES[notification.related_type] ?? null;
  return (
    <li className={`flex flex-col gap-2 border-b border-ink/10 py-4 sm:flex-row sm:items-start sm:justify-between ${unread ? "" : "opacity-70"}`}>
      <div className="flex gap-3">
        <span aria-hidden="true" className={`mt-2 size-2 shrink-0 ${unread ? "bg-signal" : "bg-transparent"}`} />
        <div>
          <p className="text-ink">
            {notification.title}
            {unread && <span className="sr-only"> (unread)</span>}
          </p>
          <p>{notification.message}</p>
          <p className="mt-1 text-sm text-body/80">{timeAgo(notification.created_at)}</p>
        </div>
      </div>
      <div className="flex gap-4 pl-5 sm:pl-0">
        {href && <Link href={href} onClick={unread ? onRead : undefined} className="min-h-11 py-2 text-signal underline-offset-4 hover:underline">Open</Link>}
        {unread && <button type="button" onClick={onRead} className="min-h-11 py-2 underline-offset-4 hover:underline">Mark read</button>}
      </div>
    </li>
  );
}

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(() => api.notifications().then((page) => setItems(page.results)).catch(setError), []);
  useEffect(() => { load(); }, [load]);

  async function markRead(id: string) {
    await api.markRead(id).catch(setError);
    load();
  }

  const unreadCount = items?.filter((item) => item.read_at === null).length ?? 0;

  return (
    <>
      <PageHeader
        title="Notifications"
        intro="What happened while you were away."
        action={unreadCount > 0 ? <Button variant="secondary" onClick={() => api.markAllRead().then(load).catch(setError)}>Mark all read</Button> : undefined}
      />
      <div className="mt-6">
        <ErrorNote error={error} />
        {!items && !error && <Loading />}
        {items?.length === 0 && <Empty title="No notifications" />}
        {items && items.length > 0 && <ul>{items.map((item) => <NotificationRow key={item.id} notification={item} onRead={() => markRead(item.id)} />)}</ul>}
      </div>
    </>
  );
}
