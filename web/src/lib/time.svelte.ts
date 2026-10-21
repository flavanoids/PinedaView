// SPDX-License-Identifier: Apache-2.0
export const clock = $state<{ now: Date }>({ now: new Date() });

let handle: ReturnType<typeof setInterval> | undefined;

export function startClock(): void {
  stopClock();
  handle = setInterval(() => {
    clock.now = new Date();
  }, 1000);
}

export function stopClock(): void {
  if (handle !== undefined) clearInterval(handle);
  handle = undefined;
}

export interface Remaining {
  minutes: number;
  seconds: number;
  totalSeconds: number;
  done: boolean;
}

/** Time left until an ISO target — computed locally so the server needn't
    stream a tick every second. */
export function remaining(
  targetIso: string,
  from: Date = clock.now,
): Remaining {
  const ms = new Date(targetIso).getTime() - from.getTime();
  if (Number.isNaN(ms) || ms <= 0) {
    return { minutes: 0, seconds: 0, totalSeconds: 0, done: true };
  }
  const totalSeconds = Math.floor(ms / 1000);
  return {
    minutes: Math.floor(totalSeconds / 60),
    seconds: totalSeconds % 60,
    totalSeconds,
    done: false,
  };
}
