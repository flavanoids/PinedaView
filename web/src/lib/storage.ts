// SPDX-License-Identifier: Apache-2.0
/** localStorage that never throws (private windows, blocked site data). */
export function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore — a remembered convenience, not required state */
  }
}
