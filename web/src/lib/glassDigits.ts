// SPDX-License-Identifier: Apache-2.0
/**
 * The Photo Clock's glass figures, drawn live with WebGL so they keep
 * bending whatever is behind them while the photos swipe, fade and drift.
 *
 * lib/glass.ts bakes the whole look on the CPU, photo and all: it's a still
 * of the glass over the photo as it sat, so a moving photo slid under glass
 * that didn't move with it, and the next photo's bake swapped in halfway. Here
 * the costly part that doesn't depend on the photo (the figures' outline,
 * bevel, normals and shadows) is baked once a minute (lib/glass.ts
 * bakeShape), and a fragment shader runs the rest of the same recipe each
 * frame against both photos where they are on screen right then: each pixel
 * of glass bends, stains and is lit by the photo actually under it, so the
 * glass's seam travels with the photos' own.
 */

import { DOME, GLARE, MATTE, type Look, type RGB, type Shape } from "./glass";

/** The minute's melt: how long, and how wide (× the strokes' half-width)
    the bridge of glass that pulls between old and new figures reaches. */
export const MELT_MS = 950;
const NECK = 0.7;
/** The sandblasted tooth's tile, device px (a power of two: it repeats). */
const GRAIN_TILE = 128;

/** In and out with a little give at both ends: the figures draw back a
    touch before they flow, and overshoot a touch before they settle. */
export function liquidEase(t: number): number {
  const c = 0.55 * 1.525;
  return t < 0.5
    ? (Math.pow(2 * t, 2) * ((c + 1) * 2 * t - c)) / 2
    : (Math.pow(2 * t - 2, 2) * ((c + 1) * (t * 2 - 2) + c) + 2) / 2;
}

/** One photo slot, as it is on screen this frame. */
export interface SlotView {
  /** 0–1: the slot's opacity, 0 when it has no photo. */
  on: number;
  /** Screen (CSS px, relative to the clock) → the slot's photo texture's
      0–1 coordinates, as a column-major 3×3 affine matrix. */
  toUv: Float32Array;
  /** Unit direction from the figures towards the photo's light. */
  light: [number, number];
  lightRgb: RGB;
  tint: RGB | null;
  /** 0–1: how bright the photo is behind the glass (lib/glass.ts
      Bake.glare). */
  glare: number;
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

const VERT = `
attribute vec2 aCorner;
varying vec2 vUv;
void main() {
  vUv = vec2(aCorner.x * 0.5 + 0.5, 0.5 - aCorner.y * 0.5);
  gl_Position = vec4(aCorner, 0.0, 1.0);
}`;

const FRAG = `
#define GLARE_MILK ${GLARE.milk.toFixed(3)}
#define GLARE_SMOKE ${GLARE.smoke.toFixed(3)}
#define GLARE_SHADE ${GLARE.shade.toFixed(3)}
#define GLARE_SHADOW ${GLARE.shadow.toFixed(3)}
#define DOME_POW ${DOME.pow.toFixed(3)}
#define DOME_RIM ${DOME.rimKeep.toFixed(3)}
#define NECK ${NECK.toFixed(3)}
#define MATTE_SAT ${MATTE.saturate.toFixed(3)}
#define MATTE_GLOOM_VEIL ${MATTE.gloomVeil.toFixed(3)}
#define MATTE_GLOOM_MIX ${MATTE.gloomMix.toFixed(3)}
#define MATTE_GLARE ${MATTE.glare.toFixed(3)}
#define MATTE_GRAIN ${MATTE.grain.toFixed(3)}
#define MATTE_EDGE ${MATTE.edge.toFixed(3)}
#define GRAIN_TILE ${GRAIN_TILE.toFixed(1)}
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
varying vec2 vUv;
uniform sampler2D uGeo;
uniform sampler2D uAux;
uniform sampler2D uPhoto0;
uniform sampler2D uPhoto1;
uniform vec2 uOrigin;
uniform vec2 uBoxSize;
uniform vec2 uTexel;
uniform float uBend;
uniform float uOff;
uniform float uMilk;
uniform mat3 uM0;
uniform mat3 uM1;
uniform float uOn0;
uniform float uOn1;
uniform vec2 uL0;
uniform vec2 uL1;
uniform vec3 uLc0;
uniform vec3 uLc1;
uniform vec3 uT0;
uniform vec3 uT1;
uniform float uH0;
uniform float uH1;
uniform vec3 uC0;
uniform vec3 uC1;
uniform float uG0;
uniform float uG1;
// The look (lib/glass.ts Look): rim lit, back, all, power; spec, power;
// stain at the rim, inside; disperse, shade, caustic.
uniform vec4 uRim;
uniform vec2 uSpec;
uniform vec2 uStain;
uniform vec3 uMisc;
// The share of the shape's width and height on screen (1: all of it).
// Less, and each half is read from the shape's own end, the middle left
// out: a slab baked once at its widest and tallest draws at any smaller
// size, its straight sides being the same all the way along.
uniform vec2 uSlice;
// The lens beyond the rim (lib/glass.ts Look dome, magnify, gloss): the
// magnifying's reach (CSS px), the dome and its gloss.
uniform float uMagPx;
uniform float uDome;
uniform float uGloss;
// A melt (WebGL2 only): the old and new figures' distance fields (device
// px) and the old shape's aux; how far it's got (uK, eased, may overshoot)
// and its swell (uEnv, 0 at both ends); the new box's 0–1 → the old's;
// the changing figures' rect (0–1) and its feather; the rim's width and
// the strokes' half-width, device px.
uniform sampler2D uField;
uniform sampler2D uFieldOld;
uniform sampler2D uAuxOld;
uniform float uMelt;
uniform float uK;
uniform float uEnv;
uniform vec4 uOldXf;
uniform vec4 uGate;
uniform vec2 uFeather;
uniform float uRimPx;
uniform float uHalf;
// Sandblasted (lib/glass.ts Look.matte), and its tooth: a tiling grain (r)
// and which way each grain scatters (g, b).
uniform float uMatte;
uniform sampler2D uGrain;

float slice(float t, float s) {
  t *= s;
  return t > s * 0.5 ? t + 1.0 - s : t;
}

vec2 at(vec2 uv) {
  return vec2(slice(uv.x, uSlice.x), slice(uv.y, uSlice.y));
}

float inside(vec2 uv) {
  return step(0.0, uv.x) * step(uv.x, 1.0) * step(0.0, uv.y) * step(uv.y, 1.0);
}

// How much of each slot shows at p (slot 1 is drawn over slot 0).
vec2 weights(vec2 p, out vec2 a, out vec2 b) {
  a = (uM0 * vec3(p, 1.0)).xy;
  b = (uM1 * vec3(p, 1.0)).xy;
  float w1 = inside(b) * uOn1;
  return vec2(inside(a) * uOn0 * (1.0 - w1), w1);
}

vec2 oldUv(vec2 uv) {
  return uv * uOldXf.xy + uOldXf.zw;
}

// The surface mid-melt: the two distances blended, plus a bridge of glass
// where they're close, the way a liquid pulls between two drops.
float field(vec2 uv, float env) {
  float a = texture2D(uFieldOld, oldUv(uv)).r;
  float b = texture2D(uField, uv).r;
  float s = max(1.0, NECK * uHalf);
  float h = max(s - abs(a - b), 0.0) / s;
  return mix(a, b, uK) + h * h * s * 0.25 * env;
}

// lib/glass.ts tiltAt().
float tiltAt(float sd) {
  float rim = 1.0 - clamp(sd / uRimPx, 0.0, 1.0);
  if (uDome <= 0.0) return rim;
  float body = pow(1.0 - clamp(sd / uHalf, 0.0, 1.0), DOME_POW) * uDome;
  return 1.0 - (1.0 - rim * DOME_RIM) * (1.0 - body);
}

void main() {
  vec2 p = uOrigin + vUv * uBoxSize;
  vec2 uv = at(vUv);
  vec4 g = texture2D(uGeo, uv);
  vec4 x = texture2D(uAux, uv);
  float a = g.a;

  // The light, stain and caustic of the photo under this pixel.
  vec2 pa;
  vec2 pb;
  vec2 w = weights(p, pa, pb);
  float k = w.x + w.y > 0.001 ? w.y / (w.x + w.y) : uOn1;
  vec2 L = normalize(mix(uL0, uL1, k) + vec2(1e-5, 0.0));
  vec3 lc = mix(uLc0, uLc1, k);
  vec3 tn = mix(uT0, uT1, k);
  float has = mix(uH0, uH1, k);
  float luma = mix(uG0, uG1, k);
  float glare = clamp((luma - 0.45) / 0.35, 0.0, 1.0);
  glare = glare * glare * (3.0 - 2.0 * glare);
  float gloom = clamp((0.45 - luma) / 0.35, 0.0, 1.0);
  gloom = gloom * gloom * (3.0 - 2.0 * gloom);

  // The glass here: coverage, the outward slope, how far in across the
  // rim, how far from the spine, and its shadow and caustic. Baked, or
  // mid-melt, built from the two fields.
  vec2 n = g.xy * 2.0 - 1.0;
  float t = g.z;
  float m = x.b;
  float shadow = x.g;
  vec2 co = L * uOff * uTexel;
  float caus = texture2D(uAux, uv + co).r;
  float swell = 0.0;
  if (uMelt > 0.5) {
    // Only the figures that change swell; the rest stay put.
    vec2 gi = smoothstep(uGate.xy - uFeather, uGate.xy, vUv)
            * (1.0 - smoothstep(uGate.zw, uGate.zw + uFeather, vUv));
    swell = uEnv * gi.x * gi.y;
    float sd = field(vUv, swell);
    a = clamp(sd + 0.5, 0.0, 1.0);
    // Mid-melt the blend carries both shapes' spines and seams; a wider
    // footprint for the slope smooths them into one surface, narrowing
    // back to the crisp outline as the figures settle.
    vec2 e = uTexel * mix(1.5, max(1.5, uHalf * 0.45), swell);
    vec2 gr = vec2(field(vUv + vec2(e.x, 0.0), swell) - field(vUv - vec2(e.x, 0.0), swell),
                   field(vUv + vec2(0.0, e.y), swell) - field(vUv - vec2(0.0, e.y), swell));
    n = -gr / max(length(gr), 1e-5) * tiltAt(sd);
    t = clamp(sd / uRimPx, 0.0, 1.0);
    m = sd > -0.5 ? clamp((uHalf - sd) / uHalf, 0.0, 1.0) : 0.0;
    float kc = clamp(uK, 0.0, 1.0);
    vec2 ou = oldUv(vUv);
    shadow = mix(texture2D(uAuxOld, ou).g, x.g, kc);
    caus = mix(texture2D(uAuxOld, ou + co).r, caus, kc);
  }

  vec4 col;
  if (a < 0.004) {
    // Outside: only the caustic the glass throws away from the light.
    float c = caus * uMisc.z;
    col = vec4(mix(uC0, uC1, k) * c, c);
  } else if (uMatte > 0.5) {
    // Sandblasted, the same steps as lib/glass.ts shadeGlass(): matte and
    // even to the edge, no lens and no shine. Each grain sees the blurred
    // photo a pixel to one side; the colour comes back a little before a
    // white veil, lighter over a dark photo; a fine tooth, and the cut
    // edge a hair lighter.
    vec4 gr = texture2D(uGrain, gl_FragCoord.xy / GRAIN_TILE);
    vec2 qa;
    vec2 qb;
    vec2 wq = weights(p + gr.gb * 2.0 - 1.0, qa, qb);
    vec3 c = vec3(0.0);
    if (wq.x > 0.0) c += texture2D(uPhoto0, qa).rgb * wq.x;
    if (wq.y > 0.0) c += texture2D(uPhoto1, qb).rgb * wq.y;
    float s = has * (uStain.x + uStain.y);
    c *= 1.0 - s + s * tn;
    float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
    c = clamp(mix(vec3(lum), c, MATTE_SAT), 0.0, 1.0);
    float veil = uMilk + (MATTE_GLOOM_VEIL - uMilk) * gloom * MATTE_GLOOM_MIX;
    c = mix(c, vec3(1.0), veil) * (1.0 - MATTE_GLARE * glare);
    c += (gr.r - 0.5) * MATTE_GRAIN + (1.0 - smoothstep(0.0, 0.5, t)) * MATTE_EDGE;
    col = vec4(clamp(c, 0.0, 1.0) * a, a);
  } else {
    // The same steps as lib/glass.ts shadeGlass().
    float nz = sqrt(max(0.0, 1.0 - dot(n, n)));
    // The rim reaches outward for what it shows, red a touch further and
    // blue a touch short; the thick middle magnifies, reading from nearer
    // the spine. One lookup of where that lands in each photo (the
    // matrices are affine, so the spread maps through their linear part),
    // and a photo is only read where it shows.
    float tl = length(n);
    vec2 d = n * uBend * (1.0 + 0.6 * swell);
    if (tl > 0.001) d -= n / tl * uMagPx * m;
    vec2 qa;
    vec2 qb;
    vec2 wq = weights(p + d, qa, qb);
    vec3 c = vec3(0.0);
    if (wq.x > 0.0) {
      vec2 e = mat2(uM0[0].xy, uM0[1].xy) * d * uMisc.x;
      c += vec3(texture2D(uPhoto0, qa + e).r, texture2D(uPhoto0, qa).g,
                texture2D(uPhoto0, qa - e).b) * wq.x;
    }
    if (wq.y > 0.0) {
      vec2 e = mat2(uM1[0].xy, uM1[1].xy) * d * uMisc.x;
      c += vec3(texture2D(uPhoto1, qb + e).r, texture2D(uPhoto1, qb).g,
                texture2D(uPhoto1, qb - e).b) * wq.y;
    }
    float s = has * (uStain.x + uStain.y * t);
    c *= 1.0 - s + s * tn;
    // Over a bright photo, white glass vanishes: less milk, and smoke.
    // Over a dark photo, white glass is luminous and visible: milk boost & ambient lift.
    float wash = (uMilk + (0.75 - uMilk) * gloom * 0.7) * (1.0 - GLARE_MILK * glare);
    float smoke = 1.0 - GLARE_SMOKE * glare;
    c = (c + (1.0 - c) * wash) * smoke;
    c = min(vec3(1.0), c + (1.0 - c) * (0.35 * gloom));

    float facing = dot(n, L);
    float edge = pow(1.0 - nz, uRim.w);
    float shade = 1.0 - max(0.0, -facing) * (1.0 - nz)
                      * (uMisc.y + GLARE_SHADE * glare) * (1.0 - 0.6 * gloom);
    vec3 H3 = normalize(normalize(vec3(L, 0.35)) + vec3(0.0, 0.0, 1.0));
    float ndh = max(0.0, dot(vec3(n, nz), H3));
    float spec = pow(ndh, uSpec.y) * uSpec.x * (1.0 - t)
               + pow(ndh, 14.0) * uGloss * min(1.0, tl / 0.25);
    float glow = edge * (uRim.x * max(0.0, facing)
                       + uRim.y * max(0.0, -facing)
                       + uRim.z) + spec;
    c = min(c * shade + lc * glow, 1.0);
    col = vec4(c * a, a);
  }
  // The shadows lie under it all.
  float sh = min(1.0, shadow * (1.0 + GLARE_SHADOW * glare) * (1.0 - 0.4 * gloom));
  gl_FragColor = col + vec4(0.0, 0.0, 0.0, sh) * (1.0 - col.a);
}`;

const UNIFORMS = [
  "uGeo",
  "uAux",
  "uPhoto0",
  "uPhoto1",
  "uOrigin",
  "uBoxSize",
  "uTexel",
  "uBend",
  "uOff",
  "uMilk",
  "uM0",
  "uM1",
  "uOn0",
  "uOn1",
  "uL0",
  "uL1",
  "uLc0",
  "uLc1",
  "uT0",
  "uT1",
  "uH0",
  "uH1",
  "uC0",
  "uC1",
  "uG0",
  "uG1",
  "uRim",
  "uSpec",
  "uStain",
  "uMisc",
  "uSlice",
  "uMagPx",
  "uDome",
  "uGloss",
  "uField",
  "uFieldOld",
  "uAuxOld",
  "uMelt",
  "uK",
  "uEnv",
  "uOldXf",
  "uGate",
  "uFeather",
  "uRimPx",
  "uHalf",
  "uMatte",
  "uGrain",
] as const;

/** Texture units: the shape's geo and aux, the two photos, then for a
    melt the new and old figures' fields and the old shape's aux. */
const FIELD = 4;
const FIELD_OLD = 5;
const AUX_OLD = 6;
const GRAIN = 7;

/** The tooth: fine grain, and a smoother bump whose slope says which way
    each grain scatters. Seeded, so every screen and minute has the same. */
function grainTile(): Uint8Array {
  const N = GRAIN_TILE;
  let seed = 0x9e3779b9;
  const rnd = (): number => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const white = Float32Array.from({ length: N * N }, rnd);
  const at = (x: number, y: number): number =>
    white[((y + N) % N) * N + ((x + N) % N)]!;
  const blur =
    (r: number) =>
    (x: number, y: number): number => {
      let s = 0;
      for (let dy = -r; dy <= r; dy++)
        for (let dx = -r; dx <= r; dx++) s += at(x + dx, y + dy);
      return s / (2 * r + 1) ** 2;
    };
  const fine = blur(1);
  const bump = blur(2);
  const out = new Uint8Array(N * N * 4);
  const clamp = (v: number): number => Math.min(255, Math.max(0, v));
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const i = (y * N + x) * 4;
      // A 3×3 mean of uniform noise spans about ±0.29 round 0.5.
      out[i] = clamp(128 + (fine(x, y) - 0.5) * 440);
      out[i + 1] = clamp(128 + (bump(x + 1, y) - bump(x - 1, y)) * 1500);
      out[i + 2] = clamp(128 + (bump(x, y + 1) - bump(x, y - 1)) * 1500);
      out[i + 3] = 255;
    }
  }
  return out;
}

/** The photo as slot `i` shows it (object-fit cover at `pos`, in a
    `width`×`height` box), blurred like the glass sees it, as a canvas
    `res` times the box's size. */
export function coverCrop(
  img: HTMLImageElement,
  width: number,
  height: number,
  pos: [number, number],
  blur: number,
  res: number,
): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(width * res));
  c.height = Math.max(1, Math.round(height * res));
  const ctx = c.getContext("2d");
  if (!ctx) return c;
  const scale = Math.max(width / img.naturalWidth, height / img.naturalHeight);
  const x = (width - img.naturalWidth * scale) * pos[0];
  const y = (height - img.naturalHeight * scale) * pos[1];
  ctx.filter = `blur(${blur * res}px)`;
  ctx.setTransform(scale * res, 0, 0, scale * res, x * res, y * res);
  ctx.drawImage(img, 0, 0);
  return c;
}

export class GlassDigits {
  private gl: WebGLRenderingContext;
  /** WebGL2, which can sample a float field smoothly: the figures melt
      from one minute into the next. Without it they crossfade. */
  private gl2: WebGL2RenderingContext | null;
  private prog: WebGLProgram;
  private loc: Record<string, WebGLUniformLocation | null> = {};
  /** One per texture unit (see FIELD), each bound to its unit; a melt
      swaps the old shape's into the old units. */
  private tex: WebGLTexture[];
  private shape: Shape | null = null;
  private melt: {
    start: number;
    xf: [number, number, number, number];
    gate: [number, number, number, number];
    feather: [number, number];
  } | null = null;

  /** null when the browser has no WebGL; the caller bakes on the CPU. */
  static create(canvas: HTMLCanvasElement): GlassDigits | null {
    const opts: WebGLContextAttributes = {
      premultipliedAlpha: true,
      antialias: false,
      alpha: true,
      depth: false,
      stencil: false,
    };
    const gl =
      canvas.getContext("webgl2", opts) ?? canvas.getContext("webgl", opts);
    if (!gl) return null;
    try {
      return new GlassDigits(gl);
    } catch {
      return null;
    }
  }

  private constructor(gl: WebGLRenderingContext | WebGL2RenderingContext) {
    this.gl = gl as WebGLRenderingContext;
    this.gl2 =
      typeof WebGL2RenderingContext !== "undefined" &&
      gl instanceof WebGL2RenderingContext
        ? gl
        : null;
    const compile = (type: number, src: string): WebGLShader => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
        throw new Error(gl.getShaderInfoLog(s) ?? "shader");
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(prog) ?? "link");
    this.prog = prog;
    gl.useProgram(prog);
    for (const name of UNIFORMS)
      this.loc[name] = gl.getUniformLocation(prog, name);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const at = gl.getAttribLocation(prog, "aCorner");
    gl.enableVertexAttribArray(at);
    gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0);

    this.tex = [0, 1, 2, 3, FIELD, FIELD_OLD, AUX_OLD, GRAIN].map((unit) => {
      const t = gl.createTexture()!;
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, t);
      // The shape is sampled texel for texel; the photos and the fields
      // smoothly.
      const smooth =
        unit === 2 || unit === 3 || unit === FIELD || unit === FIELD_OLD;
      const filter = smooth ? gl.LINEAR : gl.NEAREST;
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
      const wrap = unit === GRAIN ? gl.REPEAT : gl.CLAMP_TO_EDGE;
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
      const gl2 = this.gl2;
      if (gl2 && (unit === FIELD || unit === FIELD_OLD))
        gl2.texImage2D(
          gl2.TEXTURE_2D,
          0,
          gl2.R16F,
          1,
          1,
          0,
          gl2.RED,
          gl2.FLOAT,
          new Float32Array([0]),
        );
      else
        gl.texImage2D(
          gl.TEXTURE_2D,
          0,
          gl.RGBA,
          1,
          1,
          0,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          new Uint8Array([0, 0, 0, 0]),
        );
      return t;
    });
    gl.activeTexture(gl.TEXTURE0 + GRAIN);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.RGBA,
      GRAIN_TILE,
      GRAIN_TILE,
      0,
      gl.RGBA,
      gl.UNSIGNED_BYTE,
      grainTile(),
    );
    for (const [name, unit] of [
      ["uGeo", 0],
      ["uAux", 1],
      ["uPhoto0", 2],
      ["uPhoto1", 3],
      ["uField", FIELD],
      ["uFieldOld", FIELD_OLD],
      ["uAuxOld", AUX_OLD],
      ["uGrain", GRAIN],
    ] as const)
      gl.uniform1i(this.loc[name]!, unit);
    gl.disable(gl.BLEND);
  }

  get ready(): boolean {
    return this.shape !== null;
  }

  /** The figures' shape (a minute's worth); sizes the canvas to it. Given
      `melt` (the old and new figures' boxes, CSS px), the old figures
      melt into these over MELT_MS, as draw() is called each frame; true if
      they will. They can only where the new box holds the old one. */
  setShape(
    canvas: HTMLCanvasElement,
    shape: Shape,
    melt?: { from: Box; to: Box },
  ): boolean {
    const gl = this.gl;
    const was = this.shape;
    this.melt = null;
    const melting =
      !!melt &&
      !!this.gl2 &&
      !!was?.field &&
      !!shape.field &&
      this.beginMelt(was, shape, melt.from, melt.to);
    if (melting) {
      // The old shape's field and aux move to the old units as they are.
      this.swap(FIELD, FIELD_OLD);
      this.swap(1, AUX_OLD);
    }
    this.shape = shape;
    if (canvas.width !== shape.W || canvas.height !== shape.H) {
      canvas.width = shape.W;
      canvas.height = shape.H;
    }
    gl.viewport(0, 0, shape.W, shape.H);
    for (const [unit, data] of [
      [0, shape.geo],
      [1, shape.aux],
    ] as const) {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, this.tex[unit]!);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        shape.W,
        shape.H,
        0,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        data,
      );
    }
    const gl2 = this.gl2;
    if (gl2 && shape.field) {
      gl2.activeTexture(gl2.TEXTURE0 + FIELD);
      gl2.bindTexture(gl2.TEXTURE_2D, this.tex[FIELD]!);
      gl2.texImage2D(
        gl2.TEXTURE_2D,
        0,
        gl2.R16F,
        shape.W,
        shape.H,
        0,
        gl2.RED,
        gl2.FLOAT,
        shape.field,
      );
    }
    return melting;
  }

  /** A melt from `a` in box `from` to `b` in box `to`: where the old
      figures sit in the new box, and which of them change. */
  private beginMelt(a: Shape, b: Shape, from: Box, to: Box): boolean {
    if (!this.canMelt(from, to)) return false;
    const xf: [number, number, number, number] = [
      to.width / from.width,
      to.height / from.height,
      (to.left - from.left) / from.width,
      (to.top - from.top) / from.height,
    ];
    // The changing figures: where the two fields differ, every other px.
    const fa = a.field!;
    const fb = b.field!;
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (let y = 0; y < b.H; y += 2) {
      const v = ((y + 0.5) / b.H) * xf[1] + xf[3];
      const ay = Math.min(a.H - 1, Math.max(0, Math.floor(v * a.H)));
      for (let x = 0; x < b.W; x += 2) {
        const u = ((x + 0.5) / b.W) * xf[0] + xf[2];
        const ax = Math.min(a.W - 1, Math.max(0, Math.floor(u * a.W)));
        if (Math.abs(fa[ay * a.W + ax]! - fb[y * b.W + x]!) < 1) continue;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
    if (x1 < x0) return false;
    const pad = b.half * 2;
    this.melt = {
      start: performance.now(),
      xf,
      gate: [
        (x0 - pad) / b.W,
        (y0 - pad) / b.H,
        (x1 + pad) / b.W,
        (y1 + pad) / b.H,
      ],
      feather: [pad / b.W, pad / b.H],
    };
    return true;
  }

  private swap(i: number, j: number): void {
    const gl = this.gl;
    [this.tex[i], this.tex[j]] = [this.tex[j]!, this.tex[i]!];
    for (const unit of [i, j]) {
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, this.tex[unit]!);
    }
  }

  /** The figures in box `from` could melt into new ones in `to`: WebGL2,
      a field for them, and the new box holding the old. */
  canMelt(from: Box, to: Box): boolean {
    return (
      !!this.gl2 &&
      !!this.shape?.field &&
      from.left >= to.left - 1 &&
      from.top >= to.top - 1 &&
      from.left + from.width <= to.left + to.width + 1 &&
      from.top + from.height <= to.top + to.height + 1
    );
  }

  /** The figures are melting: keep drawing every frame. */
  get melting(): boolean {
    return this.melt !== null;
  }

  /** What slot 0 or 1's glass bends: its photo as coverCrop() made it. */
  setPhoto(slot: 0 | 1, source: TexImageSource): void {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE2 + slot);
    gl.bindTexture(gl.TEXTURE_2D, this.tex[2 + slot]!);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  }

  /** One frame: the glass in `box` (CSS px) over the slots as they are.
      A `box` smaller than the shape (a slab mid-resize) is drawn sliced,
      into the canvas's bottom left; the rest is cleared. */
  draw(box: Box, look: Look, milk: number, slots: [SlotView, SlotView]): void {
    const shape = this.shape;
    if (!shape) return;
    const gl = this.gl;
    const u = this.loc;
    gl.useProgram(this.prog);
    const shown = Math.min(shape.H, Math.round(box.height * shape.dpr));
    const wide = Math.min(shape.W, Math.round(box.width * shape.dpr));
    if (shown < shape.H || wide < shape.W) {
      gl.viewport(0, 0, shape.W, shape.H);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.viewport(0, 0, wide, shown);
    gl.uniform2f(u.uSlice!, wide / shape.W, shown / shape.H);
    gl.uniform2f(u.uOrigin!, box.left, box.top);
    gl.uniform2f(u.uBoxSize!, box.width, box.height);
    gl.uniform2f(u.uTexel!, 1 / shape.W, 1 / shape.H);
    gl.uniform1f(u.uBend!, (shape.r * look.bend) / shape.dpr);
    gl.uniform1f(u.uOff!, Math.round(shape.r * 1.4));
    gl.uniform1f(u.uMilk!, milk * look.milk);
    gl.uniform4f(u.uRim!, look.rimLit, look.rimBack, look.rimAll, look.rimPow);
    gl.uniform2f(u.uSpec!, look.spec, look.specPow);
    gl.uniform2f(u.uStain!, look.stain[0], look.stain[1]);
    gl.uniform3f(u.uMisc!, look.disperse, look.shade, look.caustic);
    // The lens beyond the rim is the figures' (a slab has no field).
    const figures = shape.field !== null;
    gl.uniform1f(
      u.uMagPx!,
      figures ? (look.magnify * shape.half) / shape.dpr : 0,
    );
    gl.uniform1f(u.uDome!, figures ? look.dome : 0);
    gl.uniform1f(u.uGloss!, figures ? look.gloss : 0);
    gl.uniform1f(u.uMatte!, look.matte ? 1 : 0);
    gl.uniform1f(u.uRimPx!, shape.r);
    gl.uniform1f(u.uHalf!, shape.half);
    const mt = this.melt;
    const t = mt ? Math.min(1, (performance.now() - mt.start) / MELT_MS) : 1;
    if (mt && t < 1) {
      gl.uniform1f(u.uMelt!, 1);
      gl.uniform1f(u.uK!, liquidEase(t));
      gl.uniform1f(u.uEnv!, Math.sin(Math.PI * t));
      gl.uniform4f(u.uOldXf!, ...mt.xf);
      gl.uniform4f(u.uGate!, ...mt.gate);
      gl.uniform2f(u.uFeather!, ...mt.feather);
    } else {
      this.melt = null;
      gl.uniform1f(u.uMelt!, 0);
    }
    slots.forEach((s, i) => {
      gl.uniformMatrix3fv(u[`uM${i}`]!, false, s.toUv);
      gl.uniform1f(u[`uOn${i}`]!, s.on);
      gl.uniform2f(u[`uL${i}`]!, s.light[0], s.light[1]);
      gl.uniform3f(
        u[`uLc${i}`]!,
        s.lightRgb[0] / 255,
        s.lightRgb[1] / 255,
        s.lightRgb[2] / 255,
      );
      const t = s.tint;
      const top = t ? Math.max(...t) || 1 : 1;
      gl.uniform3f(
        u[`uT${i}`]!,
        t ? t[0] / top : 1,
        t ? t[1] / top : 1,
        t ? t[2] / top : 1,
      );
      gl.uniform1f(u[`uH${i}`]!, t ? 1 : 0);
      // The caustic is the stain's colour, or the light's through clear glass.
      const c = t ?? s.lightRgb;
      gl.uniform3f(u[`uC${i}`]!, c[0] / 255, c[1] / 255, c[2] / 255);
      gl.uniform1f(u[`uG${i}`]!, s.glare);
    });
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  dispose(): void {
    const gl = this.gl;
    for (const t of this.tex) gl.deleteTexture(t);
    gl.deleteProgram(this.prog);
    this.shape = null;
  }
}
