"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, ErrorNote, Field, fieldErrors } from "@/components/ui";
import { api } from "@/lib/api";

export default function RecoverPage() {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [codesLeft, setCodesLeft] = useState<number | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const result = await api.recover(
        String(form.get("email")),
        String(form.get("recovery_code")),
        String(form.get("new_password")),
      );
      setCodesLeft(result.recovery_codes_left);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  if (codesLeft !== null) {
    return (
      <>
        <h1 className="text-headline text-ink">Password changed</h1>
        <p className="mt-4 text-lg">
          You were signed out on every device. You have {codesLeft} recovery code
          {codesLeft === 1 ? "" : "s"} left; make new ones in Settings if that is getting low.
        </p>
        <Link href="/login" className="mt-8 inline-flex bg-signal px-6 py-3 text-paper hover:bg-ink">
          Sign in
        </Link>
      </>
    );
  }

  return (
    <>
      <h1 className="text-headline text-ink">Reset your password</h1>
      <p className="mt-4 text-lg">Use one of the recovery codes you saved when you signed up.</p>
      <form onSubmit={handleSubmit} className="mt-10 flex flex-col gap-6">
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field label="Recovery code" name="recovery_code" autoComplete="off" placeholder="K7QX-M2VD-9HTP" required />
        <Field
          label="New password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          errors={fieldErrors(error, "new_password")}
        />
        <ErrorNote error={error} />
        <Button type="submit" busy={busy}>
          Reset password
        </Button>
      </form>
      <Link href="/login" className="mt-8 inline-block underline-offset-4 hover:underline">
        Back to sign in
      </Link>
    </>
  );
}
