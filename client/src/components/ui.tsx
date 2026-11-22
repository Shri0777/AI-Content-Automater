"use client";

/*
 * Small building blocks used on every screen: buttons, form fields, notes
 * and headers. Square corners and hairlines follow the theme; focus rings
 * come from globals.css.
 */

import Link from "next/link";

import { ApiError } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/format";
import type { PostStatus } from "@/lib/types";

const BUTTON_STYLES = {
  primary:
    "bg-signal text-paper hover:bg-ink disabled:bg-mist disabled:text-body/60",
  secondary:
    "border border-ink/30 text-ink hover:border-ink hover:bg-mist/60 disabled:opacity-50",
  quiet: "text-body underline-offset-4 hover:text-ink hover:underline disabled:opacity-50",
  danger: "border border-danger/40 text-danger hover:bg-danger hover:text-paper",
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof BUTTON_STYLES;
  busy?: boolean;
};

export function Button({ variant = "primary", busy, className = "", children, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      aria-busy={busy || undefined}
      className={`inline-flex min-h-11 items-center justify-center gap-2 px-5 text-base transition-colors duration-150 ${BUTTON_STYLES[variant]} ${className}`}
    >
      {busy ? "Working…" : children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "primary",
  children,
  className = "",
}: {
  href: string;
  variant?: keyof typeof BUTTON_STYLES;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex min-h-11 items-center justify-center px-5 text-base transition-colors duration-150 ${BUTTON_STYLES[variant]} ${className}`}
    >
      {children}
    </Link>
  );
}

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  errors?: string[];
};

/** A labelled input with an underline, a hint and the API's field errors. */
export function Field({ label, hint, errors, id, ...rest }: FieldProps) {
  const fieldId = id ?? rest.name;
  const describedBy = errors?.length ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-sm text-body">
        {label}
      </label>
      <input
        id={fieldId}
        aria-invalid={errors?.length ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
        className="border-b border-body/50 bg-transparent py-2 text-lg text-ink outline-none transition-colors placeholder:text-body/50 focus:border-signal aria-invalid:border-danger"
      />
      {hint && !errors?.length && (
        <p id={`${fieldId}-hint`} className="text-sm text-body/80">
          {hint}
        </p>
      )}
      {errors?.length ? (
        <p id={`${fieldId}-error`} className="text-sm text-danger">
          {errors.join(" ")}
        </p>
      ) : null}
    </div>
  );
}

/** Shows what went wrong and, where the API says, how to fix it. */
export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : "Something went wrong. Try again.";
  return (
    <p role="alert" className="border-l-2 border-danger py-1 pl-3 text-danger">
      {message}
    </p>
  );
}

export function fieldErrors(error: unknown, name: string): string[] | undefined {
  if (error instanceof ApiError && error.fields[name]) return error.fields[name];
  return undefined;
}

export function PageHeader({
  title,
  intro,
  action,
}: {
  title: string;
  intro?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-ink/20 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-2xl">
        <h1 className="text-headline text-ink">{title}</h1>
        {intro && <p className="mt-3 text-lg">{intro}</p>}
      </div>
      {action}
    </header>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="border border-dashed border-body/40 p-8">
      <p className="text-title text-ink">{title}</p>
      {children && <div className="mt-3 max-w-xl">{children}</div>}
    </div>
  );
}

const STATUS_TONE: Partial<Record<PostStatus, string>> = {
  awaiting_approval: "bg-signal text-paper",
  published: "bg-ok/10 text-ok",
  failed: "bg-danger/10 text-danger",
  rejected: "bg-mist text-body",
  expired: "bg-mist text-body",
  skipped: "bg-mist text-body",
};

export function StatusBadge({ status }: { status: PostStatus }) {
  const tone = STATUS_TONE[status] ?? "bg-mist text-ink";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-sm whitespace-nowrap ${tone}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p role="status" className="animate-pulse text-body/70">
      {label}…
    </p>
  );
}
