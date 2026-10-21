<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
  A screen nobody has set up yet (ViewModel.welcome): no cards until someone
  keeps it from the phone menu's Screens page, which lists it as "A new
  screen wants to join".
-->
<script lang="ts">
  let { deviceId }: { deviceId: string } = $props();

  const menu = `${location.host}/menu`;
  // Straight to setting up this screen (menu_page's ?setup=).
  const setupUrl = $derived(
    `${location.origin}/menu?setup=${encodeURIComponent(deviceId)}`,
  );
  let qr = $state("");
  $effect(() => {
    void import("qrcode").then(({ default: QRCode }) => {
      void QRCode.toString(setupUrl, {
        type: "svg",
        margin: 1,
        color: { dark: "#1f1d1a", light: "#0000" },
      }).then((svg) => (qr = svg));
    });
  });
</script>

<div class="welcome" role="status">
  <span class="wave" aria-hidden="true">👋</span>
  <h1>New screen!</h1>
  <p>Scan this with your phone's camera to set me up.</p>
  {#if qr}
    <!-- eslint-disable-next-line svelte/no-at-html-tags -- our own QR SVG -->
    <div class="qr" aria-hidden="true">{@html qr}</div>
  {/if}
  <p class="or">Or open the menu on your phone: <b>{menu}</b></p>
</div>

<style>
  .welcome {
    position: fixed;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.6em;
    padding: 2rem;
    text-align: center;
    z-index: 20;
    background: #f6f3ee;
    color: #1f1d1a;
    font-size: clamp(1rem, 3.2vmin, 2.2rem);
  }
  .wave {
    font-size: 4em;
    line-height: 1;
  }
  h1 {
    margin: 0;
    font-size: 2.6em;
    line-height: 1.05;
  }
  p {
    margin: 0;
    max-width: 22em;
    line-height: 1.35;
  }
  .qr {
    width: min(14em, 38vmin);
    margin: 0.6em 0;
    padding: 0.6em;
    border-radius: 0.8em;
    background: #fff;
  }
  .qr :global(svg) {
    display: block;
    width: 100%;
    height: auto;
  }
  .or {
    color: #5b554d;
    font-size: 0.85em;
  }
</style>
