import Link from "next/link";

import { DitherField } from "@/components/DitherField";

/** Sign-in pages: the form on paper, the dither field beside it on wide screens. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="flex flex-col px-4 py-6 sm:px-10">
        <Link href="/" className="text-lg tracking-tight text-ink">
          AI Content Automator
        </Link>
        <main className="flex flex-1 items-center py-12">
          <div className="w-full max-w-md">{children}</div>
        </main>
      </div>
      <div className="relative hidden bg-ink lg:block">
        <DitherField />
      </div>
    </div>
  );
}
