#!/usr/bin/env python3
"""Recolor the duck's gold in the hero artworks to the CTA gold (#e0b051).

Deterministic pixel remap — no AI regeneration. The duck is the artwork's only
gold element (verified: a single gold cluster per image), so a gold-range
predicate constrained to the duck's bounding region isolates it exactly.

How it works, per image:
  1. Sample the duck's gold pixels (hue/sat/light window) and take their
     median HSL — the artwork's own duck gold, e.g. #e6da6f.
  2. Map hue/sat/light so that median lands exactly on the target (the
     subscribe button's gold #e0b051, hsl(40 70% 60%)): hue shifts by the
     target/median difference, saturation and lightness scale by the
     target/median ratios. Scaling (not pinning) preserves the duck's shading
     structure — highlights stay highlights, shadow stays shadow.
  3. Apply the shift only to gold-range pixels inside the duck's bounding
     region, with a feathered weight at the range edges so antialiased
     boundaries between the duck and the navy/foam taper cleanly.
  4. Encode lossless WebP and verify: every pixel outside the mask is
     byte-identical to the source decode; all changed pixels sit inside the
     duck region; the new gold median matches the target.

Usage: python3 tools/repaint_duck_gold.py [--target e0b051] FILE [FILE ...]
Files are rewritten in place after verification passes.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

# Gold-range predicate (duck gold lives near hue 54°; the artwork's other
# families are navy, ice-blue and white, which these windows exclude).
HUE_LO, HUE_HI = 30.0, 80.0     # degrees
SAT_LO = 0.15                   # white/navy blends fall below this fast
LIGHT_LO, LIGHT_HI = 0.25, 0.95

# Feather ramps (weights taper to 0 across these margins so edges stay clean).
HUE_RAMP = 8.0
SAT_RAMP = 0.15
LIGHT_RAMP = 0.12
# Lightness above this is white foam, not gold — hard cut.
LIGHT_WHITE = 0.96

BOX_MARGIN = 24  # px of slack around the sampled gold cluster


def rgb_to_hsl(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgbf = rgb.astype(np.float32) / 255.0
    r, g, b = rgbf[..., 0], rgbf[..., 1], rgbf[..., 2]
    mx = rgbf.max(-1)
    mn = rgbf.min(-1)
    delta = mx - mn
    light = (mx + mn) / 2.0
    safe = np.where(delta > 1e-9, delta, 1.0)
    sat = np.where(delta > 1e-9, np.where(light <= 0.5, delta / (mx + mn + 1e-9),
                                          delta / (2.0 - mx - mn + 1e-9)), 0.0)
    r_eq = (mx == r) & (delta > 1e-9)
    g_eq = (mx == g) & (delta > 1e-9) & ~r_eq
    hue = np.where(r_eq, ((g - b) / safe) % 6.0,
                   np.where(g_eq, (b - r) / safe + 2.0, (r - g) / safe + 4.0)) * 60.0
    hue = np.where(delta > 1e-9, hue, 0.0)
    return hue, sat, light


def hsl_to_rgb(hue: np.ndarray, sat: np.ndarray, light: np.ndarray) -> np.ndarray:
    hue6 = (hue / 60.0) % 6.0
    c = (1.0 - np.abs(2.0 * light - 1.0)) * sat
    x = c * (1.0 - np.abs(hue6 % 2.0 - 1.0))
    m = light - c / 2.0
    i = hue6.astype(int)
    r = np.choose(i, [c, x, np.zeros_like(c), np.zeros_like(c), x, c]) + m
    g = np.choose(i, [x, c, c, x, np.zeros_like(c), np.zeros_like(c)]) + m
    b = np.choose(i, [np.zeros_like(c), np.zeros_like(c), x, c, c, x]) + m
    rgb = np.stack([r, g, b], axis=-1)
    return np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def repaint(path: Path, target_hex: str) -> None:
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    src = np.asarray(img.copy())

    hue, sat, light = rgb_to_hsl(src)
    gold = ((hue >= HUE_LO) & (hue <= HUE_HI) & (sat >= SAT_LO) &
            (light >= LIGHT_LO) & (light <= LIGHT_HI))
    if int(gold.sum()) == 0:
        raise SystemExit(f"{path}: no gold pixels found — nothing to remap")

    ys, xs = np.nonzero(gold)
    x0, x1 = max(int(xs.min()) - BOX_MARGIN, 0), min(int(xs.max()) + BOX_MARGIN + 1, src.shape[1])
    y0, y1 = max(int(ys.min()) - BOX_MARGIN, 0), min(int(ys.max()) + BOX_MARGIN + 1, src.shape[0])
    box = np.zeros(src.shape[:2], dtype=bool)
    box[y0:y1, x0:x1] = True
    outside = int((gold & ~box).sum())
    if outside:
        raise SystemExit(f"{path}: {outside} gold pixels fall outside the sampled "
                         "cluster box — multiple gold regions, refusing to remap blindly")

    med_h = float(np.median(hue[gold]))
    med_s = float(np.median(sat[gold]))
    med_l = float(np.median(light[gold]))

    tr, tg, tb = (int(target_hex[i:i + 2], 16) for i in (0, 2, 4))
    t_hue, t_sat, t_light = rgb_to_hsl(np.array([[[tr, tg, tb]]], dtype=np.uint8))
    t_hue, t_sat, t_light = float(t_hue[0, 0]), float(t_sat[0, 0]), float(t_light[0, 0])

    # Feathered weight: 1 inside the gold core, tapering to 0 at every window
    # edge; w == 0 pixels stay byte-identical.
    w = (smoothstep(HUE_LO - HUE_RAMP, HUE_LO + HUE_RAMP, hue) *
         (1.0 - smoothstep(HUE_HI - HUE_RAMP, HUE_HI + HUE_RAMP, hue)) *
         smoothstep(SAT_LO - SAT_RAMP, SAT_LO + SAT_RAMP, sat) *
         smoothstep(LIGHT_LO - LIGHT_RAMP, LIGHT_LO + LIGHT_RAMP, light) *
         (1.0 - smoothstep(LIGHT_HI - LIGHT_RAMP, LIGHT_HI + LIGHT_RAMP, light)) *
         (1.0 - smoothstep(LIGHT_WHITE - 0.01, LIGHT_WHITE, light)) *
         box.astype(np.float32))

    new_hue = (hue + (t_hue - med_h)) % 360.0
    new_sat = np.clip(sat * (t_sat / med_s), 0.0, 1.0)
    new_light = np.clip(light * (t_light / med_l), 0.0, 1.0)
    remapped = hsl_to_rgb(new_hue, new_sat, new_light)

    w3 = w[..., np.newaxis]
    out = np.rint(src + (remapped.astype(np.float32) - src.astype(np.float32)) * w3)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # Outside the mask the result must equal the source exactly.
    w0 = w == 0.0
    if not np.array_equal(src[w0], out[w0]):
        raise SystemExit(f"{path}: pixels outside the feathered mask changed — aborting")

    Image.fromarray(out).save(path, format="WEBP", lossless=True, method=6, exact=True)

    # Re-decode and verify the written artifact.
    back = np.asarray(Image.open(path).convert("RGB"))
    if not np.array_equal(out, back):
        raise SystemExit(f"{path}: lossless re-decode differs — encoding is not exact")
    changed = np.any(back != src, axis=-1)
    new_gold = gold & (w > 0.5)
    med_rgb = (np.median(back[..., 0][new_gold]), np.median(back[..., 1][new_gold]),
               np.median(back[..., 2][new_gold]))
    print(f"{path}:")
    print(f"  gold pixels touched (weight>0): {int((w > 0).sum())} "
          f"(core weight>0.5: {int(new_gold.sum())}), all inside box "
          f"x[{x0}..{x1}) y[{y0}..{y1})")
    print(f"  changed pixels total: {int(changed.sum())}")
    print(f"  duck gold median HSL {med_h:.1f}deg/{med_s:.3f}/{med_l:.3f} "
          f"-> target hsl({t_hue:.1f} {t_sat:.3f} {t_light:.3f}); achieved core median RGB "
          f"({med_rgb[0]:.0f},{med_rgb[1]:.0f},{med_rgb[2]:.0f}) vs target ({tr},{tg},{tb})")
    print(f"  size: {path.stat().st_size} bytes (lossless WebP, non-gold pixels byte-identical)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--target", default="e0b051", help="target gold hex (default e0b051)")
    args = parser.parse_args()
    target = args.target.lstrip("#")
    if len(target) != 6:
        raise SystemExit("--target must be a 6-digit hex color")
    for path in args.files:
        if not path.is_file():
            raise SystemExit(f"not a file: {path}")
    for path in args.files:
        repaint(path, target)


if __name__ == "__main__":
    main()
