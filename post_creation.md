# How posts are made: worth reading, worth saving

This file decides what every post looks like. The part between the
`rules:start` and `rules:end` markers is read by the app and sent to the AI
each time it writes or fixes a post (`studio/post_rules.py`), so **editing
those rules changes the posts** (after restarting the app). Everything else
here explains why the rules are what they are.

## The problem this fixes

The first posters were a decorative AI picture with one line on top, such as
"Quick tip: List folder sizes with du and sort". Nobody saves that: it has no
information you could not guess from the line itself, the picture says
nothing, and "Quick tip" is filler. A post is worth posting when someone
would **save it or send it to a friend** because it holds something useful.

## What the research says

Researched on 2026-11-17. Most public "data" on social formats comes from
marketing tools selling to creators, so it is marked by how much to trust it.

| Finding | Evidence | Trust |
|---|---|---|
| Instagram's own head named watch time, likes per reach and **sends per reach** as the top ranking signals; sends matter most for reaching people who do not follow you. | Adam Mosseri, January 2025, as reported by [Buffer](https://buffer.com/resources/instagram-algorithms/) and [Sprout Social](https://sproutsocial.com/insights/instagram-algorithm/) | Good (first-hand statement, second-hand report) |
| "Sends outweigh likes by 3–5x" | Repeated by many blogs, no primary source; Instagram publishes no multiplier | Ignore |
| Educational carousels are saved and sent more than single images | Third-party studies (for example Metricool, quoted by [Storrito](https://storrito.com/resources/how-instagram-carousels-beat-reels-for-engagement-in-2026-and-when-to-use-each/)); numbers vary from 1.4x to 9x between sources | Direction is consistent; numbers are not |
| On LinkedIn, document (carousel) posts have the highest average engagement rate of any format, 7.00% | [Socialinsider 2026 LinkedIn benchmarks](https://www.socialinsider.io/blog/linkedin-study/), 1.3 million business posts | Fair (large sample, engagement rate only, not reach) |
| Carousels win on engagement but not on reach | [Vulse 2026 benchmarks](https://vulse.co/blog/linkedin-content-benchmarks-2026-which-post-format-drives-most-engagement) | Fair |
| The first image decides everything: a big, short headline (3–7 words) with a clear promise or a challenged belief, high contrast, one focal point | YouTube: "How to Make Instagram Carousels That ACTUALLY Get Views & Reach" ([video](https://www.youtube.com/watch?v=WWyvLYdVaF0)), transcript read in full | Practitioner advice |
| Every slide or block must make sense on its own ("design each slide like a mini poster"); one idea per block | Same video; also [dev.to carousel guide](https://dev.to/fermainpariz/how-to-create-instagram-carousel-posts-that-get-saved-and-shared-2026-guide-1jjm) | Practitioner advice, consistent across sources |
| Tech posts that do well are concrete: numbered steps, real examples, "what to do" | [dev.to carousel guide](https://dev.to/fermainpariz/how-to-create-instagram-carousel-posts-that-get-saved-and-shared-2026-guide-1jjm), [Kontentino: the save is the new like](https://www.kontentino.com/blog/the-save-is-the-new-like-are-you-creating-for-it/) | Practitioner advice |

Not checked: Instagram itself could not be browsed (it needs a logged-in
browser), so no individual Instagram posts were studied. Nothing above is
specific to tech accounts with numbers attached; no source broke results out
that way.

## Update, 2026-11-22: slides, fewer words, no AI art by default

A second research pass on 2026-11-22 changed the form of a post, not its
substance:

| Finding | Evidence | Trust |
|---|---|---|
| Multi-slide posts beat single images: LinkedIn document posts 21.77% median engagement vs 6.52% for images; Instagram carousels 6.9% vs 4.4% | [Buffer, 45M+ posts, Mar 2026](https://buffer.com/resources/data-best-content-format-social-media/); [Socialinsider, 2.45M LinkedIn posts](https://www.socialinsider.io/blog/linkedin-study/) | Fair (vendor data, engagement not reach) |
| On X a copy-link share weighs 20, a reply 5, a like 0.5; "not interested" -43.2, report -234 | X's published ranking weights, as reported by [PPC Land, Sep 2026](https://ppc.land/x-gives-copy-link-shares-a-feed-weight-of-20-against-0-5-for-likes/) | Good (code, second-hand) |
| Content people suspect is AI-made is rated 48% less trustworthy and 57% less authentic | [Raptive, 3,000 US adults, Aug 2025](https://raptive.com/blog/the-ai-stink-is-real-and-its-costing-brands/) | Fair (commissioned study) |
| Meta labels images it detects as AI-generated ("AI info") | [Meta Transparency Center](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content) | Good (first-hand) |

## What a post is now

**A post is a set of slides plus a caption.** One idea per slide, in words
that can be read in about two seconds:

1. **Cover**: the headline, big, in the plan's brand colour. AI artwork only
   when the plan asks for it (off by default: no image model is called).
2. **Figure** (when the article has a number that matters): the number,
   big, with what it means, and a before-and-after bar pair when the
   article gives both numbers.
3. **Key points**: 3 to 5 slides, one point each, 15 to 25 words.
4. **Quote** (when the article has a strong one): copied word for word.
5. **Closing**: the takeaway and the source.

Slides are 1080x1350 (portrait). LinkedIn gets them as one document post
(a PDF people swipe through). Platforms that show one picture (X, Facebook,
Buffer) get a square image: the figure slide when there is one, else the
cover.

Plain code checks what it can, for free: a quote that is not word for word
in the article is dropped, a figure whose number is not in the article is
dropped, and a slide with too many words sends the post back for a rewrite
(studio/post_content.py). The AI review also scores **shareability**: would
a busy professional send this to a colleague?

**The caption** goes deeper: what happened, why it matters and to whom,
what to do about it, then one specific question that invites replies (sends
and replies are what platforms reward), then the source link.

<!-- rules:start -->
Write for a curious professional who will only save or share a post that
teaches them something. Every post must pass this test: "Would someone send
this to a colleague or save it for later?"

The post is a set of slides people swipe through, plus a caption. A slide
is read in about two seconds, so each slide holds one idea in few words.

Headline (the cover slide):
- 3 to 8 words, at most 60 characters. The real news or a specific promise,
  in plain words. Examples: "OpenAI cut GPT pricing by 50%", "3 ways the EU
  AI Act changes hiring".
- Never start with "Quick tip", "Breaking", "Did you know", "Here's" or an
  emoji. No clickbait, no question you cannot answer.

Key points (one slide each):
- 3 to 5 points, each one complete sentence of 15 to 25 words.
- Each point makes sense on its own and is concrete: a figure, a name, a
  date, a command, a deadline, a before-and-after, or a step someone can take.
- Cover, in this order where the article allows: what happened, the key
  detail, why it matters and to whom, what the reader can do.
- Never pad: no "This is a big deal", "Stay tuned", "Exciting times".
- Every point must be stated in or directly follow from the article.

Figure (its own slide; leave it out when there is none):
- The one number that matters most, written exactly as the article gives it,
  with a short label saying what it means.
- Add a before-and-after comparison only if the article states both numbers.
- Never work out, round or convert a number yourself.

Quote (its own slide; leave it out when there is none):
- Only a sentence copied word for word from the article, with the speaker as
  the article names them. A quote that is not in the article is removed.

Takeaway (the closing slide):
- One sentence of at most 20 words: why it matters, or what to do next.

Caption:
- Open with one line that says why this matters to the reader.
- Then short paragraphs: what happened (with the specifics), why it matters,
  who is affected, and one practical takeaway or next step.
- Keep the article's numbers, names and dates exact. Quote nothing you
  cannot see in the article. Say "the article does not say" rather than
  guess.
- Plain, friendly language. Explain any jargon in a few words.
- Then one specific question that invites readers to share their own
  experience or view, for example "Would a 50% price cut change which model
  your team uses?". Never a generic "What do you think?", and never ask for
  likes, shares or follows.
- At most 3 relevant hashtags, after the question, before the source line.
- End with the line "Source: <source name>, <article link>".

If the article is thin (no real facts beyond the title), write fewer points
rather than inventing any, and leave out the figure and the quote.
<!-- rules:end -->

## Topics

A plan follows one or more topics. Each built-in topic reads a handful of
news feeds that were checked to answer (the list, with the feeds, is in
`newsroom/presets.py`). You can also add **your own topic**: a name, the
words to search for in the news, and your own instructions for the AI, which
are added to the rules above for that topic only.

## Checking a post against this file

The AI review (`studio/prompts.py`, REVIEW_PROMPT) scores every post for
grounding, relevance, clarity, tone, safety and shareability, and the
points, figure, quote and takeaway are checked like the caption: anything
not backed by the article is a blocker. Plain code adds a "major" issue for
any slide with too many words (`studio/post_content.py`), which sends the
post back for a rewrite.
