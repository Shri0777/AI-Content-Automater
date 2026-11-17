# Frontend theme: analysis of the "OtherSync" template

The owner chose Wix template **wh-1305, "SAAS company (Innovative)"** (the
demo brand is "OtherSync") as the look for our frontend. This document
records what the template does, measured from the live demo on 2026-11-17,
and how its design language maps onto our app. The frontend is built
later; this is the reference for it.

Source: https://www.wix.com/website-template/view/html/wh-1305 (the site
itself renders from https://www.wix.com/demone2/other-sync).

> **Licensing.** Wix templates are licensed for building sites on Wix. We
> take the *design language* (palette, type scale, layout patterns, tone),
> not its files: no copying of its images, video, client logos, icons,
> illustrations or text. Its typeface (Helvetica, served by Wix under its own
> licence) is replaced with a free font below. All our imagery is our own:
> real screenshots of our app and posters our pipeline makes.

## 1. Overall character

Editorial, minimal and confident: one blue hue in three strengths on white
and pale grey, very large tightly-tracked headlines in a single regular
weight, thin hairline rules, square corners, generous white space. Visual
interest comes from product screenshots in device frames and a pixelated
(dithered) blue background, not from decoration.

## 2. Design tokens (measured)

### Colours

| Token | Value | Used for |
|---|---|---|
| `--ink` | `#1825AA` (24, 37, 170) | Headlines, nav links, footer and hero background |
| `--accent` | `#0047FF` (0, 71, 255) | Primary buttons ("Request a Demo"), "Apply Now" links |
| `--body` | `#3856C7` (56, 86, 199) | Body text, eyebrow labels, form labels |
| `--mist` | `#E0E1E8` (224, 225, 232) | Alternate section background; text on `--ink` |
| `--paper` | `#FFFFFF` | Page background, cards, nav pills |

Text contrast (WCAG, computed): `--ink` on white 11.2:1, `--body` on white
6.3:1, white on `--accent` 6.3:1, `--ink` on `--mist` 8.6:1. `--body` on
`--mist` is 4.9:1: AA for normal text, but with little margin, so use
`--ink` there for small text.

### Typography

One family, **one weight (regular 400)**, contrast made by size alone.

| Role | Size / line height | Letter spacing | Colour |
|---|---|---|---|
| Display (hero, closing CTA) | 72 / 64.8 px (0.9) | -3.6 px (-0.05em) | `--ink`, white on blue |
| Section headline | 64 / 60.8 px (0.95) | -3.2 px (-0.05em) | `--ink` |
| Large statement | 48 px | tight | `--ink` / white |
| Card title | 24 / 26.4 px (1.1) | -1.2 px (-0.05em) | `--ink` |
| Lead paragraph | 18–24 px | normal | `--body` |
| Eyebrow label ("A Symphony of Synergy") | 20 / 22 px | normal | `--body` |
| Body, nav, buttons | 16 / 20 px | normal (nav -0.8 px) | `--body` / `--ink` |
| Small (form labels, "Apply Now") | 14 px | normal | `--body` / `--accent` |

The template uses Helvetica (`helvetica-w01-roman`). **Our choice: Inter
Tight** (free, SIL Open Font License, made for tight display tracking),
falling back to `"Helvetica Neue", Helvetica, Arial, sans-serif`.

### Shape and lines

- **Square corners** on buttons, nav pills and feature cards (radius 0).
  Product screenshots and photos have softly rounded corners (about 8–12 px).
- **Hairline rules** (1 px, `--ink` or `--body`) separate sections: a
  full-width rule with the eyebrow label just under it, and vertical rules
  between columns of feature cards.
- Form inputs are underline-only (no box), labels above.

### Spacing

24 px page gutter at desktop (content starts at x = 24), sections separated
by roughly 120–200 px of space, 3-column grids with about 410 px columns at
1280 px.

## 3. Components

| Component | Description |
|---|---|
| **Header** | Three white "pills" floating on the hero: logo pill (left), nav pill with 4 links (centre, current page underlined), and a solid `--accent` CTA button with a ↗ arrow (right, flush to the edge). Stays fixed on scroll. |
| **Primary button** | Solid `--accent`, white 16 px text, ↗ arrow icon on the right, square corners, about 234 × 42 px. |
| **Secondary button** | Pale (white/mist) fill, `--accent` text and ↗ arrow, thin border. |
| **Eyebrow + rule** | Full-width 1 px rule, then a 20 px `--body` label under it, then the big headline. Repeated on every section. |
| **Feature card (column)** | Line-art icon (circles/globe, 1.5 px strokes in `--body`), large empty space, then 24 px title and 16 px description. Columns divided by vertical hairlines. |
| **Numbered card** | White card, 24 px title left and "01" right on one line, a rule under them, then description. On the home page three of these are staggered diagonally. On Platform they form a 2 × 2 grid. |
| **Logo strip** | Four partner logos in one row on `--mist`, with an eyebrow above and a 64 px headline. |
| **Device showcase** | Product UI shown inside a browser frame (hero) or a phone and tablet mockup (mid-page), overlapping the dithered blue background. |
| **Team card** | Portrait (about 119 × 133 px), name 24 px, role 16 px `--body`. Three across. |
| **Job list row** | Job title 24 px on the left, "Apply Now" 14 px `--accent` on the right, rule between rows. |
| **Closing CTA** | 72 px headline centred, short paragraph, primary button, with small photos scattered around the edges. |
| **Footer** | `--ink` background with a stepped (staircase) top edge, a very large white logo wordmark, then a bottom bar: social icons, Privacy Policy, Accessibility Statement, copyright. |
| **Contact form** | Two columns: heading, intro and contact details on the left; underline inputs (first/last name, email, phone with country code, company, short answer, message) and a solid submit button on the right. |

## 4. Page layouts

**Home (about 4,960 px tall at 1280 px wide)**
1. Hero on `--ink` with the dithered background (a looping video in the
   template, with a pause control): small intro text left, display
   headline centred, browser-framed dashboard screenshot overlapping the
   bottom, secondary CTA floating on the right.
2. Eyebrow "A Symphony of Synergy" + 64 px statement + three feature
   columns with line icons.
3. `--mist` section: "Client Logos" eyebrow, 64 px headline, logo strip.
4. Eyebrow "Elevate Your Enterprise", 64 px headline left, three staggered
   numbered cards (01–03) right.
5. Full-width dithered blue band with phone and tablet product mockups.
6. Closing CTA "See OtherSync in action" with scattered photos.
7. Stepped footer.

**Platform (about 3,390 px):** display headline + lead paragraph; eyebrow
"The Pillars of Our Platform" + 48 px statement + 2 × 2 numbered cards
(01–04); "Connect Everything" band on `--ink` with integration visuals;
"Your Data, Fortified" security CTA; footer.

**About (about 2,680 px):** display headline + lead; "Our Leadership"
eyebrow + 48 px mission statement + three team cards; "Join Our Team"
eyebrow + 64 px headline + job list with "Apply Now"; footer.

**Contact (about 1,410 px):** "Let's Connect" 64 px, intro, headquarters
block (email, phone, address) on the left; the form on the right; footer.

**Motion:** looping dithered background video in the hero and mid-page
band, with a pause control (good: it respects users who need motion
stopped). Not measured: hover and scroll animations. The mobile layout
could not be captured (the browser tool stalled at phone width).

## 5. How it maps onto our app

The template is a marketing site; ours is a marketing site **and** a
working app. The same tokens and components cover both.

| Our page | Template pattern it borrows |
|---|---|
| **Landing** ("Your news, posted while you sleep") | Home: hero with a real dashboard screenshot of our app in a browser frame; three feature columns (Finds the news, Makes the poster, Posts on schedule); numbered "how it works" cards for the pipeline (01 Research, 02 Draft, 03 Poster, 04 Review, 05 Publish); closing CTA "Try the demo". The logo strip becomes "Posts to": Buffer, X, LinkedIn, Facebook (wordmarks only as each brand's rules allow). |
| **How it works** | Platform: 2 × 2 numbered cards for the safety features (Review and correct, Auto-post gate, Never posts twice, Your own keys). |
| **About / Case study** | About: the V3 → V4 rebuild story and measured results instead of team cards. |
| **Log in / Register / Recover** | Contact form style: underline inputs, solid submit. |
| **Dashboard** | White cards with numbered headers: "Waiting for approval", "Up next" (upcoming slots), "Recently published", usage meters. Eyebrow + rule section headers. |
| **Post review** | Poster on the left (rounded image), headline and caption on the right, review scores as a five-row list, versions as a numbered list (01, 02, 03), Approve as the primary button and Edit as the secondary one. |
| **Plans and schedule** | Job-list rows for plans (name left, "Pause/Edit" right); the schedule editor as weekday toggles and time chips with square corners. |
| **Accounts and keys** | Numbered cards per platform and per key kind, with status text in `--body` and a ↗ connect button. |
| **Notifications** | Job-list rows: message left, time right, unread marked with an `--accent` dot. |

Our app must also show states the template never needed: error (red is
not in the palette; add `--danger: #C8102E`, 5.9:1 on white), success
(`--ok: #0A7A3E`, 5.4:1 on white), "needs attention" amber (pick a shade
that reaches 4.5:1), and empty states. Keep
them as small text or dots, so the blue palette stays dominant.

## 6. Accessibility notes for our version

- Keep the template's pause control for any background motion, and turn
  the motion off for `prefers-reduced-motion`.
- Use `--ink`, not `--body`, for small text on `--mist`.
- Visible focus rings (2 px `--accent` outline with offset), since the
  square buttons have no other focus style.
- The ↗ arrow is decoration: the button's text alone must say what it does.
- Underline-only inputs need a clear focus state and labels that stay visible.
