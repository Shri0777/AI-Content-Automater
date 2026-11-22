import Link from "next/link";

import { DitherField } from "@/components/DitherField";
import { SiteHeader } from "@/components/SiteHeader";

const STEPS = [
  {
    title: "Finds the news",
    text: "Reads the feeds for your topics, drops stale and repeated stories, and lets your AI pick the most credible one.",
  },
  {
    title: "Writes the post",
    text: "Your text model writes the caption in your words and credits the source.",
  },
  {
    title: "Makes the poster",
    text: "Your image model paints the artwork; the headline is drawn on it, so it is always spelled right.",
  },
  {
    title: "Checks it",
    text: "An AI review scores it, fixed rules decide the verdict, and weak posts are corrected up to twice.",
  },
  {
    title: "Posts on time",
    text: "At the times you set, after your approval, or on its own when the review is spotless.",
  },
];

const PROMISES = [
  {
    title: "Your own AI keys",
    text: "Claude, OpenAI, OpenRouter, Groq, Ollama, fal or NVIDIA. Keys are encrypted and never shown again.",
  },
  {
    title: "Never posts twice",
    text: "If a platform takes a post but never answers, it asks you instead of risking a duplicate.",
  },
  {
    title: "Nothing stale, no filler",
    text: "If no article is good enough, nothing is posted. After downtime, late posts are skipped, not sent.",
  },
];

export default function LandingPage() {
  return (
    <main>
      <section className="relative isolate overflow-hidden bg-ink text-paper">
        <div className="absolute inset-0 -z-10 opacity-90 lg:left-1/3">
          <DitherField />
        </div>
        <div className="absolute inset-0 -z-10 bg-gradient-to-r from-ink via-ink/85 to-transparent" />
        <SiteHeader onDark />
        <div className="px-4 pt-20 pb-28 sm:px-8 sm:pt-32 sm:pb-40">
          <h1 className="max-w-4xl text-[clamp(3rem,9vw,6.5rem)] leading-[0.9] tracking-[-0.055em]">
            <span className="rise block" style={{ "--delay": "80ms" } as React.CSSProperties}>
              News in.
            </span>
            <span className="rise block" style={{ "--delay": "220ms" } as React.CSSProperties}>
              Posters out.
            </span>
            <span className="rise block" style={{ "--delay": "360ms" } as React.CSSProperties}>
              On your schedule.
            </span>
          </h1>
          <p
            className="rise mt-10 max-w-xl text-lg text-paper/85"
            style={{ "--delay": "520ms" } as React.CSSProperties}
          >
            It finds the news on topics you choose, makes a poster with your own AI models, checks
            it, and posts it to your accounts when you say so.
          </p>
          <div className="rise mt-10 flex flex-wrap gap-3" style={{ "--delay": "640ms" } as React.CSSProperties}>
            <Link href="/register" className="bg-signal px-6 py-3.5 text-paper hover:bg-paper hover:text-ink">
              Create an account
            </Link>
            <Link href="/login" className="border border-paper/50 px-6 py-3.5 hover:border-paper">
              Sign in
            </Link>
          </div>
        </div>
      </section>

      <section aria-labelledby="how" className="px-4 py-24 sm:px-8">
        <div className="border-t border-ink/30 pt-4">
          <h2 id="how" className="text-lg">
            How a post is made
          </h2>
        </div>
        <ol className="mt-12 grid gap-px bg-ink/15 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex flex-col bg-paper p-6 lg:min-h-80">
              <span className="text-title text-ink/40 tabular-nums">{String(index + 1).padStart(2, "0")}</span>
              <h3 className="mt-auto pt-16 text-title text-ink">{step.title}</h3>
              <p className="mt-3">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="promises" className="bg-mist px-4 py-24 sm:px-8">
        <h2 id="promises" className="max-w-3xl text-headline text-ink">
          Built to be trusted with your accounts.
        </h2>
        <div className="mt-14 grid gap-10 md:grid-cols-3 md:gap-0">
          {PROMISES.map((promise) => (
            <div key={promise.title} className="md:border-l md:border-ink/25 md:px-6 md:first:border-l-0 md:first:pl-0">
              <h3 className="text-title text-ink">{promise.title}</h3>
              <p className="mt-3 max-w-sm">{promise.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="px-4 py-24 sm:px-8">
        <h2 className="max-w-3xl text-headline text-ink">Try it with no keys at all.</h2>
        <p className="mt-6 max-w-xl text-lg">
          Demo mode uses built-in stand-ins for the AI, the news and the social network, so you can
          follow a post from start to finish before adding anything of your own.
        </p>
        <Link href="/register" className="mt-8 inline-flex bg-signal px-6 py-3.5 text-paper hover:bg-ink">
          Create an account
        </Link>
      </section>

      <footer className="bg-ink px-4 py-10 text-sm text-paper/80 sm:px-8">
        AI Content Automator. Demo content is canned, not real AI output.
      </footer>
    </main>
  );
}
