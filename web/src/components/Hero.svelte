<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { ViewModel } from "@pinedaview/protocol";

  import { cardComponent } from "../cards";
  import Countdown from "../cards/Countdown.svelte";
  import NowPlaying from "../cards/NowPlaying.svelte";
  import { cardStale } from "../cards/types";

  let { view }: { view: ViewModel } = $props();
</script>

{#if view.hero.kind === "nowPlaying"}
  <NowPlaying {view} stale={false} hero={true} />
{:else if view.hero.kind === "countdown"}
  <Countdown {view} stale={false} hero={true} />
{:else if view.hero.card}
  {@const CardView = cardComponent(view.hero.card)}
  <CardView
    {view}
    stale={cardStale(view, view.hero.card)}
    hero={true}
    id={view.hero.card}
  />
{/if}
