// SPDX-License-Identifier: Apache-2.0
/**
 * An album cover's average colour as `rgb(r g b)`, for tinting the glass or
 * panel it sits on so it reads as part of the record rather than generic
 * grey. One 1×1 canvas draw per cover — no per-frame cost. Resolves
 * undefined if the image won't load or the canvas is tainted (a
 * cross-origin cover in dev).
 */
export function coverTint(url: string): Promise<string | undefined> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = c.height = 1;
        const ctx = c.getContext("2d");
        if (!ctx) return resolve(undefined);
        ctx.drawImage(img, 0, 0, 1, 1);
        const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
        resolve(`rgb(${r} ${g} ${b})`);
      } catch {
        resolve(undefined);
      }
    };
    img.onerror = () => resolve(undefined);
    img.src = url;
  });
}
