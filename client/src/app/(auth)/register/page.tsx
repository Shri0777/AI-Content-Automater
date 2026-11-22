"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RecoveryCodes } from "@/components/RecoveryCodes";
import { Button, ErrorNote, Field, fieldErrors } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function RegisterPage() {
  const router = useRouter();
  const { signIn } = useSession();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setBusy(true);
    setError(null);
    try {
      const created = await api.register(email, password, String(form.get("invite_code")));
      const result = await api.login(email, password);
      signIn(result.access, result.user);
      setCodes(created.recovery_codes);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  if (codes) {
    return (
      <>
        <h1 className="text-headline text-ink">Save your recovery codes</h1>
        <div className="mt-8">
          <RecoveryCodes codes={codes} doneLabel="Continue to the app" onDone={() => router.push("/app")} />
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="text-headline text-ink">Create your account</h1>
      <p className="mt-4 text-lg">Sign-up is by invitation while the service is free.</p>
      <form onSubmit={handleSubmit} className="mt-10 flex flex-col gap-6">
        <Field label="Email" name="email" type="email" autoComplete="email" required errors={fieldErrors(error, "email")} />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          hint="At least 8 characters, not a common password."
          errors={fieldErrors(error, "password")}
        />
        <Field label="Invite code" name="invite_code" autoComplete="off" required errors={fieldErrors(error, "invite_code")} />
        <ErrorNote error={error} />
        <Button type="submit" busy={busy}>
          Create account
        </Button>
      </form>
      <Link href="/login" className="mt-8 inline-block underline-offset-4 hover:underline">
        Already have an account? Sign in
      </Link>
    </>
  );
}
