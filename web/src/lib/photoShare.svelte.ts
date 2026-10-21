// SPDX-License-Identifier: Apache-2.0
/** The photo on screen right now, shared by the Photo Clock and the Photo
    card, so Alternate's handoff carries one photo across instead of cutting
    to a different one. Whichever is showing writes it; the other starts
    from it (and the Photo card, warming out of sight, keeps following it). */
export const photoShare = $state<{ name: string | null }>({ name: null });
