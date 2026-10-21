<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Test-only wrapper: gives Cycler a concrete `item` snippet. `count` is fed
     by an inline `items.length`, exactly like the cards feed it from their
     store arrays, so tests exercise the same getter-prop reactivity. The
     dwell is a module constant like the cards' CYCLE_MS — the real callers
     never feed it reactively, and the testing library's raw-state props
     would invalidate it on every rerender, which the app never does. -->
<script lang="ts">
  import Cycler from "./Cycler.svelte";

  let { items }: { items: string[] } = $props();
  const DWELL_MS = 1000;
</script>

<Cycler count={items.length} intervalMs={DWELL_MS}>
  {#snippet item(i)}
    <span class="item" data-i={i}>item {i}</span>
  {/snippet}
</Cycler>
