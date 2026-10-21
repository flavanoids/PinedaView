// SPDX-License-Identifier: Apache-2.0
/**
 * Liquid glass clock hands for the round Photo Clock, drawn live with WebGL.
 *
 * The figures' glass (lib/glass.ts) is baked on the CPU once a minute; a
 * hand that turns can't be, since what it bends changes as it moves. So the
 * same recipe runs as a fragment shader: each hand is a rounded rod (a
 * capsule's distance field), its height falls off over a bevel to the
 * outline, and the slope bends the photo behind it — red a touch more than
 * blue — lights the side facing the photo's own light in that light's
 * colour, rims the outline and darkens the far edge. A tint stains it,
 * deeper where it's thicker, and milk whitens it. Two soft shadows lift it
 * off the photo.
 *
 * Only a strip round each hand is drawn (one quad per hand, rotated in the
 * vertex shader), so a frame costs a few hundred thousand pixels, not the
 * whole disc.
 */

export type RGB = [number, number, number];

export interface Hand {
  /** Clockwise from 12, in radians. */
  angle: number;
  /** Centre to tip, and centre back to the tail's end (CSS px). */
  length: number;
  tail: number;
  /** Half the rod's thickness (CSS px). */
  radius: number;
}

export interface Look {
  flat: boolean;
  /** 0–1: how milky the glass is (the Glass opacity setting). */
  milk: number;
  tint: RGB | null;
  /** Unit direction from the centre towards the photo's light. */
  light: [number, number];
  lightRgb: RGB;
}

const VERT = `
attribute vec2 aCorner;
uniform vec2 uA;
uniform vec2 uB;
uniform float uR;
uniform float uPad;
uniform vec2 uSize;
varying vec2 vP;
void main() {
  vec2 d = uB - uA;
  float len = length(d);
  vec2 ax = len > 0.0 ? d / len : vec2(1.0, 0.0);
  vec2 nr = vec2(-ax.y, ax.x);
  vec2 mid = (uA + uB) * 0.5;
  vec2 p = mid + ax * aCorner.x * (len * 0.5 + uR + uPad)
               + nr * aCorner.y * (uR + uPad);
  vP = p;
  vec2 clip = p / uSize * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
}`;

const FRAG = `
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
varying vec2 vP;
uniform vec2 uA;
uniform vec2 uB;
uniform float uR;
uniform vec2 uSize;
uniform float uK;
uniform float uDpr;
uniform sampler2D uPhoto0;
uniform sampler2D uPhoto1;
uniform float uMix;
uniform float uFlat;
uniform float uMilk;
uniform vec3 uTint;
uniform float uHasTint;
uniform vec2 uL;
uniform vec3 uLc;

float seg(vec2 p, out vec2 n) {
  vec2 pa = p - uA;
  vec2 ba = uB - uA;
  float bb = dot(ba, ba);
  float h = bb > 0.0 ? clamp(dot(pa, ba) / bb, 0.0, 1.0) : 0.0;
  vec2 q = pa - ba * h;
  float l = length(q);
  n = l > 1e-4 ? q / l : vec2(0.0, -1.0);
  return l - uR;
}

vec3 photo(vec2 p) {
  vec2 uv = clamp(p / uSize, 0.0, 1.0);
  return mix(texture2D(uPhoto0, uv).rgb, texture2D(uPhoto1, uv).rgb, uMix);
}

void main() {
  vec2 n;
  vec2 m;
  float sd = seg(vP, n);
  // The glass lifted off the photo: a tight contact shadow, a soft one below.
  float s1 = seg(vP - vec2(0.0, 2.0 * uK), m);
  float s2 = seg(vP - vec2(0.0, 12.0 * uK), m);
  float sh = 0.18 * (1.0 - smoothstep(-3.0 * uK, 3.0 * uK, s1))
           + 0.30 * (1.0 - smoothstep(-26.0 * uK, 26.0 * uK, s2));
  sh = min(sh, 0.42);
  float a = clamp(0.5 - sd * uDpr, 0.0, 1.0);
  if (a <= 0.0 && sh <= 0.002) discard;

  // Height: 0 at the outline, rising over a bevel almost the rod's radius,
  // so it reads as a rounded rod of glass.
  float bevel = uR * 0.95;
  float t = clamp(-sd, 0.0, bevel) / bevel;
  float h = 1.0 - pow(1.0 - t, 3.0);
  float dh = 3.0 * (1.0 - t) * (1.0 - t) / bevel;
  vec3 N = normalize(vec3(n * dh * uR * 0.5 * (1.0 - uFlat), 1.0));

  // Refraction, red bent a touch more than blue.
  vec2 off = -N.xy * uR * 1.6 * (1.0 - uFlat);
  vec3 c = vec3(photo(vP + off * 1.12).r, photo(vP + off).g, photo(vP + off * 0.88).b);

  // Stain, deeper where the glass is thicker; then the milk.
  float s = uHasTint * (0.22 + 0.33 * h);
  c *= 1.0 - s + s * uTint;
  float milk = max(uMilk * 0.6, uFlat * 0.45);
  c += (1.0 - c) * milk;

  vec3 L3 = normalize(vec3(uL, 0.55));
  vec3 H3 = normalize(L3 + vec3(0.0, 0.0, 1.0));
  float facing = dot(N.xy, L3.xy);
  float shade = 1.0 - max(0.0, -facing) * 0.45;
  float spec = pow(max(0.0, dot(N, H3)), 60.0) * 0.7 * (1.0 - uFlat);
  float rim = pow(1.0 - N.z, 2.2) * 0.3;
  float glow = spec + rim * (0.4 + 0.6 * max(0.0, facing));
  c = c * shade + uLc * glow;

  gl_FragColor = vec4(min(c, 1.0) * a, a + sh * (1.0 - a));
}`;

/** The photo cropped to the disc the way the page shows it (object-fit
    cover, then the photo's own rotation), as a square canvas. */
export function discCrop(
  img: HTMLImageElement,
  rotation: number,
  side: number,
): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = side;
  const ctx = c.getContext("2d");
  if (!ctx) return c;
  const turned = Math.abs(rotation) % 180 === 90;
  const w = turned ? img.naturalHeight : img.naturalWidth;
  const h = turned ? img.naturalWidth : img.naturalHeight;
  const scale = Math.max(side / w, side / h);
  ctx.translate(side / 2, side / 2);
  ctx.rotate((rotation * Math.PI) / 180);
  ctx.drawImage(
    img,
    (-img.naturalWidth * scale) / 2,
    (-img.naturalHeight * scale) / 2,
    img.naturalWidth * scale,
    img.naturalHeight * scale,
  );
  return c;
}

export class GlassHands {
  private gl: WebGLRenderingContext;
  private prog: WebGLProgram;
  private loc: Record<string, WebGLUniformLocation | null> = {};
  private tex: [WebGLTexture, WebGLTexture];
  private width = 1;
  private height = 1;
  private dpr = 1;

  /** null when the browser has no WebGL; the caller draws plain hands. */
  static create(canvas: HTMLCanvasElement): GlassHands | null {
    const gl = canvas.getContext("webgl", {
      premultipliedAlpha: true,
      antialias: false,
      alpha: true,
    });
    if (!gl) return null;
    try {
      return new GlassHands(gl);
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
    for (const name of [
      "uA",
      "uB",
      "uR",
      "uPad",
      "uSize",
      "uK",
      "uDpr",
      "uPhoto0",
      "uPhoto1",
      "uMix",
      "uFlat",
      "uMilk",
      "uTint",
      "uHasTint",
      "uL",
      "uLc",
    ])
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

    const blank = (): WebGLTexture => {
      const t = gl.createTexture()!;
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
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
        new Uint8Array([40, 40, 40, 255]),
      );
      return t;
    };
    this.tex = [blank(), blank()];
    gl.uniform1i(this.loc.uPhoto0!, 0);
    gl.uniform1i(this.loc.uPhoto1!, 1);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  }

  /** Match the canvas to its box: `width`×`height` CSS px at `dpr`. */
  resize(
    canvas: HTMLCanvasElement,
    width: number,
    height: number,
    dpr: number,
  ): void {
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    this.gl.viewport(0, 0, canvas.width, canvas.height);
  }

  /** What slot 0 or 1's glass bends: the photo as cropped to the disc. */
  setPhoto(slot: 0 | 1, source: TexImageSource): void {
    const gl = this.gl;
    gl.activeTexture(slot === 0 ? gl.TEXTURE0 : gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.tex[slot]);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  }

  /** Draw `hands` (back to front) and a hub of radius `hub` at the centre.
      `mix` crossfades from slot 0's photo (0) to slot 1's (1). */
  draw(hands: Hand[], hub: number, look: Look, mix: number): void {
    const gl = this.gl;
    const u = this.loc;
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(this.prog);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.tex[0]);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.tex[1]);
    const k = Math.min(this.width, this.height) / 1600;
    gl.uniform2f(u.uSize!, this.width, this.height);
    gl.uniform1f(u.uK!, k);
    gl.uniform1f(u.uDpr!, this.dpr);
    gl.uniform1f(u.uPad!, 40 * k);
    gl.uniform1f(u.uMix!, mix);
    gl.uniform1f(u.uFlat!, look.flat ? 1 : 0);
    gl.uniform1f(u.uMilk!, look.milk);
    const tint = look.tint;
    const top = tint ? Math.max(...tint) || 1 : 1;
    gl.uniform3f(
      u.uTint!,
      (tint?.[0] ?? top) / top,
      (tint?.[1] ?? top) / top,
      (tint?.[2] ?? top) / top,
    );
    gl.uniform1f(u.uHasTint!, tint ? 1 : 0);
    gl.uniform2f(u.uL!, look.light[0], look.light[1]);
    gl.uniform3f(
      u.uLc!,
      look.lightRgb[0] / 255,
      look.lightRgb[1] / 255,
      look.lightRgb[2] / 255,
    );
    const cx = this.width / 2;
    const cy = this.height / 2;
    const rod = (ax: number, ay: number, bx: number, by: number, r: number) => {
      gl.uniform2f(u.uA!, ax, ay);
      gl.uniform2f(u.uB!, bx, by);
      gl.uniform1f(u.uR!, r);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    for (const h of hands) {
      const dx = Math.sin(h.angle);
      const dy = -Math.cos(h.angle);
      rod(
        cx - dx * h.tail,
        cy - dy * h.tail,
        cx + dx * h.length,
        cy + dy * h.length,
        h.radius,
      );
    }
    if (hub > 0) rod(cx, cy, cx, cy, hub);
  }

  dispose(): void {
    const gl = this.gl;
    gl.deleteTexture(this.tex[0]);
    gl.deleteTexture(this.tex[1]);
    gl.deleteProgram(this.prog);
  }
}
