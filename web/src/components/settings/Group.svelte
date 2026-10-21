<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- A titled run of settings inside a section, divided by hairlines. -->
<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    title?: string;
    description?: string;
    children: Snippet;
  }
  let { title, description, children }: Props = $props();
</script>

<section class="group">
  {#if title}<h4>{title}</h4>{/if}
  {#if description}<p class="description">{description}</p>{/if}
  <div class="rows">{@render children()}</div>
</section>

<style>
  .group {
    display: flex;
    flex-direction: column;
  }
  .group + :global(.group) {
    margin-top: var(--space-3);
  }
  h4 {
    margin: 0 0 2px;
    font-size: var(--type-caption);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--on-stage-soft);
  }
  .description {
    margin: 2px 0 0;
    font-size: var(--type-caption);
    line-height: 1.4;
    color: var(--on-stage-soft);
  }
  .rows {
    display: flex;
    flex-direction: column;
  }
  .rows > :global(* + *) {
    border-top: 1px solid color-mix(in srgb, var(--on-stage) 9%, transparent);
  }
</style>
