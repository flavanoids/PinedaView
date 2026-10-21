// SPDX-License-Identifier: Apache-2.0
/** Layout-edit mode: a working copy of the card order that the Save bar commits
    to this device or to the whole profile. */
export const edit = $state<{
  active: boolean;
  stack: string[];
  hero: string | null;
}>({
  active: false,
  stack: [],
  hero: null,
});

export function enterEdit(hero: string | null, body: string[]): void {
  edit.hero = hero;
  edit.stack = [...body];
  edit.active = true;
}

export function cancelEdit(): void {
  edit.active = false;
  edit.stack = [];
}

export function moveCard(from: number, to: number): void {
  if (
    from === to ||
    from < 0 ||
    to < 0 ||
    from >= edit.stack.length ||
    to >= edit.stack.length
  ) {
    return;
  }
  const next = [...edit.stack];
  const [card] = next.splice(from, 1);
  if (card === undefined) return;
  next.splice(to, 0, card);
  edit.stack = next;
}

/** The full stack (hero first) to persist. */
export function fullStack(): string[] {
  return edit.hero ? [edit.hero, ...edit.stack] : [...edit.stack];
}
