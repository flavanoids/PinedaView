<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts" module>
  // wttr.in weather code → emoji. Trimmed; unknown codes fall back to a thermometer.
  const GLYPHS: Record<string, string> = {
    "113": "☀️",
    "116": "⛅",
    "119": "☁️",
    "122": "☁️",
    "143": "🌫️",
    "176": "🌦️",
    "179": "🌨️",
    "182": "🌧️",
    "200": "⛈️",
    "227": "🌨️",
    "230": "❄️",
    "248": "🌫️",
    "266": "🌦️",
    "296": "🌧️",
    "302": "🌧️",
    "308": "🌧️",
    "320": "🌨️",
    "338": "❄️",
    "353": "🌦️",
    "356": "🌧️",
    "359": "🌧️",
    "386": "⛈️",
    "389": "⛈️",
  };

  // Codes whose daytime glyph carries a sun — swapped for a night face when the
  // slot is after dusk, so a 3am forecast row doesn't show ☀️.
  const NIGHT: Record<string, string> = {
    "113": "🌙",
    "116": "☁️",
  };

  export function glyphFor(
    code: string | number | null | undefined,
    isDay: boolean = true,
  ): string {
    const key = String(code);
    if (!isDay && key in NIGHT) return NIGHT[key] as string;
    return GLYPHS[key] ?? "🌡️";
  }
</script>

<script lang="ts">
  interface Props {
    code: string | number | null | undefined;
    size?: "sm" | "lg";
    isDay?: boolean;
  }
  let { code, size = "lg", isDay = true }: Props = $props();
</script>

<span class="glyph" class:sm={size === "sm"} aria-hidden="true"
  >{glyphFor(code, isDay)}</span
>

<style>
  .glyph {
    font-size: var(--type-xl);
    line-height: 1.15;
  }
  .glyph.sm {
    font-size: var(--type-lg);
  }
</style>
