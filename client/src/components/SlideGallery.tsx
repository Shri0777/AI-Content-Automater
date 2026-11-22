"use client";

/*
 * A post's slides, one at a time, like a carousel on Instagram or a document
 * on LinkedIn. Slide images need the login token, so each one is fetched with
 * it when first shown and kept in memory. Arrow keys move between slides when
 * the gallery has focus; the buttons and dots work with mouse, touch and keys.
 */

import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { fetchImageUrl } from "@/lib/api";

type Props = {
  /** Slide addresses as the API gives them, e.g. "/api/v1/posts/<id>/slides/1/". */
  slideUrls: string[];
  /** The post's headline, used to describe each slide. */
  headline: string;
};

function apiPath(url: string): string {
  return url.replace(/^\/api\/v1/, "");
}

/**
 * Give it a key that changes with each new version (the slide addresses stay
 * the same), so it starts again and fetches the new slides.
 */
export function SlideGallery({ slideUrls, headline }: Props) {
  const [index, setIndex] = useState(0);
  const [images, setImages] = useState<Record<string, string>>({});
  const [failed, setFailed] = useState(false);
  const made = useRef<string[]>([]);
  const count = slideUrls.length;
  const current = slideUrls[Math.min(index, count - 1)];

  useEffect(() => {
    if (!current || images[current]) return;
    let cancelled = false;
    fetchImageUrl(apiPath(current))
      .then((objectUrl) => {
        made.current.push(objectUrl);
        if (!cancelled) setImages((known) => ({ ...known, [current]: objectUrl }));
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [current, images]);

  useEffect(() => {
    const objectUrls = made.current;
    return () => objectUrls.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
  }, []);

  function go(next: number) {
    setIndex(Math.max(0, Math.min(count - 1, next)));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "ArrowRight") go(index + 1);
    else if (event.key === "ArrowLeft") go(index - 1);
    else if (event.key === "Home") go(0);
    else if (event.key === "End") go(count - 1);
    else return;
    event.preventDefault();
  }

  if (count === 0) return null;
  const position = `Slide ${index + 1} of ${count}`;
  const description = index === 0 ? `Cover: ${headline}` : `${position}: ${headline}`;

  return (
    <section aria-roledescription="carousel" aria-label="Slides">
      <div
        tabIndex={0}
        onKeyDown={onKeyDown}
        className="relative outline-none focus-visible:ring-2 focus-visible:ring-signal"
        aria-describedby="slide-help"
      >
        {failed ? (
          <div className="flex aspect-[4/5] items-center justify-center bg-mist p-6 text-center">
            The slides are not ready, or were deleted after the retention period.
          </div>
        ) : images[current] ? (
          // A blob: URL cannot be optimised by next/image, so a plain img is right here.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={images[current]} alt={description} className="aspect-[4/5] w-full rounded-lg object-cover" />
        ) : (
          <div className="aspect-[4/5] animate-pulse rounded-lg bg-mist" aria-label="Loading slide" />
        )}
      </div>
      <p id="slide-help" className="sr-only">
        Use the left and right arrow keys to move between slides.
      </p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => go(index - 1)}
          disabled={index === 0}
          className="min-h-11 min-w-11 border border-ink/40 px-3 text-ink disabled:opacity-40"
          aria-label="Previous slide"
        >
          ←
        </button>
        <ol className="flex flex-wrap justify-center gap-1" aria-label="Choose a slide">
          {slideUrls.map((url, dot) => (
            <li key={url}>
              <button
                type="button"
                onClick={() => go(dot)}
                aria-label={`Slide ${dot + 1}`}
                aria-current={dot === index ? "true" : undefined}
                className="flex min-h-11 min-w-6 items-center justify-center"
              >
                <span className={`block h-2 w-2 rounded-full ${dot === index ? "bg-ink" : "bg-ink/30"}`} />
              </button>
            </li>
          ))}
        </ol>
        <button
          type="button"
          onClick={() => go(index + 1)}
          disabled={index === count - 1}
          className="min-h-11 min-w-11 border border-ink/40 px-3 text-ink disabled:opacity-40"
          aria-label="Next slide"
        >
          →
        </button>
      </div>
      <p className="mt-1 text-center text-sm" aria-live="polite">
        {position}
      </p>
    </section>
  );
}
