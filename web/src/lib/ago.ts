// SPDX-License-Identifier: Apache-2.0
/** "Updated 25 min ago", "Updated 3 hr ago", "Updated yesterday". */
export function updatedAgo(iso: string, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - Date.parse(iso)) / 60_000));
  if (Number.isNaN(minutes)) return "Not updated lately";
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Updated ${hours} hr ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "Updated yesterday" : `Updated ${days} days ago`;
}
