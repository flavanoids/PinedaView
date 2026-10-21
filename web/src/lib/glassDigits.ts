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

import { GLARE, type Look, type RGB, type Shape } from "./glass";

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
// The share of the shape's height on screen (1: all of it). Less, and the
// top half and bottom half are read from the shape's two ends, the middle
// left out: a slab baked once at its tallest draws at any shorter height,
// its straight sides being the same all the way down.
uniform float uSlice;

vec2 at(vec2 uv) {
  float v = uv.y * uSlice;
  return vec2(uv.x, v > uSlice * 0.5 ? v + 1.0 - uSlice : v);
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

  vec4 col;
  if (a < 0.004) {
    // Outside: only the caustic the glass throws away from the light.
    float c = texture2D(uAux, uv + L * uOff * uTexel).r * uMisc.z;
    col = vec4(mix(uC0, uC1, k) * c, c);
  } else {
    // The same steps as lib/glass.ts shadeGlass().
    vec2 n = g.xy * 2.0 - 1.0;
    float nz = sqrt(max(0.0, 1.0 - dot(n, n)));
    float t = g.z;
    // The rim reaches outward for what it shows, red a touch further and
    // blue a touch short. One lookup of where that lands in each photo
    // (the matrices are affine, so the spread maps through their linear
    // part), and a photo is only read where it shows.
    vec2 d = n * uBend;
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
    float spec = pow(max(0.0, dot(vec3(n, nz), H3)), uSpec.y)
               * uSpec.x * (1.0 - t);
    float glow = edge * (uRim.x * max(0.0, facing)
                       + uRim.y * max(0.0, -facing)
                       + uRim.z) + spec;
    c = min(c * shade + lc * glow, 1.0);
    col = vec4(c * a, a);
  }
  // The shadows lie under it all.
  float sh = min(1.0, x.g * (1.0 + GLARE_SHADOW * glare) * (1.0 - 0.4 * gloom));
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
] as const;

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
  private prog: WebGLProgram;
  private loc: Record<string, WebGLUniformLocation | null> = {};
  /** geo, aux, photo 0, photo 1 — bound to units 0–3 for good. */
  private tex: WebGLTexture[];
  private shape: Shape | null = null;

  /** null when the browser has no WebGL; the caller bakes on the CPU. */
  static create(canvas: HTMLCanvasElement): GlassDigits | null {
    const gl = canvas.getContext("webgl", {
      premultipliedAlpha: true,
      antialias: false,
      alpha: true,
      depth: false,
      stencil: false,
    });
    if (!gl) return null;
    try {
      return new GlassDigits(gl);
    } catch {
      return null;
    }
  }

  private constructor(gl: WebGLRenderingContext) {
    this.gl = gl;
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

    this.tex = [0, 1, 2, 3].map((unit) => {
      const t = gl.createTexture()!;
      gl.activeTexture(gl.TEXTURE0 + unit);
      gl.bindTexture(gl.TEXTURE_2D, t);
      // The shape is sampled texel for texel; the photos smoothly.
      const filter = unit < 2 ? gl.NEAREST : gl.LINEAR;
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
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
      gl.uniform1i(this.loc[UNIFORMS[unit]!]!, unit);
      return t;
    });
    gl.disable(gl.BLEND);
  }

  get ready(): boolean {
    return this.shape !== null;
  }

  /** The figures' shape (a minute's worth); sizes the canvas to it. */
  setShape(canvas: HTMLCanvasElement, shape: Shape): void {
    const gl = this.gl;
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
  }

  /** What slot 0 or 1's glass bends: its photo as coverCrop() made it. */
  setPhoto(slot: 0 | 1, source: TexImageSource): void {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE2 + slot);
    gl.bindTexture(gl.TEXTURE_2D, this.tex[2 + slot]!);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  }

  /** One frame: the glass in `box` (CSS px) over the slots as they are.
      A `box` shorter than the shape (a slab mid-resize) is drawn sliced,
      into the bottom of the canvas; the rest is cleared. */
  draw(box: Box, look: Look, milk: number, slots: [SlotView, SlotView]): void {
    const shape = this.shape;
    if (!shape) return;
    const gl = this.gl;
    const u = this.loc;
    gl.useProgram(this.prog);
    const shown = Math.min(shape.H, Math.round(box.height * shape.dpr));
    if (shown < shape.H) {
      gl.viewport(0, 0, shape.W, shape.H);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
    }
    gl.viewport(0, 0, shape.W, shown);
    gl.uniform1f(u.uSlice!, shown / shape.H);
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
