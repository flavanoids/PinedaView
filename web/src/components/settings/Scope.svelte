<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  Says who a section's settings apply to, so nobody is surprised when a
  change shows up on another screen (or doesn't).
-->
<script lang="ts">
  interface Props {
    kind: "home" | "profile" | "screen" | "device";
    name?: string;
  }
  let { kind, name = "" }: Props = $props();

  const text = $derived(
    {
      home: "Applies to every screen in the house.",
      profile: `Shared by every screen using the “${name}” profile.`,
      screen: name
        ? `Applies to “${name}” only.`
        : "Applies to this screen only.",
      device: "Saved on this device only.",
    }[kind],
  );
</script>

<p class="scope">{text}</p>

<style>
  .scope {
    margin: 0 0 var(--space-2);
    padding: 6px 10px;
    border-radius: 8px;
    font-size: var(--type-caption);
    line-height: 1.4;
    color: var(--on-stage-soft);
    background: color-mix(in srgb, var(--accent) 9%, transparent);
  }
</style>
