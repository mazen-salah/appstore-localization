---
name: appstore-localization
description: >-
  Localize an iOS app's App Store listing — metadata (name, subtitle, keywords,
  description, promotional text, release notes) AND screenshots — into many
  locales at maximum quality. Translates copy with the Gemini MCP, optimizes each
  storefront's keyword field with real popularity/difficulty data from the Astro
  ASO MCP, and localizes screenshot captions by band-translating with Gemini and
  compositing onto the pristine screenshot with Python (the in-phone app UI stays
  pixel-sharp). Outputs fastlane-ready metadata/ and screenshots/ folders. Use
  when the user has an English App Store listing and wants localized versions, or
  mentions "localize the App Store", "translate my screenshots", "localized
  keywords/ASO", or "App Store metadata for other languages".
license: MIT
user-invocable: true
---

# App Store Localization

Turn one English App Store listing into a polished, multi-locale one. Two halves,
either or both:

1. **Metadata** — translate name / subtitle / keywords / description / promo /
   release notes per locale, and (critically) **rebuild the keyword field from
   real per-storefront popularity data** instead of literally translating English
   keywords.
2. **Screenshots** — translate only the marketing **caption** on each screenshot
   and composite it back onto the pristine image, so the phone mock-up's in-app UI
   stays sharp and in its original language.

Output lands in the fastlane layout (`metadata/<locale>/*.txt`,
`screenshots/<locale>/*.png`) so `fastlane deliver` can upload it.

> **Tooling used:** Gemini MCP (`mcp__gemini__gemini_chat`, `mcp__gemini__edit_image`),
> Astro ASO MCP (`mcp__astro-aso__*`), and the bundled Python scripts
> (`scripts/compose.py`, `scripts/check_metadata.py`). See **Requirements** at the
> bottom — if a server is missing, say so and fall back to the documented manual path.

---

## Always recall first

Check memory / the repo for prior runs of THIS app: chosen target locales, the
keyword research already done per storefront, band measurements for each
screenshot frame, and which locales are actually *live* on App Store Connect (a
locale can't be created if the app name collides in that storefront — note it and
skip rather than fail the whole `deliver`). Resume; don't redo.

---

## Part A — Metadata localization

### A1. Decide the target locales
Use the storefronts the user wants / that are live on App Store Connect. App Store
locale codes (e.g. `en-US`, `de-DE`, `fr-FR`, `es-MX`, `it`, `ja`, `ko`, `pt-BR`,
`ru`, `tr`, `zh-Hans`, `ar-SA`, `id`). Confirm the list before doing 12× the work.

### A2. Translate the prose fields (Gemini MCP)
For `description`, `promotional_text`, `release_notes`, `subtitle` and the app
`name`, translate with `mcp__gemini__gemini_chat`. Give the source text and the
target locale, and instruct:
- Keep the meaning and marketing tone; do **not** add guarantees or claims the
  English copy doesn't make.
- Respect Apple limits (the validator enforces them): name ≤30, subtitle ≤30,
  promo ≤170, description ≤4000, release notes ≤4000.
- Localize numerals/currency phrasing naturally; keep product names/trademarks.
- Right-to-left locales (ar) read naturally RTL.

Write each result to `ios/fastlane/metadata/<locale>/<field>.txt`.

### A3. Discover keyword candidates (Astro ASO MCP)
**Do not just translate the English keywords** — search volume differs per
storefront. For each locale, gather candidates in that store's language:
`mcp__astro-aso__get_keyword_suggestions` for AI suggestions, plus
`mcp__astro-aso__extract_competitors_keywords` / `mcp__astro-aso__search_app_store`
to mine what competitors rank for.

### A4. Validate the keyword set with real Astro data (don't skip)
Batch the candidate keywords through `mcp__astro-aso__add_keywords(keywords=[...],
store=<cc>, appId=<id>)` — Astro returns each term's real **popularity**,
**difficulty** and your **ranking**. Use `mcp__astro-aso__search_rankings(...,
includeStatistics=true)` to check trend/volatility on borderline terms. Then
select by **popularity vs difficulty**:
- keep high-popularity terms you can realistically rank for; drop near-zero
  popularity (wasted chars) and unattainable high-difficulty heads;
- drop any word already in the localized `name`/`subtitle` (App Store indexes
  name + subtitle + keywords as one word-bag — repeating wastes the 100 chars).

Pack the survivors into a **comma-separated, no-spaces** string ≤100 chars
(`vintage,collectible,appraisal`, not `vintage, collectible, appraisal`) and write
`keywords.txt`. Full tool sequence: `references/keyword-research.md`.

### A5. Lint against Apple limits
```
python scripts/check_metadata.py ios/fastlane/metadata
```
Fix every `OVER` (hard limit) and review the keyword warnings (wasted spaces,
duplicates, redundant-with-name). Re-run until clean.

---

## Part B — Screenshot caption localization

The phone screenshots are device mock-ups with a marketing **caption** (headline +
subtitle) above/below. Translate only the caption; keep the in-phone UI pristine.

### B1. Gather pristine sources
The finished English screenshots at full store resolution (e.g. 6.9" iPhone =
1290×2796). These are the composite bases — never a previously-localized/degraded
copy. Confirm the path with the user. (Need to *create* screenshots first? That's
a different job — see **Related skills**.)

### B2. Measure each frame's caption band (once)
```
python scripts/compose.py detect screenshot.png
```
gives a starting `--y0/--y1`. Then crop and eyeball it:
```
python scripts/compose.py crop screenshot.png --y0 0 --y1 700 -o /tmp/band.png
```
View `/tmp/band.png` (downscale to ≤460px wide if your image viewer rejects large
files). Adjust so the band tightly contains the whole caption and its inner edge
falls in clean background — exclude arrows / curved-shape boundaries where you can.
Top-caption frame → `--y0 0`; bottom-caption frame → `--y1 <image height>`.

### B3. Translate each band (Gemini MCP)
For every (locale, frame), call `mcp__gemini__edit_image`:
- `model`: `gemini-3-pro-image-preview`
- `images`: the band crop (`filePath`)
- `outputPath`: `/tmp/band_<locale>_<frame>.png`
- `prompt`: give the **exact** target text per line plus a strict
  preservation instruction (see `references/prompt-templates.md`). Provide the
  target strings yourself (don't let the model free-translate) so you control
  wording, line count and fit. Keep translations short — long languages (German)
  must still fit one width. State the per-frame text colours and which word has the
  highlight blob.

**Inspect every returned band.** Models occasionally misspell — re-issue that one
spelling it letter-by-letter. For RTL/sparse layouts the model may *append* the
translation and leave the source text in place; if so, instruct it to "completely
remove all Latin letters; output only <language>; fill erased areas with the
background."

### B4. Composite back onto the pristine screenshot
```
python scripts/compose.py composite screenshot.png --y0 0 --y1 700 \
       --band /tmp/band_<locale>_<frame>.png -o ios/fastlane/screenshots/<locale>/<n>.png
```
Then **verify visually**: caption crisp and single (no source-text ghost/tail),
colours match the original, highlight blob / curve / arrow intact, no horizontal
seam line, phone UI pristine.

### B5. en-US + final check
- `en-US` screenshots = the pristine originals, but **flattened to RGB** (Apple
  rejects screenshots with an alpha channel; export PNGs are often RGBA — open and
  `.convert("RGB")`).
- Confirm every file is the exact required size and mode **RGB** (no alpha) for all
  locales before finishing.

`scripts/compose.py` internals are documented in
`references/screenshot-pipeline.md` (additive colour match, ink+colour mask,
phase-correlation align, inner-edge guard).

---

## Part C — Ship (ASK the user which way)

Everything above just produced files on disk. **Ask the user how they want to
ship** — do not assume:

> "Do you want me to upload with **fastlane**, or would you rather **paste/upload
> manually** in App Store Connect? (fastlane is automated but needs an ASC API key
> configured; manual gives you a final eyeball before anything goes live.)"

### Option 1 — Manual (the user pastes/uploads themselves)
Produce a clean hand-off so they can copy without hunting:
- Print each locale's fields (name, subtitle, keywords, description, promo, release
  notes) ready to copy, and point to `ios/fastlane/screenshots/<locale>/` for the
  images to drag into ASC.
- Remind them of the order: App Store Connect → the app → the editable version →
  per-localization fields + media → Save.
- Nothing leaves the machine; the user is the upload gate.

### Option 2 — fastlane (automated)
Requires an App Store Connect **API key** configured for fastlane (an `App Store
Connect API Key` JSON / `.p8`) — **the user provides/points to it; never commit
it.** Then, from the iOS project:
- Metadata only: `fastlane deliver --skip_screenshots --skip_binary_upload --force`
- Screenshots only: `fastlane deliver --skip_metadata --skip_binary_upload --overwrite_screenshots --force`
- Or a project lane that wraps `deliver` with the API key.

**Scope to live locales.** If some target locales aren't created on App Store
Connect yet (e.g. the app name collides in that storefront), a `deliver` run that
sees their `metadata/<locale>/` folders will fail trying to create them. Either
give those locales a unique localized name first, or run `deliver` against a
metadata path containing only the live locales. `skip_metadata` /
`skip_screenshots` keep the two halves independent.

Default to **not** submitting for review or changing the app version as part of a
metadata/screenshot push (`--submit_for_review` is a separate, explicit decision).

---

## Done criteria
All target locales have Astro-validated metadata and correctly-sized RGB
screenshots in the fastlane folders; captions are crisp and correctly spelled; the
in-phone UI is unchanged. The user has chosen a ship path (manual or fastlane) and
it's done or handed off. Save the chosen translations + band measurements to memory
so re-runs are cheap.

---

## Requirements

**Required**
- **Python 3.9+** with **numpy** and **Pillow** — `pip install -r requirements.txt`.
  (For screenshots; metadata-only runs don't need numpy.)
- **Gemini MCP server** — text translation (`gemini_chat`) and in-image caption
  translation (`edit_image`, model `gemini-3-pro-image-preview`).
  https://github.com/search?q=gemini+mcp (any Gemini MCP exposing `gemini_chat` +
  `edit_image` works).

**Recommended**
- **Astro ASO MCP server** — used to **discover and validate** keywords against
  real per-storefront popularity/difficulty data, so keyword fields are
  *optimized*, not just translated. Without it you can still translate keywords,
  but you lose the data-driven ranking edge. https://tryastro.app?aff=pZjqo8

**Optional (only to ship)**
- **fastlane** — to upload the result with `fastlane deliver`. Not needed to
  produce the files, and not needed at all if the user prefers to paste/upload
  manually in App Store Connect (the skill asks which). Uploading via fastlane
  needs an App Store Connect API key that the user supplies — never committed.
  https://fastlane.tools

**No credentials live in this repo.** It performs local image maths and writes
text files; all API access is via your separately-configured MCP servers /
fastlane. Never commit App Store Connect API keys (`AuthKey_*.p8`,
`appstore_api_key.json`), service accounts, or analytics tokens — the `.gitignore`
blocks the common ones.

## Related skills you may also want
- A screenshot **generation** skill (to create the English base screenshots and
  captions before localizing them) — e.g. an "App Store screenshots" / ASO
  screenshot designer skill.
- An **App Store review pre-flight** skill (guideline 3.1.2 paywall, 5.1.1
  privacy, metadata 2.3) to check the listing before submitting.
- A background-removal step (`rembg`) if your source art needs transparent assets.
