<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { a11y, setA11y } from "../lib/a11y.svelte";
  import {
    motion,
    setMotionChoice,
    type MotionChoice,
  } from "../lib/tier.svelte";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";

  const MOTION: { value: MotionChoice; label: string }[] = [
    { value: "auto", label: "Auto" },
    { value: "standard", label: "Full" },
    { value: "lite", label: "Reduced" },
  ];

  const TOGGLES: {
    key: keyof typeof a11y;
    label: string;
    hint: string;
  }[] = [
    {
      key: "largerText",
      label: "Larger text",
      hint: "Makes all text one size bigger.",
    },
    {
      key: "highContrast",
      label: "High contrast",
      hint: "Darker secondary text and an outline around each card.",
    },
    {
      key: "reduceTransparency",
      label: "Reduce transparency",
      hint: "Replaces the frosted-glass effect with solid cards.",
    },
    {
      key: "announceUpdates",
      label: "Announce updates",
      hint: "A screen reader speaks weather alerts and music changes.",
    },
  ];
</script>

<Scope kind="device" />

<Group>
  <Field
    label="Motion"
    hint={motion.choice === "auto"
      ? `Auto chose ${motion.tier === "lite" ? "reduced" : "full"} motion for this device. Your system's reduce-motion setting is always respected.`
      : motion.choice === "lite"
        ? "Cards change without animation. Your system's reduce-motion setting is always respected."
        : "Cards animate as they change. Your system's reduce-motion setting is always respected."}
  >
    {#snippet children(id)}
      <Segmented
        {id}
        options={MOTION}
        value={motion.choice === "rich" ? "standard" : motion.choice}
        onchange={setMotionChoice}
      />
    {/snippet}
  </Field>

  {#each TOGGLES as t (t.key)}
    <Field label={t.label} hint={t.hint}>
      {#snippet children(id)}
        <Switch
          {id}
          checked={a11y[t.key]}
          onchange={(on) => setA11y(t.key, on)}
        />
      {/snippet}
    </Field>
  {/each}
</Group>
