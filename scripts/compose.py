#!/usr/bin/env python3
"""
App Store screenshot caption localizer — band-translate + composite pipeline.

WHY
    Image models (e.g. Gemini / "Nano Banana Pro") cap their output at roughly a
    1500px long edge. Feeding a whole 1290x2796 store screenshot in and getting
    ~1500px back means *upscaling* the result — blurry text and a soft phone UI.

HOW
    Translate only the tight caption *band* (it is short, so the model's ~1500px
    output is a DOWNSCALE to the screenshot width = crisp) and composite that band
    back onto the PRISTINE screenshot. The phone mock-up is never touched, so the
    in-app UI stays pixel-sharp (and in its original language). A glyph + colour
    diff mask means highlight blobs, curved shapes, arrows and squiggles stay
    pristine while only the letterforms change.

PIPELINE (inside `composite`)
    1. Resize the translated band to the screenshot width (downscale = crisp).
    2. Additive-only median colour match — shift the band so its dominant
       background colour equals the original's. NEVER scale by std/IQR: that
       compresses contrast and erases dark text.
    3. Phase-correlation alignment — cancel the model's ~2-5px global drift so
       backgrounds line up and stay pristine.
    4. Mask = ((glyph local-contrast) OR (raw colour change)) within each
       text-line bounding box. Pure background (neither) stays 100% pristine, so
       there is no rectangular seam. The raw-colour term also erases elements that
       MOVED (e.g. a highlight blob shifting under right-to-left text) and longer
       source-text tails the translation does not cover.
    5. Guard the band's inner edge (the side facing the rest of the screenshot)
       so crop-boundary contrast and clipped decorations never seam.

USAGE
    Requires an interpreter with numpy + Pillow (`pip install -r requirements.txt`).

    python compose.py detect    BASE.png
        Suggest caption band rows (phone edges, caption extent, clean gap).

    python compose.py crop      BASE.png --y0 0 --y1 700 -o band.png
        Crop the caption band [y0, y1) full width. Send `band.png` to your image
        model to translate the text (see references/prompt-templates.md).

    python compose.py composite BASE.png --y0 0 --y1 700 \\
                       --band band_translated.png -o final.png
        Composite the translated band back onto the pristine screenshot.

This script contains no credentials and talks to no network — it is pure local
image maths. Translation and any store API calls happen elsewhere (your agent /
MCP servers).
"""
from __future__ import annotations

import argparse
import sys

try:
    import numpy as np
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    sys.exit(
        "compose.py needs numpy + Pillow.\n"
        "  pip install -r requirements.txt   (or: pip install numpy Pillow)"
    )


# --------------------------------------------------------------------------- #
# Colour + alignment helpers
# --------------------------------------------------------------------------- #
def color_transfer(src: Image.Image, ref: Image.Image) -> Image.Image:
    """ADDITIVE-only median match: shift `src` so its dominant background colour
    equals `ref`'s. Fixes a model's background/colour drift WITHOUT scaling,
    which would compress and erase dark text. Median is robust to text outliers.
    """
    s = np.asarray(src).astype(np.float32)
    r = np.asarray(ref).astype(np.float32)
    for c in range(3):
        s[..., c] = s[..., c] - np.median(s[..., c]) + np.median(r[..., c])
    return Image.fromarray(np.clip(s, 0, 255).astype(np.uint8))


def _align(gem_arr: np.ndarray, pri_arr: np.ndarray, maxshift: int = 12):
    """Integer (dy, dx) that best registers `gem_arr` onto `pri_arr` via phase
    correlation. Shifts beyond `maxshift` are treated as spurious and ignored."""
    import numpy.fft as fft

    g = gem_arr.mean(2).astype(np.float64)
    p = pri_arr.mean(2).astype(np.float64)
    g -= g.mean()
    p -= p.mean()
    cross = fft.rfft2(g) * np.conj(fft.rfft2(p))
    cross /= np.abs(cross) + 1e-9
    corr = fft.irfft2(cross, s=g.shape)
    dy, dx = np.unravel_index(np.argmax(corr), corr.shape)
    h, w = g.shape
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    if abs(dy) > maxshift:
        dy = 0
    if abs(dx) > maxshift:
        dx = 0
    return int(dy), int(dx)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def crop(base_path: str, y0: int, y1: int, out_path: str) -> None:
    im = Image.open(base_path).convert("RGB")
    width = im.size[0]
    im.crop((0, y0, width, y1)).save(out_path)
    print(f"band {width}x{y1 - y0} rows[{y0},{y1}) -> {out_path}")


def composite(
    base_path: str,
    y0: int,
    y1: int,
    band_path: str,
    out_path: str,
    thresh: int = 45,
    dilate: int = 3,
    feather: float = 2.0,
    guard: int = 28,
) -> None:
    base = Image.open(base_path).convert("RGB")
    width = base.size[0]
    band_h = y1 - y0
    pristine = base.crop((0, y0, width, y1))

    gem = Image.open(band_path).convert("RGB").resize((width, band_h), Image.LANCZOS)
    gem = color_transfer(gem, pristine)

    ga, pa = np.asarray(gem), np.asarray(pristine)
    dy, dx = _align(ga, pa)
    if dy or dx:
        gem = Image.fromarray(np.roll(ga, shift=(-dy, -dx), axis=(0, 1)))
        print(f"  aligned band by dy={-dy} dx={-dx}")

    p = np.asarray(pristine).astype(np.int16)
    g = np.asarray(gem).astype(np.int16)
    diff = np.abs(g - p).max(axis=2)
    raw = diff > thresh

    # 1) bounding box of each text line — limits where we operate so curves /
    #    phone edges outside the caption are never touched.
    active = raw.sum(axis=1) > (width * 0.003)
    box = np.zeros_like(raw, dtype=bool)
    rows = np.where(active)[0]
    if len(rows):
        start = prev = rows[0]
        blocks = []
        for r in rows[1:]:
            if r - prev > 14:
                blocks.append((start, prev))
                start = r
            prev = r
        blocks.append((start, prev))
        for b0, b1 in blocks:
            b0 = max(0, b0 - 10)
            b1 = min(band_h - 1, b1 + 10)
            cols = np.where(raw[b0 : b1 + 1].any(axis=0))[0]
            if not len(cols):
                continue
            c0 = max(0, cols.min() - 12)
            c1 = min(width - 1, cols.max() + 12)
            box[b0 : b1 + 1, c0 : c1 + 1] = True

    # 2) ink = glyph local-contrast OR a real colour change, within the boxes.
    pblur = np.asarray(pristine.filter(ImageFilter.GaussianBlur(7))).astype(np.int16)
    gblur = np.asarray(gem.filter(ImageFilter.GaussianBlur(7))).astype(np.int16)
    p_ink = np.abs(p - pblur).max(axis=2)
    g_ink = np.abs(g - gblur).max(axis=2)
    ink = ((p_ink > 12) | (g_ink > 12) | raw) & box

    # guard the inner edge (side facing the rest of the screenshot)
    if y0 == 0:
        ink[band_h - guard :, :] = False  # caption on top -> guard bottom
    else:
        ink[:guard, :] = False  # caption on bottom -> guard top

    mask = Image.fromarray((ink * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MaxFilter(2 * dilate + 1)).filter(
        ImageFilter.GaussianBlur(feather)
    )

    out = base.copy()
    out.paste(gem, (0, y0), mask)
    out = out.convert("RGB")  # App Store rejects screenshots with an alpha channel
    out.save(out_path, "PNG")
    coverage = (np.asarray(mask) > 10).mean() * 100
    print(f"saved {out_path} {out.size} ink-coverage={coverage:.1f}%")


def detect(base_path: str) -> None:
    """Heuristic band suggestion: locate the phone mock-up (dark neutral bezel in
    the centre columns) and the caption text above / below it."""
    im = Image.open(base_path).convert("RGB")
    width, height = im.size
    a = np.asarray(im).astype(np.int16)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    lum = a.mean(2)

    centre = slice(int(width * 0.23), int(width * 0.77))
    bezel = ((lum < 70) & (np.abs(R - G) < 18) & (np.abs(R - B) < 18))[:, centre].sum(1) > 200
    rows = np.where(bezel)[0]
    p_top, p_bot = (int(rows.min()), int(rows.max())) if len(rows) else (None, None)

    text = ((R - G > 18) & (R - B > 8) & (lum < 175)) | ((R > 225) & (G > 225) & (B > 225))
    text_rows = text.sum(1)

    print(f"{base_path}: {width}x{height}  phone~={p_top}-{p_bot}")
    if p_top:
        top = np.where(text_rows[:p_top] > 10)[0]
        if len(top):
            print(
                f"  TOP caption ~= {int(top.min())}-{int(top.max())} ; "
                f"gap to phone ~= {int(top.max())}-{p_top}  "
                f"-> try: --y0 0 --y1 {min(p_top - 5, int(top.max()) + 60)}"
            )
    if p_bot:
        bot = np.where(text_rows[p_bot:] > 10)[0] + p_bot
        if len(bot):
            print(
                f"  BOTTOM caption ~= {int(bot.min())}-{int(bot.max())} ; "
                f"gap from phone ~= {p_bot}-{int(bot.min())}  "
                f"-> try: --y0 {max(p_bot + 5, int(bot.min()) - 60)} --y1 {height}"
            )
    print(
        "  Keep the band TIGHT to the caption; exclude arrows / curved-shape "
        "boundaries where you can. The inner edge is guarded, so leave ~28px margin."
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Localize App Store screenshot captions by band-translating "
        "and compositing onto the pristine screenshot.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="suggest caption band rows for a screenshot")
    d.add_argument("base", help="pristine screenshot PNG")

    c = sub.add_parser("crop", help="crop the caption band to send for translation")
    c.add_argument("base", help="pristine screenshot PNG")
    c.add_argument("--y0", type=int, required=True, help="band top row (inclusive)")
    c.add_argument("--y1", type=int, required=True, help="band bottom row (exclusive)")
    c.add_argument("-o", "--out", required=True, help="output band PNG")

    m = sub.add_parser("composite", help="composite a translated band back onto the screenshot")
    m.add_argument("base", help="pristine screenshot PNG")
    m.add_argument("--y0", type=int, required=True, help="band top row (inclusive)")
    m.add_argument("--y1", type=int, required=True, help="band bottom row (exclusive)")
    m.add_argument("--band", required=True, help="translated band PNG (from your image model)")
    m.add_argument("-o", "--out", required=True, help="output full-size screenshot PNG")
    m.add_argument("--thresh", type=int, default=45, help="colour-diff threshold (default 45)")
    m.add_argument("--feather", type=float, default=2.0, help="mask feather px (default 2)")
    m.add_argument("--guard", type=int, default=28, help="inner-edge guard rows (default 28)")

    args = parser.parse_args(argv)
    if args.cmd == "detect":
        detect(args.base)
    elif args.cmd == "crop":
        crop(args.base, args.y0, args.y1, args.out)
    elif args.cmd == "composite":
        composite(
            args.base, args.y0, args.y1, args.band, args.out,
            thresh=args.thresh, feather=args.feather, guard=args.guard,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
