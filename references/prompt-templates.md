# Gemini prompt templates

Copy/paste prompts for the two translation jobs. Replace `<LANGUAGE>` and the
bracketed text. Provide the **exact** target strings yourself — don't let the
model free-translate — so you control wording, line breaks and fit.

---

## 1. Screenshot caption band — `mcp__gemini__edit_image`

Model: `gemini-3-pro-image-preview`. Input: the cropped caption band.

```
Translate ALL visible text in this image from English to <LANGUAGE>. Use exactly
this text:
- Headline (<N> lines, keep <N> lines): "<LINE 1>" / "<LINE 2>" / ...
- Subtitle: "<SUBTITLE>"

CRITICAL constraints:
- Keep the EXACT same font family, weight, size, color(s), letter-spacing and
  alignment as the original (<state colours, e.g. "dark maroon headline; white
  subtitle", or "first letter dark, rest white">).
- Keep EVERY non-text element pixel-identical and in place: the background, the
  rounded highlight blob behind <WHICH WORD>, and any arrow / curved boundary /
  squiggle. Do NOT move, resize, recolor, add, or remove any graphic element.
- Only replace the letterforms with the <LANGUAGE> translation, on the same
  baselines. Keep it concise to fit the same width.
- Output the full image at the same dimensions and composition.
```

### Spelling correction (when a glyph is wrong)
Re-run the same prompt but spell the offending word out:

```
... line 3 "<WORD>" (spelled <W>-<O>-<R>-<D>, NOT "<wrong rendering>") ...
```

### Right-to-left / sparse layouts (Arabic, Hebrew)
If the model appends the translation and leaves the source text in place, force a
clean replace:

```
Produce a version where the English words are COMPLETELY REMOVED (no Latin letters
may remain anywhere) and replaced with <LANGUAGE>. The output must contain ONLY
this <LANGUAGE> text: <lines>. Erase the original glyphs and fill that area with
the same background so no trace of the source text remains. Render natural
right-to-left text. Keep the background and the highlight blob in place.
```

### CJK / non-Latin
Add: `Render the <LANGUAGE> text in a clean bold sans-serif <LANGUAGE> font at a
similar weight and size to the original.` (The model substitutes an appropriate
script font; the Latin marketing font won't cover CJK/Arabic glyphs.)

---

## 2. Metadata prose — `mcp__gemini__gemini_chat`

```
Translate this App Store <FIELD> from English to <LANGUAGE> for the <LOCALE>
storefront. Keep the marketing tone and meaning; do not add claims, guarantees, or
features the source does not state. Localize phrasing/numerals naturally; keep
product names and trademarks unchanged. Hard limit: <LIMIT> characters — if the
natural translation is longer, tighten it to fit. Return only the translated text,
no quotes or commentary.

SOURCE:
<paste the English field>
```

Field limits to put in `<LIMIT>`: name 30, subtitle 30, promotional_text 170,
description 4000, release_notes 4000. Validate afterwards with
`scripts/check_metadata.py`.

> Keywords are **not** translated with this template — they are rebuilt from
> store-specific popularity data. See `keyword-research.md`.
