// SPDX-License-Identifier: Apache-2.0
/**
 * Stained liquid glass for the Photo Clock's figures, baked into a canvas
 * once per minute / photo / setting rather than filtered live: an SVG
 * displacement or backdrop filter would re-run on every frame on the Pi.
 *
 * Each figure is a rounded lens. Its height falls off over the last few
 * pixels to the outline; the slope bends the photo behind it (with a slight
 * split between red and blue at the edges), lights the side facing the
 * photo's own brightest spot in that light's colour, rims the whole outline
 * thinly, and darkens the far edges. A tint pools in the thick middle of
 * the strokes, the way coloured glass is deeper where it's thicker, and
 * the glass throws a faint caustic of it onto the photo away from the light.
 */

import { effectiveTier } from "./tier.svelte";

export type RGB = [number, number, number];

export interface Light {
  /** Where the light is, in the photo's own 0–1 coordinates. */
  u: number;
  v: number;
  rgb: RGB;
}

const lightCache = new Map<string, Light>();

/** The photo's light: the middle of its brightest tenth, and its colour.
    Evenly lit photos get a soft daylight from above left. Cached by image src / key. */
export function findLight(
  img: HTMLImageElement | HTMLCanvasElement,
  cacheKey?: string,
): Light {
  const fallback: Light = { u: 0.15, v: -0.3, rgb: [255, 250, 240] };
  const key = cacheKey ?? (img instanceof HTMLImageElement ? img.src : "");
  if (key && lightCache.has(key)) return lightCache.get(key)!;

  const w = 48;
  const [iw, ih] =
    img instanceof HTMLImageElement
      ? [img.naturalWidth, img.naturalHeight]
      : [img.width, img.height];
  const h = Math.max(1, Math.round((w * ih) / iw));
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  if (!ctx) return fallback;
  ctx.drawImage(img, 0, 0, w, h);
  let px: Uint8ClampedArray;
  try {
    px = ctx.getImageData(0, 0, w, h).data;
  } catch {
    return fallback; // a cross-origin photo can't be read
  }
  const lum = new Float32Array(w * h);
  for (let i = 0; i < w * h; i++)
    lum[i] =
      0.2126 * px[i * 4]! + 0.7152 * px[i * 4 + 1]! + 0.0722 * px[i * 4 + 2]!;
  const sorted = Float32Array.from(lum).sort();
  const cut = sorted[Math.floor(sorted.length * 0.9)]!;
  if (cut - sorted[Math.floor(sorted.length * 0.5)]! < 30) {
    if (key) lightCache.set(key, fallback);
    return fallback;
  }
  let n = 0;
  let su = 0;
  let sv = 0;
  const rgb: RGB = [0, 0, 0];
  for (let i = 0; i < w * h; i++) {
    if (lum[i]! < cut) continue;
    n++;
    su += (i % w) + 0.5;
    sv += Math.floor(i / w) + 0.5;
    rgb[0] += px[i * 4]!;
    rgb[1] += px[i * 4 + 1]!;
    rgb[2] += px[i * 4 + 2]!;
  }
  // Lift the colour to a light: keep its hue, push it near full brightness.
  const top = Math.max(...rgb) || 1;
  const result: Light = {
    u: su / n / w,
    v: sv / n / h,
    rgb: rgb.map((c) => 155 + (100 * c) / top) as RGB,
  };
  if (key) {
    lightCache.set(key, result);
    if (lightCache.size > 50)
      lightCache.delete(lightCache.keys().next().value!);
  }
  return result;
}

export interface Bake extends Figures {
  canvas: HTMLCanvasElement;
  img: HTMLImageElement;
  /** Photo → screen: object-fit cover's scale and offset. */
  scale: number;
  x: number;
  y: number;
  look: Look;
  /** 0–1: how milky the glass is (the Glass opacity setting). */
  milk: number;
  tint: RGB | null;
  light: Light;
  /** 0–1: how bright the photo is behind the figures (glareOf). */
  glare: number;
  /** 0–1: mean photo luma behind the figures. */
  luma?: number;
}

/** How the glass answers a bright photo behind it (Bake.glare at 1): this
    much less milk, this much smoke, this much more shade on the rim away
    from the light, and its shadows this many times darker again. Shared
    with glassDigits.ts's shader. */
export const GLARE = { milk: 0.6, smoke: 0.14, shade: 0.6, shadow: 2.6 };

/** A photo's brightness behind the glass (mean luma, 0–1) as glare: none
    up to a mid-grey, all of it by a pale wall or sky. */
export function glareOf(luma: number): number {
  const t = Math.min(1, Math.max(0, (luma - 0.45) / 0.35));
  return t * t * (3 - 2 * t);
}

/** A photo's darkness behind the glass (mean luma, 0–1) as gloom: none
    for pale or mid-tones, full for dark night skies or deep shadows. */
export function gloomOf(luma: number): number {
  const t = Math.min(1, Math.max(0, (0.45 - luma) / 0.35));
  return t * t * (3 - 2 * t);
}

function boxBlur(
  src: Float32Array,
  w: number,
  h: number,
  r: number,
  tmp?: Float32Array,
  out?: Float32Array,
): Float32Array {
  const t = tmp ?? new Float32Array(w * h);
  const o = out ?? new Float32Array(w * h);
  const d = 2 * r + 1;
  for (let y = 0; y < h; y++) {
    let s = 0;
    const row = y * w;
    for (let x = -r; x <= r; x++)
      s += src[row + Math.min(w - 1, Math.max(0, x))]!;
    for (let x = 0; x < w; x++) {
      t[row + x] = s / d;
      s +=
        src[row + Math.min(w - 1, x + r + 1)]! - src[row + Math.max(0, x - r)]!;
    }
  }
  for (let x = 0; x < w; x++) {
    let s = 0;
    for (let y = -r; y <= r; y++)
      s += t[Math.min(h - 1, Math.max(0, y)) * w + x]!;
    for (let y = 0; y < h; y++) {
      o[y * w + x] = s / d;
      s +=
        t[Math.min(h - 1, y + r + 1) * w + x]! - t[Math.max(0, y - r) * w + x]!;
    }
  }
  return o;
}

/** Where and how the figures sit: everything their shape depends on. */
export interface Figures {
  /** The canvas's box on screen (CSS px), padded round the figures. */
  left: number;
  top: number;
  width: number;
  height: number;
  /** Ink box centre of the figures, screen px. */
  cx: number;
  cy: number;
  text: string;
  font: (px: number) => string;
  size: number;
  spacing: number;
}

/** The figures drawn white on a canvas the size of their box (device px),
    tabular like the DOM ones: every digit in a cell as wide as a "0". */
function drawFigures(
  b: Figures,
  W: number,
  H: number,
  dpr: number,
): { shape: HTMLCanvasElement; A: Float32Array } {
  const size = b.size * dpr;
  const shape = document.createElement("canvas");
  shape.width = W;
  shape.height = H;
  const sx = shape.getContext("2d", { willReadFrequently: true })!;
  sx.font = b.font(size);
  sx.fillStyle = "#fff";
  sx.textAlign = "center";
  sx.textBaseline = "alphabetic";
  const space = b.spacing * dpr;
  const adv = (ch: string) =>
    /\d/.test(ch) ? sx.measureText("0").width : sx.measureText(ch).width;
  const lines = b.text.split("\n");

  if (lines.length > 1) {
    const lineHeight = size * 0.85;
    const totalHeight = (lines.length - 1) * lineHeight;
    const midY = (b.cy - b.top) * dpr;
    lines.forEach((line, lineIdx) => {
      const lineTotal = [...line].reduce(
        (s, ch) => s + adv(ch) + space,
        -space,
      );
      const ink = sx.measureText(line);
      const lineCenterY = midY - totalHeight / 2 + lineIdx * lineHeight;
      const baseline =
        lineCenterY +
        (ink.actualBoundingBoxAscent - ink.actualBoundingBoxDescent) / 2;
      let pen = (b.cx - b.left) * dpr - lineTotal / 2;
      for (const ch of line) {
        const a = adv(ch);
        sx.fillText(ch, pen + a / 2, baseline);
        pen += a + space;
      }
    });
  } else {
    const total = [...b.text].reduce((s, ch) => s + adv(ch) + space, -space);
    const ink = sx.measureText(b.text);
    const baseline =
      (b.cy - b.top) * dpr +
      (ink.actualBoundingBoxAscent - ink.actualBoundingBoxDescent) / 2;
    let pen = (b.cx - b.left) * dpr - total / 2;
    for (const ch of b.text) {
      const a = adv(ch);
      sx.fillText(ch, pen + a / 2, baseline);
      pen += a + space;
    }
  }
  const raw = sx.getImageData(0, 0, W, H).data;
  const A = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++) A[i] = raw[i * 4 + 3]! / 255;
  return { shape, A };
}

/** A glass look: the numbers shared by the CPU bake below and
    lib/glassDigits.ts's shader, so the two can't drift apart. */
export interface Look {
  /** The rim's width, as a share of the font size. */
  bevel: number;
  /** How far the rim reaches out for what it shows, × the rim's width. */
  bend: number;
  /** Red bent this much more than green, blue this much less. */
  disperse: number;
  /** How sharp the glass sees the photo: its blur, CSS px. */
  blur: number;
  /** The Glass opacity setting × this is how far it's washed to white. */
  milk: number;
  /** A tint's stain: this much at the rim, plus this much inside. */
  stain: readonly [number, number];
  /** How much the rim away from the light darkens. */
  shade: number;
  /** Rim light: on the side facing the light, the side away (its
      reflection), and all round; sharpened by the power. */
  rimLit: number;
  rimBack: number;
  rimAll: number;
  rimPow: number;
  /** A fine specular line along the lit rim. */
  spec: number;
  specPow: number;
  /** The faint colour the glass throws off away from the light. */
  caustic: number;
  /** The glass's shadows: [drop (CSS px), blur (CSS px), alpha]. */
  shadows: readonly (readonly [number, number, number])[];
}

export type LookName = "liquid" | "frosted" | "crystal";

/** After iOS's Liquid Glass: clear in the middle, the bending and the
    light all in a rounded rim. The others vary it. */
const LIQUID: Look = {
  bevel: 0.055,
  bend: 0.75,
  disperse: 0.06,
  blur: 1.2,
  milk: 0.4,
  stain: [0.1, 0.18],
  shade: 0.1,
  rimLit: 0.55,
  rimBack: 0.25,
  rimAll: 0.05,
  rimPow: 3.8,
  spec: 0.32,
  specPow: 80,
  caustic: 0.05,
  shadows: [
    [2, 3, 0.08],
    [10, 24, 0.12],
  ],
};

export const LOOKS: Record<LookName, Look> = {
  liquid: LIQUID,
  /** Ground glass: the photo behind is only colour, the figures always
      read. */
  frosted: {
    ...LIQUID,
    bend: 0.45,
    disperse: 0.02,
    blur: 12,
    milk: 0.75,
    rimLit: 0.45,
    rimBack: 0.2,
    spec: 0.2,
  },
  /** Cut crystal: a wider, brighter rim, more bend and colour split, almost
      nothing in the middle. */
  crystal: {
    ...LIQUID,
    bevel: 0.075,
    bend: 1,
    disperse: 0.14,
    blur: 0.6,
    milk: 0.12,
    rimLit: 0.95,
    rimBack: 0.5,
    rimAll: 0.12,
    rimPow: 2,
    spec: 0.6,
    specPow: 64,
    caustic: 0.08,
    shadows: [
      [2, 3, 0.08],
      [10, 24, 0.1],
    ],
  },
};

/** Squared distance transform along one row or column (Felzenszwalb &
    Huttenlocher), in place over `f` with `n` samples. */
function edt1(
  f: Float64Array,
  n: number,
  d: Float64Array,
  v: Int32Array,
  z: Float64Array,
): void {
  let k = 0;
  v[0] = 0;
  z[0] = -Infinity;
  z[1] = Infinity;
  for (let q = 1; q < n; q++) {
    let s = (f[q]! + q * q - (f[v[k]!]! + v[k]! * v[k]!)) / (2 * q - 2 * v[k]!);
    while (s <= z[k]!) {
      k--;
      s = (f[q]! + q * q - (f[v[k]!]! + v[k]! * v[k]!)) / (2 * q - 2 * v[k]!);
    }
    k++;
    v[k] = q;
    z[k] = s;
    z[k + 1] = Infinity;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    while (z[k + 1]! < q) k++;
    d[q] = (q - v[k]!) * (q - v[k]!) + f[v[k]!]!;
  }
  for (let q = 0; q < n; q++) f[q] = d[q]!;
}

/** Each pixel's distance (px) to the nearest pixel where `seed` is true. */
function distance(
  seed: (i: number) => boolean,
  W: number,
  H: number,
): Float32Array {
  const BIG = 1e12;
  const n = Math.max(W, H);
  const f = new Float64Array(n);
  const d = new Float64Array(n);
  const v = new Int32Array(n);
  const z = new Float64Array(n + 1);
  const g = new Float64Array(W * H);
  for (let i = 0; i < W * H; i++) g[i] = seed(i) ? 0 : BIG;
  for (let x = 0; x < W; x++) {
    for (let y = 0; y < H; y++) f[y] = g[y * W + x]!;
    edt1(f, H, d, v, z);
    for (let y = 0; y < H; y++) g[y * W + x] = f[y]!;
  }
  const out = new Float32Array(W * H);
  for (let y = 0; y < H; y++) {
    const row = y * W;
    for (let x = 0; x < W; x++) f[x] = g[row + x]!;
    edt1(f, W, d, v, z);
    for (let x = 0; x < W; x++) out[row + x] = Math.sqrt(f[x]!);
  }
  return out;
}

/** The glass's surface, from a true distance to the outline (not a blur
    of it, which squares off every corner): across the rim it rises as a
    quarter circle, standing straight up at the outline and level by the
    rim's width in, so the middle stays clear and flat. Returns the rim
    width (device px), the softened coverage for the caustic, and per pixel
    the outward normal's x and y (its z follows) and how far in (0–1). */
function lens(
  A: Float32Array,
  W: number,
  H: number,
  size: number,
  look: Look,
): {
  r: number;
  B: Float32Array;
  nx: Float32Array;
  ny: Float32Array;
  t: Float32Array;
} {
  const r = Math.max(3, size * look.bevel);
  const din = distance((i) => A[i]! < 0.5, W, H);
  const dout = distance((i) => A[i]! >= 0.5, W, H);
  // Signed distance, inside positive, nudged by the anti-aliased coverage
  // and smoothed a little so the pixel grid doesn't step the rim.
  let sd: Float32Array = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++)
    sd[i] = A[i]! >= 0.5 ? din[i]! - 1 + A[i]! : A[i]! - dout[i]!;
  sd = boxBlur(boxBlur(sd, W, H, 2), W, H, 2);
  const nx = new Float32Array(W * H);
  const ny = new Float32Array(W * H);
  const t = new Float32Array(W * H);
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      const k = Math.min(1, Math.max(0, sd[i]! / r));
      t[i] = k;
      const gx = sd[i + 1]! - sd[i - 1]!;
      const gy = sd[i + W]! - sd[i - W]!;
      const gl = Math.hypot(gx, gy);
      if (gl < 1e-6 || k >= 1) continue;
      // Quarter circle: tilt (1 - k) outward, i.e. against the gradient.
      nx[i] = (-gx / gl) * (1 - k);
      ny[i] = (-gy / gl) * (1 - k);
    }
  }
  const b = Math.max(2, Math.round(r * 0.6));
  const B = boxBlur(boxBlur(A, W, H, b), W, H, b);
  return { r, B, nx, ny, t };
}

/** The glass lifted off the photo, just: a contact shadow and a soft one
    below. Each is cast by a copy drawn off the canvas, so only the shadow
    lands. */
function castShadows(
  cx: CanvasRenderingContext2D,
  shape: HTMLCanvasElement,
  W: number,
  H: number,
  dpr: number,
  look: Look,
  darker = 1,
): void {
  const away = W + H;
  for (const [y, blur, alpha] of look.shadows) {
    cx.shadowColor = `rgb(0 0 0 / ${Math.min(1, alpha * darker)})`;
    cx.shadowBlur = blur * dpr;
    cx.shadowOffsetX = away;
    cx.shadowOffsetY = y * dpr;
    cx.drawImage(shape, -away, 0);
  }
  cx.shadowColor = "transparent";
}

/** The glass's shape alone, with no photo in it: what lib/glassDigits.ts
    bends the photos through live. Device px, rows top first.
    `geo`: the outward normal's x and y (0–255 for -1–1), how far in from
    the outline (0–255 across the rim), and the figures' coverage.
    `aux`: the softened coverage (for the caustic) and the shadows' alpha. */
export interface Shape {
  W: number;
  H: number;
  dpr: number;
  /** The rim's width, device px. */
  r: number;
  geo: Uint8Array;
  aux: Uint8Array;
  /** The figures alone, white, for casting shadows. */
  figures: HTMLCanvasElement;
}

export function bakeShape(b: Figures, look: Look): Shape | null {
  const tier = effectiveTier();
  const maxDpr = tier === "lite" ? 1 : 1.5;
  const dpr = Math.min(maxDpr, window.devicePixelRatio || 1);
  const W = Math.round(b.width * dpr);
  const H = Math.round(b.height * dpr);
  if (W < 4 || H < 4) return null;
  const { shape, A } = drawFigures(b, W, H, dpr);
  return shapeOf(shape, A, W, H, dpr, b.size * dpr, look);
}

/** A rounded slab of the same glass (the music card's): `width`×`height`
    CSS px with corner `radius`, centred in a canvas `pad` larger all round
    for its shadows. Its rim is `rim` CSS px in the Liquid look, wider or
    narrower with the others as the figures' is. */
export function bakePanel(
  width: number,
  height: number,
  radius: number,
  rim: number,
  pad: number,
  look: Look,
): Shape | null {
  const tier = effectiveTier();
  const maxDpr = tier === "lite" ? 1 : 1.5;
  const dpr = Math.min(maxDpr, window.devicePixelRatio || 1);
  const W = Math.round((width + pad * 2) * dpr);
  const H = Math.round((height + pad * 2) * dpr);
  if (W < 4 || H < 4) return null;
  const shape = document.createElement("canvas");
  shape.width = W;
  shape.height = H;
  const sx = shape.getContext("2d", { willReadFrequently: true })!;
  sx.fillStyle = "#fff";
  sx.beginPath();
  sx.roundRect(pad * dpr, pad * dpr, width * dpr, height * dpr, radius * dpr);
  sx.fill();
  const raw = sx.getImageData(0, 0, W, H).data;
  const A = new Float32Array(W * H);
  for (let i = 0; i < W * H; i++) A[i] = raw[i * 4 + 3]! / 255;
  return shapeOf(shape, A, W, H, dpr, (rim * dpr) / LIQUID.bevel, look);
}

/** The lens, shadows and packing every glass shape shares. */
function shapeOf(
  shape: HTMLCanvasElement,
  A: Float32Array,
  W: number,
  H: number,
  dpr: number,
  size: number,
  look: Look,
): Shape {
  const { r, B, nx, ny, t } = lens(A, W, H, size, look);

  const shadow = document.createElement("canvas");
  shadow.width = W;
  shadow.height = H;
  const shx = shadow.getContext("2d", { willReadFrequently: true })!;
  castShadows(shx, shape, W, H, dpr, look);
  const sh = shx.getImageData(0, 0, W, H).data;

  const geo = new Uint8Array(W * H * 4);
  const aux = new Uint8Array(W * H * 4);
  for (let i = 0; i < W * H; i++) {
    const p = i * 4;
    aux[p] = B[i]! * 255;
    aux[p + 1] = sh[p + 3]!;
    geo[p] = Math.round(nx[i]! * 127.5 + 127.5);
    geo[p + 1] = Math.round(ny[i]! * 127.5 + 127.5);
    geo[p + 2] = t[i]! * 255;
    geo[p + 3] = A[i]! * 255;
  }
  return { W, H, dpr, r, geo, aux, figures: shape };
}

/** One pixel of glass: the photo seen through it (`sample(dx, dy, ch)`
    reads channel ch, 0–255, that far away in device px), stained, washed
    and lit. The same steps as glassDigits.ts's fragment shader. */
function shadeGlass(
  nx: number,
  ny: number,
  t: number,
  r: number,
  sample: (dx: number, dy: number, ch: number) => number,
  L: [number, number],
  lc: RGB,
  tn: number[] | null,
  milk: number,
  luma: number,
  look: Look,
  out: Uint8ClampedArray,
  p: number,
): void {
  const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
  const bend = r * look.bend;
  const dx = nx * bend;
  const dy = ny * bend;
  const e = look.disperse;
  let cr = sample(dx * (1 + e), dy * (1 + e), 0);
  let cg = sample(dx, dy, 1);
  let cb = sample(dx * (1 - e), dy * (1 - e), 2);
  if (tn) {
    const s = look.stain[0] + look.stain[1] * t;
    cr *= 1 - s + s * tn[0]!;
    cg *= 1 - s + s * tn[1]!;
    cb *= 1 - s + s * tn[2]!;
  }
  const glare = glareOf(luma);
  const gloom = gloomOf(luma);
  const wash = (milk + (0.75 - milk) * gloom * 0.7) * (1 - GLARE.milk * glare);
  const smoke = 1 - GLARE.smoke * glare;
  cr = (cr + (255 - cr) * wash) * smoke;
  cg = (cg + (255 - cg) * wash) * smoke;
  cb = (cb + (255 - cb) * wash) * smoke;
  cr = Math.min(255, cr + (255 - cr) * (0.35 * gloom));
  cg = Math.min(255, cg + (255 - cg) * (0.35 * gloom));
  cb = Math.min(255, cb + (255 - cb) * (0.35 * gloom));

  const facing = nx * L[0] + ny * L[1];
  const edge = Math.pow(1 - nz, look.rimPow);
  const shade =
    1 -
    Math.max(0, -facing) *
      (1 - nz) *
      (look.shade + GLARE.shade * glare) *
      (1 - 0.6 * gloom);
  // The highlight's half vector, light raised a little off the screen.
  const lz = 0.35;
  const ll = Math.hypot(L[0], L[1], lz);
  const hx = L[0] / ll;
  const hy = L[1] / ll;
  const hz = lz / ll + 1;
  const hl = Math.hypot(hx, hy, hz);
  const spec =
    Math.pow(Math.max(0, (nx * hx + ny * hy + nz * hz) / hl), look.specPow) *
    look.spec *
    (1 - t);
  const glow =
    edge *
      (look.rimLit * Math.max(0, facing) +
        look.rimBack * Math.max(0, -facing) +
        look.rimAll) +
    spec;
  out[p] = cr * shade + lc[0] * glow;
  out[p + 1] = cg * shade + lc[1] * glow;
  out[p + 2] = cb * shade + lc[2] * glow;
}

export function bake(b: Bake): boolean {
  const { look } = b;
  const shape = bakeShape(b, look);
  if (!shape) return false;
  const { W, H, dpr, r, geo, aux } = shape;

  // The photo behind, cropped exactly as on screen; frosted glass sees it
  // through a blur, liquid glass nearly sharp.
  const back = document.createElement("canvas");
  back.width = W;
  back.height = H;
  const bx = back.getContext("2d", { willReadFrequently: true })!;
  bx.filter = `blur(${look.blur * dpr}px)`;
  bx.setTransform(
    b.scale * dpr,
    0,
    0,
    b.scale * dpr,
    (b.x - b.left) * dpr,
    (b.y - b.top) * dpr,
  );
  bx.drawImage(b.img, 0, 0);
  let bg: Uint8ClampedArray;
  try {
    bg = bx.getImageData(0, 0, W, H).data;
  } catch {
    return false;
  }

  // The light, as a direction from the figures towards it.
  const lx = b.x + b.light.u * b.img.naturalWidth * b.scale - b.cx;
  const ly = b.y + b.light.v * b.img.naturalHeight * b.scale - b.cy;
  const ll = Math.hypot(lx, ly) || 1;
  const L: [number, number] = [lx / ll, ly / ll];
  const lc = b.light.rgb;
  const tint = b.tint;
  const tmax = tint ? Math.max(...tint) || 1 : 1;
  const tn = tint ? tint.map((c) => c / tmax) : null;
  // The caustic falls away from the light, a rim's width out.
  const off = Math.round(r * 1.4);
  const cdx = Math.round(L[0] * off);
  const cdy = Math.round(L[1] * off);
  const caustic = tint ?? lc;
  const milk = b.milk * look.milk;

  const out = new ImageData(W, H);
  const o = out.data;
  let x = 0;
  let y = 0;
  const sample = (dx: number, dy: number, ch: number) => {
    const rx = (x + dx + 0.5) | 0;
    const ry = (y + dy + 0.5) | 0;
    const clX = rx < 0 ? 0 : rx >= W ? W - 1 : rx;
    const clY = ry < 0 ? 0 : ry >= H ? H - 1 : ry;
    return bg[(clY * W + clX) * 4 + ch]!;
  };
  for (y = 0; y < H; y++) {
    for (x = 0; x < W; x++) {
      const p = (y * W + x) * 4;
      const a = geo[p + 3]! / 255;
      if (a < 0.004) {
        // Outside: only the caustic, if the glass throws one here.
        const sx2 = x + cdx;
        const sy2 = y + cdy;
        if (sx2 < 0 || sy2 < 0 || sx2 >= W || sy2 >= H) continue;
        const c = (aux[(sy2 * W + sx2) * 4]! / 255) * look.caustic;
        if (c < 0.004) continue;
        o[p] = caustic[0];
        o[p + 1] = caustic[1];
        o[p + 2] = caustic[2];
        o[p + 3] = c * 255;
        continue;
      }
      const lumaVal = b.luma ?? b.glare ?? 0.5;
      shadeGlass(
        geo[p]! / 127.5 - 1,
        geo[p + 1]! / 127.5 - 1,
        geo[p + 2]! / 255,
        r,
        sample,
        L,
        lc,
        tn,
        milk,
        lumaVal,
        look,
        o,
        p,
      );
      o[p + 3] = a * 255;
    }
  }
  // The shadows baked in rather than a CSS filter, which would be redrawn
  // on every frame while the photos swipe; the glass goes on top.
  const glass = document.createElement("canvas");
  glass.width = W;
  glass.height = H;
  glass.getContext("2d")!.putImageData(out, 0, 0);
  b.canvas.width = W;
  b.canvas.height = H;
  const cx = b.canvas.getContext("2d")!;
  const lumaVal = b.luma ?? b.glare ?? 0.5;
  const shadowMul = Math.max(
    0.4,
    1 + GLARE.shadow * glareOf(lumaVal) - 0.4 * gloomOf(lumaVal),
  );
  castShadows(cx, shape.figures, W, H, dpr, look, shadowMul);
  cx.drawImage(glass, 0, 0);
  return true;
}
