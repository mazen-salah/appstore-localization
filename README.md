# App Store Localization — a Claude Code skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-8A63D2.svg)](https://docs.claude.com/en/docs/claude-code)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

Localize an iOS app's **App Store listing** — metadata *and* screenshots — into
many locales at maximum quality, then ship it the way you prefer.

It orchestrates three things:

- **Gemini MCP** — translates the marketing copy, and translates the caption text
  *inside* each screenshot.
- **Astro ASO MCP** — discovers and **validates** keywords against real
  per-storefront popularity/difficulty data (so the keyword field is *optimized*,
  not just translated).
- **Python (Pillow + numpy)** — composites the translated caption back onto the
  pristine screenshot so the in-phone app UI stays pixel-sharp, and lints metadata
  against Apple's field limits.

Output lands in the standard fastlane layout (`metadata/<locale>/*.txt`,
`screenshots/<locale>/*.png`), ready to upload — by hand or with `fastlane
deliver`.

---

## Why this exists

**Screenshots.** Image models cap their output around a ~1500px long edge. Feed a
whole 1290×2796 store screenshot in and you get a smaller image back that has to be
upscaled — blurry text and a soft phone UI. This skill instead translates **only
the caption band** (short → the model's output is a *downscale* to the screenshot
width = crisp) and composites it back onto the untouched original. A glyph + colour
diff mask means highlight blobs, curved shapes, arrows and squiggles stay pristine
while only the letterforms change. ([deep dive](references/screenshot-pipeline.md))

**Keywords.** Search demand differs by language and country, so literally
translating your English keywords leaves ranking on the table. This skill pulls
real popularity/difficulty numbers from Astro and **validates** the candidate set
per storefront before committing it. ([deep dive](references/keyword-research.md))

---

## Requirements

| | What | Needed for |
| --- | --- | --- |
| **Required** | Python 3.9+ with `numpy` + `Pillow` (`pip install -r requirements.txt`) | screenshot compositing + metadata linting (metadata-only runs don't need numpy) |
| **Required** | **Gemini MCP** server exposing `gemini_chat` + `edit_image` (model `gemini-3-pro-image-preview`) | translating copy and in-image captions |
| **Recommended** | **[Astro ASO MCP](https://tryastro.app?aff=pZjqo8)** server | discovering + validating localized keywords |
| **Optional (to ship)** | **fastlane** | uploading via `fastlane deliver` — skip it entirely if you upload manually |

> **No credentials live in this repo.** The scripts do local image maths and write
> text files; all API access is through your separately-configured MCP servers and
> fastlane. App Store Connect API keys, service accounts and analytics tokens must
> never be committed — `.gitignore` blocks the common ones.

---

## Installation

Install as a Claude Code skill by cloning into your skills directory:

```bash
git clone https://github.com/mazen-salah/appstore-localization \
  ~/.claude/skills/appstore-localization
pip install -r ~/.claude/skills/appstore-localization/requirements.txt
```

Then make sure your **Gemini MCP** (and ideally **Astro ASO MCP**) servers are
configured in Claude Code. Invoke it with:

```
/appstore-localization
```

or just describe the task ("localize my App Store listing into German, French and
Japanese") and Claude will pick up the skill.

You can also use the scripts directly, with or without Claude Code (see below).

---

## Scripts

### `scripts/compose.py` — screenshot caption pipeline

```bash
# 1. suggest the caption band rows for a screenshot
python scripts/compose.py detect screenshot.png

# 2. crop the caption band to send to your image model for translation
python scripts/compose.py crop screenshot.png --y0 0 --y1 700 -o band.png

# 3. composite the translated band back onto the pristine screenshot
python scripts/compose.py composite screenshot.png --y0 0 --y1 700 \
       --band band_translated.png -o out/de-DE/1.png
```

Tunables on `composite`: `--thresh` (colour-diff, default 45), `--feather`
(default 2), `--guard` (inner-edge guard rows, default 28). See
[references/screenshot-pipeline.md](references/screenshot-pipeline.md).

### `scripts/check_metadata.py` — Apple field-limit linter

```bash
python scripts/check_metadata.py ios/fastlane/metadata
python scripts/check_metadata.py ios/fastlane/metadata --locale en-US
```

Flags name/subtitle/keywords/promo/description/release-notes over Apple's limits,
plus wasted spaces, duplicate keywords, and keywords already in name/subtitle.
Pure standard library, no dependencies. Exit code is non-zero if any hard limit is
exceeded (handy in CI).

---

## Repository layout

```
.
├── SKILL.md                          # the Claude Code skill (workflow + frontmatter)
├── README.md
├── LICENSE
├── requirements.txt
├── scripts/
│   ├── compose.py                    # screenshot band-translate + composite
│   └── check_metadata.py             # App Store field-limit linter
└── references/
    ├── screenshot-pipeline.md        # compose.py internals + tuning
    ├── prompt-templates.md           # ready-to-use Gemini prompts (incl. RTL/CJK)
    └── keyword-research.md           # Astro discover → validate → pack
```

---

## Shipping

The skill asks how you want to ship — it never uploads on its own:

- **Manual** — it prints each locale's fields ready to paste into App Store Connect
  and points to the screenshot folder to drag in. You're the final gate.
- **fastlane** — `fastlane deliver` (metadata and/or screenshots), scoped to the
  locales that actually exist on App Store Connect. Uploading needs an ASC API key
  *you* provide; it's never stored here.

Uploading metadata/screenshots does **not** submit for review or change the app
version — that stays an explicit, separate decision.

---

## Limitations

- Designed for the App Store (fastlane `deliver` layout). The screenshot technique
  is store-agnostic, but the metadata/keyword rules are Apple's.
- Band detection (`detect`) is a heuristic starting point — always eyeball the
  crop and adjust `--y0/--y1`.
- Translation quality is the image/text model's; always review returned bands for
  spelling and fit, especially RTL and CJK.
- The skill produces files and hands off; it does not manage certificates,
  provisioning, or App Review submission.

## License

[MIT](LICENSE) © 2026 Mazen Tamer Salah

## Acknowledgements

Built as a reusable Claude Code skill for shipping indie iOS apps to a global
audience. Pairs well with a screenshot-*generation* skill (to create the English
base screenshots) and an App Store review pre-flight skill.
