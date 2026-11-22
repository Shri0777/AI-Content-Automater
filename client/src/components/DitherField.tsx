"use client";

/*
 * The signature element: a field of pixels in blue and white that drifts like
 * a slow wave. It nods to the dithered background of the reference theme, but
 * it is generated live here, not a video.
 *
 * Fast by design: each frame writes one pixel per dot into a small hidden
 * canvas, then copies it onto the visible canvas scaled up with sharp edges
 * (image smoothing off). Two slower ways were measured in Firefox and dropped:
 * drawing every dot as its own square, and letting CSS
 * (image-rendering: pixelated) scale a canvas that changes every frame. Both
 * ran at about 1 frame per second.
 *
 * - With "reduce motion" on, it draws one still frame and stops.
 * - It pauses while off screen and is capped at 30 frames per second.
 */

import { useEffect, useRef } from "react";

const CELL = 6;
const FRAME_MS = 1000 / 30;
// An ordered 4x4 Bayer matrix: the classic way to dither a gradient.
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
// Colours as 0xAABBGGRR, the byte order of canvas pixel data.
const INK = 0xffaa2518;
const LIGHT = 0xffe08b7c;
const WHITE = 0xffffffff;

function brightness(x: number, y: number, t: number): number {
  const wave = Math.sin(x * 0.27 + t * 0.6) + Math.sin(y * 0.36 - t * 0.4);
  const ridge = Math.sin((x + y) * 0.12 + t * 0.25);
  return (wave * 0.35 + ridge * 0.4 + 0.5) * 0.9;
}

function paintDots(image: ImageData, t: number) {
  const pixels = new Uint32Array(image.data.buffer);
  const { width, height } = image;
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const threshold = BAYER[(row % 4) * 4 + (col % 4)] / 16;
      const value = brightness(col, row, t) - threshold;
      pixels[row * width + col] = value > 0.6 ? WHITE : value > 0.35 ? LIGHT : INK;
    }
  }
}

export function DitherField({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    const dots = document.createElement("canvas");
    const dotContext = dots.getContext("2d");
    if (!canvas || !context || !dotContext) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let image = dotContext.createImageData(1, 1);
    let frame = 0;
    let visible = true;
    let last = 0;
    const start = performance.now();

    function draw(t: number) {
      if (!context || !dotContext) return;
      paintDots(image, t);
      dotContext.putImageData(image, 0, 0);
      context.imageSmoothingEnabled = false;
      context.drawImage(dots, 0, 0, dots.width * CELL, dots.height * CELL);
    }

    function resize() {
      if (!canvas || !dotContext) return;
      canvas.width = Math.max(1, canvas.clientWidth);
      canvas.height = Math.max(1, canvas.clientHeight);
      dots.width = Math.ceil(canvas.width / CELL);
      dots.height = Math.ceil(canvas.height / CELL);
      image = dotContext.createImageData(dots.width, dots.height);
      draw((performance.now() - start) / 1000);
    }

    function tick(now: number) {
      if (!visible) return;
      if (now - last >= FRAME_MS) {
        draw((now - start) / 1000);
        last = now;
      }
      frame = requestAnimationFrame(tick);
    }

    resize();
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      cancelAnimationFrame(frame);
      if (visible && !reduceMotion) frame = requestAnimationFrame(tick);
    });
    observer.observe(canvas);
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`block h-full w-full ${className}`}
    />
  );
}
