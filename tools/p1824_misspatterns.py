#!/usr/bin/env python3
"""P1824: relief patterns for a missing texture's flat colour (hl2 plugin, hl2_missingpattern).

Writes ftesurf/gfx/misspattern/<name>_d.png (grey detail, mean DETAIL_MEAN within 8-bit quantization: the plugin
normalizes the colour by it, approximately retaining the existing tint) and <name>_n.png (tangent-space normal, Source's DX
layout: +x along u, +y along v = down the rows, as VRAD's bump basis). 256 px tiles drawn at 256 world units
(1 px = 1 unit), features 32-128 units so they survive surf speed and mips. All periodic: every feature is
built on wrapped coordinates, so the tiles repeat without a seam. Original procedural work, deterministic
(fixed seeds); rerun to regenerate byte-identical files.

  python3 tools/p1824_misspatterns.py [--out ftesurf/gfx/misspattern] [--preview sheet.png]
"""
import argparse
import os

import numpy as np
from PIL import Image

N = 256
DETAIL_MEAN = 200 / 255.0     # mat_vmt.c VMT_MISSPAT_MEAN
NAMES = ("brick", "concrete", "wood", "metal", "glass", "grass", "cracks")

yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)


def noise(rng, f0, f1, power=1.0):
    """Periodic band-limited noise, unit std: white noise kept between f0 and f1 cycles per tile."""
    f = np.fft.fftfreq(N) * N
    r = np.hypot(*np.meshgrid(f, f))
    w = np.where((r >= f0) & (r <= f1), 1.0 / np.maximum(r, 1.0) ** power, 0.0)
    n = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((N, N))) * w))
    return n / (n.std() + 1e-12)


def aniso(rng, ang, flong, f0, f1):
    """Periodic strokes along angle ang (radians): below flong cycles along them, f0..f1 across. Unit std."""
    f = np.fft.fftfreq(N) * N
    fx, fy = np.meshgrid(f, f)
    along = np.abs(fx * np.cos(ang) + fy * np.sin(ang))
    across = np.abs(-fx * np.sin(ang) + fy * np.cos(ang))
    w = ((along <= flong) & (across >= f0) & (across <= f1)).astype(np.float64)
    n = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((N, N))) * w))
    return n / (n.std() + 1e-12)


def blur(a, sigma):
    f = np.fft.fftfreq(N)
    fx, fy = np.meshgrid(f, f)
    return np.real(np.fft.ifft2(np.fft.fft2(a) * np.exp(-2 * (np.pi * sigma) ** 2 * (fx * fx + fy * fy))))


def wrap(d):
    return (d + N / 2) % N - N / 2


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def voronoi(pts, px=xx, py=yy):
    """Nearest two seeds (wrapped): distance to the nearest, the cell id, and distance to the cell edge."""
    dx = wrap(px[..., None] - pts[:, 0])
    dy = wrap(py[..., None] - pts[:, 1])
    d2 = dx * dx + dy * dy
    o = np.argsort(d2, axis=-1)[..., :2]
    i1, i2 = o[..., 0], o[..., 1]
    take = lambda a, i: np.take_along_axis(a, i[..., None], -1)[..., 0]
    v1x, v1y, v2x, v2y = take(dx, i1), take(dy, i1), take(dx, i2), take(dy, i2)
    d1, d2b = v1x * v1x + v1y * v1y, v2x * v2x + v2y * v2y
    edge = (d2b - d1) / (2 * np.hypot(v1x - v2x, v1y - v2y) + 1e-9)
    return np.sqrt(d1), i1, edge


def blocks(w, h, offset, gap, bevel):
    """Running-bond blocks w x h, alternate rows offset; distance-shaped face mask and per-block ids."""
    row = np.floor(yy / h)
    xs = xx + (row % 2) * offset
    col = np.floor(xs / w) % (N // w)
    ex = np.minimum(xs % w, w - xs % w)
    ey = np.minimum(yy % h, h - yy % h)
    e = np.minimum(ex, ey)
    face = smooth(gap / 2, gap / 2 + bevel, e)
    return face, (row * 64 + col).astype(int), e


def brick(rng):
    face, ids, e = blocks(128, 64, 64, 7, 4)
    per = rng.uniform(-1, 1, ids.max() + 1)
    chip = smooth(0.6, 1.4, noise(rng, 10, 40)) * (1 - smooth(3, 9, e))   # chipped arrises
    rough = noise(rng, 3, 20, 0.5)
    h = face * (5 + 0.6 * per[ids] + 0.5 * rough) - 2.5 * chip * face + 0.3 * noise(rng, 20, 80)
    d = 0.70 + 0.30 * face - 0.12 * chip * face + 0.05 * per[ids] * face + 0.03 * rough
    return h, d


def concrete(rng):
    face, ids, e = blocks(128, 128, 0, 4, 2)
    mott = noise(rng, 1, 8, 1.0)
    pits = np.zeros((N, N))
    for _ in range(38):
        cx, cy, r = rng.uniform(0, N), rng.uniform(0, N), rng.uniform(2.0, 4.5)
        pits = np.maximum(pits, 1 - smooth(0, r, np.hypot(wrap(xx - cx), wrap(yy - cy))))
    h = 2.5 * face + 0.5 * noise(rng, 8, 64, 0.5) + 0.8 * mott - 1.8 * pits
    d = 0.78 + 0.22 * face + 0.06 * mott - 0.20 * pits + 0.02 * noise(rng, 16, 64)
    return h, d


def wood(rng):
    pw = 64                                   # four boards a tile, each the tile's length with one butt joint
    board = np.floor(yy / pw).astype(int)
    xs = (xx + np.array([0, 150, 70, 200])[board]) % N
    ex = np.minimum(xs, N - xs)
    ey = np.minimum(yy % pw, pw - yy % pw)
    face = smooth(2, 5, np.minimum(ex, ey))
    per = rng.uniform(-1, 1, 4)[board]
    grain = aniso(rng, 0.0, 2, 5, 18)
    for _ in range(4):                        # knots
        cx, cy = rng.uniform(0, N), rng.uniform(0, N)
        r = np.hypot(wrap(xx - cx) / 2.2, wrap(yy - cy))
        grain -= 2.5 * np.exp(-r * r / 18) - 0.8 * np.sin(r / 1.5) * np.exp(-r * r / 60)
    cup = smooth(0, 14, ey)                   # boards crown slightly, low at their edges
    h = face * (3 + 0.6 * cup + 0.35 * grain + 0.3 * per)
    d = 0.70 + 0.30 * face + 0.06 * per * face + 0.04 * grain * face + 0.015 * noise(rng, 4, 24)
    return h, d


def metal(rng):
    face, ids, e = blocks(128, 128, 0, 3, 2)
    per = rng.uniform(-1, 1, ids.max() + 1)
    rx = (xx % 128)
    ry = (yy % 128)
    riv = np.zeros((N, N))
    for k in range(4):                        # rivets every 32 along each plate edge, 7 in
        c = 16 + 32 * k
        for cx, cy in ((c, 7), (c, 121), (7, c), (121, c)):
            riv = np.maximum(riv, np.sqrt(np.clip(1 - ((rx - cx) ** 2 + (ry - cy) ** 2) / 16.0, 0, 1)))
    brushed = blur(np.random.default_rng(rng.integers(1 << 30)).standard_normal((N, N)), 0.5)
    brushed = np.real(np.fft.ifft2(np.fft.fft2(brushed) * (np.abs(np.fft.fftfreq(N))[None, :] < 0.03)))
    brushed /= brushed.std() + 1e-9
    dent = noise(rng, 1, 4, 1.0)
    h = face * (2.0 + 0.5 * dent + 0.08 * brushed) + 2.0 * riv
    d = 0.72 + 0.28 * face + 0.04 * per[ids] * face + 0.025 * brushed + 0.10 * riv
    ring = np.zeros((N, N))
    for k in range(4):
        c = 16 + 32 * k
        for cx, cy in ((c, 7), (c, 121), (7, c), (121, c)):
            r = np.hypot(rx - cx, ry - cy)
            ring = np.maximum(ring, smooth(3.0, 4.0, r) * (1 - smooth(4.0, 6.0, r)))
    d -= 0.12 * ring
    return h, d


def glass(rng):
    fw = 10
    ex = np.minimum(xx % 128, 128 - xx % 128)
    ey = np.minimum(yy % 128, 128 - yy % 128)
    frame = 1 - smooth(fw / 2, fw / 2 + 3, np.minimum(ex, ey))
    wave = noise(rng, 2, 10, 1.0)
    h = 3.0 * frame + 0.25 * wave * (1 - frame)
    sheen = 0.03 * np.sin(2 * np.pi * (xx + yy) / 128) * (1 - frame)
    d = 1.0 - 0.16 * frame + 0.015 * wave + sheen
    return h, d


def grass(rng):
    pts = rng.uniform(0, N, (80, 2))
    wx, wy = 6 * noise(rng, 2, 8), 6 * noise(rng, 2, 8)
    _, ids, edge = voronoi(pts, (xx + wx) % N, (yy + wy) % N)
    clump = smooth(0, 14, edge)               # tufts ~28 units across
    layers = [aniso(rng, a, 3, 10, 28) for a in (0.3, 1.1, 1.9, 2.7)]
    pick = rng.integers(0, 4, len(pts))[ids]
    blades = np.choose(pick, layers) * clump  # each tuft leans its own way
    patch = noise(rng, 1, 5, 1.0)
    h = 3.0 * clump + 0.5 * blades + 1.2 * patch
    d = 0.76 + 0.20 * clump + 0.04 * blades + 0.07 * patch
    return h, d


def grid_seeds(rng, k, jitter):
    """k x k seeds on a jittered grid: even cells, none so small it reads as a blot."""
    g = (np.arange(k) + 0.5) * N / k
    gx, gy = np.meshgrid(g, g)
    return np.stack([gx.ravel(), gy.ravel()], 1) + rng.uniform(-jitter, jitter, (k * k, 2)) * N / k


def cracks(rng):
    wx, wy = 9 * noise(rng, 2, 7), 9 * noise(rng, 2, 7)
    jx, jy = 1.2 * noise(rng, 10, 30), 1.2 * noise(rng, 10, 30)
    px, py = (xx + wx + jx) % N, (yy + wy + jy) % N
    _, _, e1 = voronoi(grid_seeds(rng, 3, 0.3), px, py)
    _, _, e2 = voronoi(grid_seeds(rng, 4, 0.35), px, py)
    keep = smooth(0.5, 1.0, noise(rng, 1, 3))            # branches only in places, as long broken runs
    w = 2.2 + 1.3 * smooth(-1, 1, noise(rng, 2, 8))
    main = 1 - smooth(w, w + 1.5, e1)
    minor = (1 - smooth(0.9, 2.0, e2)) * keep
    shoulder = 1 - smooth(0, 10, e1)
    crack = np.maximum(main, 0.7 * minor)
    mott = noise(rng, 1, 6, 1.0)
    h = -5.0 * crack - 1.0 * shoulder + 0.6 * mott + 0.2 * noise(rng, 8, 32, 0.5)
    d = 0.96 - 0.45 * crack - 0.07 * shoulder + 0.06 * mott + 0.015 * noise(rng, 8, 32)
    return h, d


def normals(h):
    h = blur(h, 0.7)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    n = np.dstack([-gx, -gy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return np.clip(np.round((n * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)


def detail(d):
    d = blur(d, 0.5)
    for _ in range(8):                     # target the plugin's mean through clipping, before 8-bit quantization
        d = np.clip(d * (DETAIL_MEAN / d.mean()), 0, 1)
    q = np.clip(np.round(d * 255), 0, 255).astype(np.uint8)
    return np.dstack([q, q, q])


def build(name):
    rng = np.random.default_rng(1824 + NAMES.index(name))
    h, d = globals()[name](rng)
    return normals(h), detail(d)


def preview(maps, path):
    """Each pattern under a few colours, lit from the upper left by its own normals (eyeballing aid only)."""
    cols = [(0.72, 0.42, 0.30), (0.55, 0.57, 0.60), (0.30, 0.55, 0.35), (0.85, 0.82, 0.70)]
    L = np.array([-0.5, -0.5, 0.7]) / np.linalg.norm([-0.5, -0.5, 0.7])
    rows = []
    for name in NAMES:
        nm, dt = maps[name]
        n = nm.astype(np.float64) / 127.5 - 1
        shade = 0.55 + 0.45 * np.clip(n @ L, 0, 1) / L[2]
        g = dt[..., 0] / 255.0 / DETAIL_MEAN
        rows.append(np.hstack([np.clip(np.dstack([g * c[i] * shade for i in range(3)]), 0, 1) for c in cols]))
    Image.fromarray((np.vstack(rows) * 255).astype(np.uint8)).save(path)


def main():
    ap = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", default=os.path.join(root, "ftesurf", "gfx", "misspattern"))
    ap.add_argument("--preview")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    maps = {}
    for name in NAMES:
        nm, dt = build(name)
        assert nm.shape == (N, N, 3) and dt.shape == (N, N, 3)
        Image.fromarray(nm).save(os.path.join(a.out, name + "_n.png"), optimize=True)
        Image.fromarray(dt).save(os.path.join(a.out, name + "_d.png"), optimize=True)
        maps[name] = (nm, dt)
        print("%-8s detail mean %.4f (want %.4f)  range %d..%d" % (name, dt[..., 0].mean() / 255, DETAIL_MEAN,
              dt[..., 0].min(), dt[..., 0].max()))
    if a.preview:
        preview(maps, a.preview)


if __name__ == "__main__":
    main()
