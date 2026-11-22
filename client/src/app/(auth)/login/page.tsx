"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, Field } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useSession();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(String(form.get("email")), String(form.get("password")));
      signIn(result.access, result.user);
      router.push("/app");
    } catch (caught) {
      setError(caught);
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-headline text-ink">Sign in</h1>
      <form onSubmit={handleSubmit} className="mt-10 flex flex-col gap-6">
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field label="Password" name="password" type="password" autoComplete="current-password" required />
        <ErrorNote error={error} />
        <Button type="submit" busy={busy}>
          Sign in
        </Button>
      </form>
      <div className="mt-8 flex flex-col gap-2">
        <Link href="/recover" className="text-body underline-offset-4 hover:underline">
          Forgot your password? Use a recovery code
        </Link>
        <Link href="/register" className="text-body underline-offset-4 hover:underline">
          New here? Create an account
        </Link>
      </div>
    </>
  );
}
