"use client";

/*
 * A post's poster. The image needs the login token, so a plain <img src>
 * cannot load it: it is fetched with the token and shown from memory.
 */

import { useEffect, useState } from "react";

import { fetchImageUrl } from "@/lib/api";

export function PosterImage({ postId, alt, version }: { postId: string; alt: string; version?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    fetchImageUrl(`/posts/${postId}/poster/`)
      .then((made) => {
        objectUrl = made;
        setUrl(made);
      })
      .catch(() => setFailed(true));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [postId, version]);

  if (failed) {
    return (
      <div className="flex aspect-square items-center justify-center bg-mist p-6 text-center">
        The poster is not ready, or was deleted after the retention period.
      </div>
    );
  }
  if (!url) return <div className="aspect-square animate-pulse bg-mist" aria-label="Loading poster" />;
  // A blob: URL cannot be optimised by next/image, so a plain img is right here.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={alt} className="aspect-square w-full rounded-lg object-cover" />;
}
