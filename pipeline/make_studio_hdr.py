#!/usr/bin/env python3
"""
Generate a neutral studio-lighting environment (Radiance .hdr) for the viewer.

Why this and not a stock HDRI: metal is pure reflection, so it can only look
real if it reflects something believable. model-viewer's built-in "neutral" is a
soft uniform dome -- there is nothing in it to reflect, so metal renders as a
flat gradient, which is exactly the "CG look". A stock outdoor HDRI has plenty
of structure but tints everything (the sunrise one turned the gold blue).

So: build a light tent. Large bright panels separated by dark gaps, which is
what puts crisp streak highlights on jewellery, and pure-white by construction
so it cannot cast a colour.

It must be true HDR, not PNG: an 8-bit image clamps at 1.0, and a specular
highlight needs values far above that to read as a light source rather than a
grey smudge. Panels here run 6-30x.
"""
import math, struct, os

W, H = 1024, 512
OUT = "/private/tmp/claude-501/-Users-robeirtoma/218035ca-7e83-4096-a998-68e093b899ac/scratchpad/ring_mvp/studio.hdr"

AMBIENT = 0.075          # dark surround so panels read as distinct lights

# (u_center, v_center, half_w, half_h, intensity, edge_softness)
# u wraps horizontally (azimuth), v is 0 at zenith -> 1 at nadir.
#
# Panel SIZE matters as much as intensity. The first version used a key panel
# spanning ~23% of the azimuth, so a near-mirror surface (white gold, roughness
# 0.06) reflected it across the entire band and clipped to flat white at any
# exposure. Real softboxes subtend a smaller angle: small+bright gives tight
# streak highlights against a darker body, which is the jewellery look.
# A broad, DIM ceiling panel supplies overall fill so the form still reads.
# Intensities pulled down again: at 22x the gem's near-mirror TABLE facet
# reflected the key panel directly and clipped to white, which both destroyed
# the black stone (its flat top read as a white band) and looked like a "gap"
# against the dark pavilion below. A gem table is a mirror -- it shows the light
# source at its literal brightness, so the source has to be sane.
PANELS = [
    (0.30, 0.26, 0.055, 0.095, 10.0, 0.050),   # key softbox
    (0.70, 0.34, 0.065, 0.105,  4.0, 0.055),   # fill, opposite side
    (0.95, 0.46, 0.035, 0.075,  7.0, 0.035),   # rim/kicker
    (0.50, 0.06, 0.500, 0.110,  2.2, 0.090),   # broad dim ceiling = fill light
    (0.12, 0.56, 0.055, 0.065,  3.0, 0.050),   # low side accent
]

BOUNCE = 1.30            # floor bounce so undersides are not dead black


def smoothstep(e0, e1, x):
    if e1 <= e0:
        return 0.0 if x < e0 else 1.0
    t = (x - e0) / (e1 - e0)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def panel_value(u, v):
    total = 0.0
    for cu, cv, hw, hh, inten, soft in PANELS:
        # wrap-aware horizontal distance
        du = abs(u - cu)
        du = min(du, 1.0 - du)
        dv = abs(v - cv)
        fu = 1.0 - smoothstep(hw, hw + soft, du)
        fv = 1.0 - smoothstep(hh, hh + soft, dv)
        total += inten * fu * fv
    return total


def to_rgbe(r, g, b):
    v = max(r, g, b)
    if v < 1e-32:
        return (0, 0, 0, 0)
    m, e = math.frexp(v)                 # v = m * 2**e, 0.5 <= m < 1
    scale = m * 256.0 / v
    return (min(255, int(r * scale)), min(255, int(g * scale)),
            min(255, int(b * scale)), e + 128)


def main():
    rows = []
    for y in range(H):
        v = (y + 0.5) / H
        # gentle vertical gradient: brighter near the floor for bounce light
        base = AMBIENT * (1.0 + BOUNCE * smoothstep(0.55, 1.0, v))
        row = bytearray()
        for x in range(W):
            u = (x + 0.5) / W
            val = base + panel_value(u, v)
            r, g, b, e = to_rgbe(val, val, val)   # neutral: no colour cast possible
            row += bytes((r, g, b, e))
        rows.append(bytes(row))

    with open(OUT, "wb") as f:
        f.write(b"#?RADIANCE\n")
        f.write(b"FORMAT=32-bit_rle_rgbe\n\n")
        f.write(f"-Y {H} +X {W}\n".encode())
        for row in rows:
            f.write(row)                          # flat RGBE (no RLE)

    peak = AMBIENT * (1 + BOUNCE) + max(p[4] for p in PANELS)
    print(f"wrote {OUT}  {os.path.getsize(OUT)/1e6:.2f}MB  {W}x{H}  peak~{peak:.1f}")


if __name__ == "__main__":
    main()
