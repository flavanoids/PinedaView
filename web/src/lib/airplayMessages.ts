// SPDX-License-Identifier: Apache-2.0
/**
 * Idle prompts for the now-playing card when AirPlay has nothing live —
 * a nudge instead of stale leftover track metadata. One shows per calendar
 * day, cycling through the whole list before repeating (~monthly at 30
 * entries), so the card still feels tended even at rest.
 */

export const AIRPLAY_IDLE_MESSAGES: readonly string[] = [
  "Nothing's playing right now — go on, put something on.",
  "Quiet in here. How about some music?",
  "This card's just waiting for you to hit play.",
  "Hey — maybe AirPlay some Leon Bridges?",
  "No tunes yet today. Chappell Roan's always a good call.",
  "Feels like a Bad Bunny kind of afternoon.",
  "Nothing playing. Sabrina Carpenter, maybe?",
  "Silence isn't a vibe. Fix it with AirPlay.",
  "The speakers are ready when you are.",
  "How about you play some music?",
  "No Doubt could fix this silence.",
  "AirPlay something — anything's better than quiet.",
  "This screen's ready to show off whatever you play.",
  "A little Fergie never hurt anybody.",
  "Try some Nelly Furtado — it's been a minute.",
  "Nothing's on. Toro y Moi always works.",
  "Music's one tap away — AirPlay from your phone.",
  "Feeling an Eli Escobar set? Just saying.",
  "Nothing playing yet. What's the mood today?",
  "Elvis Crespo would liven this place up.",
  "Always Proper's got something for this moment.",
  "This card's better with a song attached.",
  "Go ahead, AirPlay something — we'll wait.",
  "No music yet — the house is too quiet.",
  "Sabrina, Chappell, Bad Bunny — take your pick.",
  "Put something on. This card's got nothing to show otherwise.",
  "AirPlay's open. Music's optional but encouraged.",
  "Nothing's playing. Maybe it's a No Doubt day.",
  "This is your sign to play something.",
  "Quiet right now — AirPlay something good.",
];

/** Deterministic, same message on every device on a given calendar day —
    days-since-epoch (UTC) mod the list length, so it advances once a day
    and loops back to the start once the list is exhausted. */
export function idleAirplayMessage(now: Date): string {
  const days = Math.floor(now.getTime() / 86_400_000);
  const i =
    ((days % AIRPLAY_IDLE_MESSAGES.length) + AIRPLAY_IDLE_MESSAGES.length) %
    AIRPLAY_IDLE_MESSAGES.length;
  return AIRPLAY_IDLE_MESSAGES[i] ?? AIRPLAY_IDLE_MESSAGES[0]!;
}
