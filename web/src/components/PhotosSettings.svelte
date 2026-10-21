<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import type { Photo } from "@pinedaview/protocol";

  import { UNDO_MS, useSettings } from "../lib/settings.svelte";
  import { modal } from "../lib/modal";
  import Field from "./settings/Field.svelte";
  import Group from "./settings/Group.svelte";
  import ResetButton from "./settings/ResetButton.svelte";
  import Scope from "./settings/Scope.svelte";
  import Segmented from "./settings/Segmented.svelte";
  import Switch from "./settings/Switch.svelte";

  const settings = useSettings();
  const client = settings.client;
  const origin = location.origin;
  const profile = $derived(settings.profile);
  const screen = $derived(settings.screen);
  const config = $derived(settings.config);

  const HOLDS = [
    { value: "10", label: "10 s" },
    { value: "20", label: "20 s" },
    { value: "60", label: "1 min" },
    { value: "300", label: "5 min" },
  ] as const;
  const ORDERS = [
    { value: "manual", label: "Your order" },
    { value: "newest", label: "Newest first" },
    { value: "shuffle", label: "Shuffle" },
  ] as const;
  const FITS = [
    { value: "fill", label: "Fill the card" },
    { value: "fit", label: "Whole photo" },
  ] as const;
  const GUESTS = [
    { value: "open", label: "Allowed" },
    { value: "review", label: "Need approval" },
    { value: "off", label: "Off" },
  ] as const;

  let photos = $state<Photo[]>([]);
  let pending = $state<Photo[]>([]);
  let busy = $state(false);
  let selected = $state<string | null>(null);
  let status = $state("");
  let confirming = $state<Photo | null>(null);
  let deletingAnim = $state<string | null>(null);

  function removeWithAnimation(name: string): void {
    deletingAnim = name;
    setTimeout(() => {
      deletingAnim = null;
      remove(name);
    }, 640);
  }

  const current = $derived(photos.find((p) => p.name === selected) ?? null);
  const selIndex = $derived(photos.findIndex((p) => p.name === selected));
  const stack = $derived(
    screen?.card_stack?.length
      ? screen.card_stack
      : (profile?.card_stack ?? []),
  );
  const showing = $derived(
    stack.includes("photo") && !screen?.cards_off?.includes("photo"),
  );
  // The hold picker shows the saved value even if it isn't one of the steps.
  const holdValue = $derived(String(profile?.photo_hold_s ?? 20));
  const holds = $derived(
    HOLDS.some((h) => h.value === holdValue)
      ? HOLDS
      : [...HOLDS, { value: holdValue, label: `${holdValue} s` }],
  );

  // A delete waits out the Undo on its toast before it reaches the server;
  // closing Settings sends any still waiting.
  const deleting = new Map<string, ReturnType<typeof setTimeout>>();
  async function refresh(): Promise<void> {
    const [all, waiting] = await Promise.all([
      client.listPhotos(),
      client.pendingPhotos(),
    ]);
    photos = all.filter((p) => !deleting.has(p.name));
    pending = waiting;
  }
  $effect(() => {
    void refresh();
  });

  function thumb(p: Photo): string {
    return `${client.photoThumbUrl(p.name)}?r=${p.rotation}`;
  }

  async function upload(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const files = [...(input.files ?? [])];
    if (files.length === 0) return;
    busy = true;
    let added = 0;
    for (const file of files) {
      try {
        await client.uploadPhoto(file);
        added += 1;
      } catch {
        /* counted below */
      }
    }
    busy = false;
    input.value = "";
    await refresh();
    const failed = files.length - added;
    if (failed)
      settings.flash(
        `${added} added. ${failed} couldn't be added — already in the library, not a photo, or a clip over 10 s.`,
        true,
      );
    else settings.flash(added === 1 ? "Photo added" : `${added} photos added`);
    if (added && !showing) setShowing(true);
  }

  async function run(
    work: () => Promise<unknown>,
    done: string,
  ): Promise<void> {
    busy = true;
    if (await settings.attempt(work, done)) await refresh();
    busy = false;
    status = done;
  }

  function remove(name: string): void {
    if (deleting.has(name)) return;
    selected = null;
    photos = photos.filter((p) => p.name !== name);
    const send = (): void => {
      deleting.delete(name);
      void run(() => client.deletePhoto(name), "");
    };
    deleting.set(name, setTimeout(send, UNDO_MS));
    status = "Photo deleted";
    settings.flash("Photo deleted", false, {
      label: "Undo",
      run: () => {
        clearTimeout(deleting.get(name));
        deleting.delete(name);
        void refresh();
      },
    });
  }
  $effect(() => () => {
    for (const [name, timer] of deleting) {
      clearTimeout(timer);
      void client.deletePhoto(name).catch(() => {});
    }
  });

  async function move(delta: number): Promise<void> {
    const to = selIndex + delta;
    if (selIndex < 0 || to < 0 || to >= photos.length) return;
    const next = [...photos];
    const [item] = next.splice(selIndex, 1);
    if (!item) return;
    next.splice(to, 0, item);
    photos = next;
    status = `Moved to ${to + 1} of ${photos.length}`;
    await settings.attempt(
      () => client.reorderPhotos(next.map((p) => p.name)),
      "",
    );
  }

  function setShowing(on: boolean): void {
    if (!screen) return;
    if (on && !stack.includes("photo")) {
      void settings.saveScreen({ card_stack: [...stack, "photo"] });
      return;
    }
    const off = new Set(screen.cards_off ?? []);
    if (on) off.delete("photo");
    else off.add("photo");
    void settings.saveScreen({ cards_off: [...off] });
  }
</script>

{#if profile && config}
  <Scope kind="profile" name={profile.name} />

  <div class="top">
    <label class="btn primary" class:busy>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,video/quicktime,video/mp4"
        multiple
        disabled={busy}
        onchange={upload}
      />
      {busy ? "Working…" : "Add photos"}
    </label>
    <p class="hint">
      {photos.length === 1 ? "1 photo" : `${photos.length} photos`} in the library.
    </p>
  </div>
  <p class="visually-hidden" role="status" aria-live="polite">{status}</p>

  {#if pending.length}
    <Group
      title="Waiting for approval"
      description="Guests sent these. Approve them to add them to the slideshow."
    >
      <ul class="pending">
        {#each pending as photo (photo.name)}
          <li>
            <img src={thumb(photo)} alt="Sent by a guest" />
            <div class="pending-actions">
              <button
                type="button"
                class="btn small primary"
                disabled={busy}
                onclick={() =>
                  run(() => client.approvePhoto(photo.name), "Photo approved")}
                >Approve</button
              >
              <button
                type="button"
                class="btn small"
                disabled={busy}
                onclick={() =>
                  run(() => client.deletePhoto(photo.name), "Photo declined")}
                >Decline</button
              >
            </div>
          </li>
        {/each}
      </ul>
    </Group>
  {/if}

  <Group title="Slideshow">
    <Field label="Photo card on {settings.screenName}">
      {#snippet children(id)}
        <Switch {id} checked={showing} onchange={setShowing} />
      {/snippet}
    </Field>
    <Field label="Show each photo for">
      {#snippet children(id)}
        <Segmented
          {id}
          options={holds}
          value={holdValue}
          onchange={(v) => settings.saveProfile({ photo_hold_s: Number(v) })}
        />
      {/snippet}
    </Field>
    <Field
      label="Order"
      hint={profile.photo_order === "shuffle"
        ? "A new random order each time the screen starts."
        : profile.photo_order === "newest"
          ? "By the date each photo was taken, newest first."
          : "The order of the library below. Select a photo to move it."}
    >
      {#snippet children(id)}
        <Segmented
          {id}
          options={ORDERS}
          value={profile.photo_order}
          onchange={(photo_order) => settings.saveProfile({ photo_order })}
        />
      {/snippet}
    </Field>
    <Field
      label="Framing"
      hint={profile.photo_fit === "fit"
        ? "The whole photo, with dark bars where it doesn't fill the card."
        : "Fills the card. The edges of some photos are cropped."}
    >
      {#snippet children(id)}
        <Segmented
          {id}
          options={FITS}
          value={profile.photo_fit}
          onchange={(photo_fit) => settings.saveProfile({ photo_fit })}
        />
      {/snippet}
    </Field>
  </Group>

  <Group title="Guests">
    <Field
      label="Photos from guests"
      hint={config.guest_uploads === "off"
        ? "The QR code and upload page won't accept photos."
        : config.guest_uploads === "review"
          ? "Guests' photos wait here until you approve them."
          : `Anyone who scans the photo card's code, or opens ${origin}/upload, can add photos.`}
      stacked
    >
      {#snippet children(id)}
        <Segmented
          {id}
          options={GUESTS}
          value={config.guest_uploads}
          onchange={(guest_uploads) => settings.saveConfig({ guest_uploads })}
        />
      {/snippet}
    </Field>
  </Group>

  {#if photos.length > 0}
    <Group title="Library">
      <ul class="grid">
        {#each photos as photo, i (photo.name)}
          <li>
            <button
              type="button"
              class="tile"
              class:on={selected === photo.name}
              aria-pressed={selected === photo.name}
              aria-label={`Photo ${i + 1} of ${photos.length}`}
              onclick={() =>
                (selected = selected === photo.name ? null : photo.name)}
            >
              <img src={thumb(photo)} alt="" loading="lazy" />
              {#if photo.has_subject}
                <span
                  class="depth"
                  title="Ready for the Photo Clock's depth effect">✨</span
                >
              {/if}
            </button>
          </li>
        {/each}
      </ul>

      {#if current}
        <div class="editor" role="group" aria-label="Edit photo">
          <div
            class="preview-wrap"
            class:deleting={deletingAnim === current.name}
          >
            <img class="preview" src={thumb(current)} alt="" />
            {#if deletingAnim === current.name}
              <div class="trash-overlay">
                <div class="trash-anim">
                  <div class="trash-lid">
                    <svg
                      viewBox="0 0 32 10"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                      stroke-linecap="round"
                    >
                      <line x1="2" y1="8" x2="30" y2="8"></line>
                      <path
                        d="M12 8V3a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v5"
                        stroke-width="2"
                      ></path>
                    </svg>
                  </div>
                  <div class="trash-body">
                    <svg
                      viewBox="0 0 32 30"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path d="M5 2l2 24a3 3 0 0 0 3 3h12a3 3 0 0 0 3-3l2-24"
                      ></path>
                      <line x1="12" y1="8" x2="12" y2="22"></line>
                      <line x1="16" y1="8" x2="16" y2="22"></line>
                      <line x1="20" y1="8" x2="20" y2="22"></line>
                    </svg>
                  </div>
                </div>
              </div>
            {/if}
          </div>
          <div class="tools">
            <button
              type="button"
              class="btn small"
              disabled={busy}
              onclick={() =>
                run(
                  () =>
                    client.rotatePhoto(
                      current.name,
                      (current.rotation + 90) % 360,
                    ),
                  "Rotated",
                )}>Rotate</button
            >
            <button
              type="button"
              class="btn small"
              disabled={busy || selIndex <= 0}
              onclick={() => move(-1)}>Move earlier</button
            >
            <button
              type="button"
              class="btn small"
              disabled={busy || selIndex >= photos.length - 1}
              onclick={() => move(1)}>Move later</button
            >
            <button
              type="button"
              class="btn small"
              disabled={busy}
              onclick={() =>
                run(
                  () => client.photoToWallpaper(current.name),
                  "Set as the background image",
                )}>Use as background</button
            >
            <button
              type="button"
              class="btn small danger"
              disabled={busy}
              onclick={() => (confirming = current)}>Delete</button
            >
          </div>
        </div>
      {:else}
        <p class="hint">Select a photo to rotate, move or delete it.</p>
      {/if}
    </Group>
  {/if}

  <ResetButton
    what="the slideshow timing, order and framing, and allows guest photos again. Your photos stay"
    onreset={async () => {
      const done = await settings.save(
        () =>
          client.resetSection({ section: "photos", profile_id: profile.id }),
        "Photo settings reset",
      );
      if (done) await settings.load();
    }}
  />

  {#if confirming}
    <div
      class="scrim"
      use:modal={{ onClose: () => (confirming = null) }}
      role="presentation"
      onclick={(e) => {
        if (e.target === e.currentTarget) confirming = null;
      }}
    >
      <div
        class="confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="del-modal-h"
      >
        <img class="confirm-preview" src={thumb(confirming)} alt="" />
        <h3 id="del-modal-h">Delete photo?</h3>
        <p class="confirm-desc">
          This will remove this photo from the slideshow. All versions and
          modifications of this image will be permanently deleted.
        </p>
        <div class="confirm-actions">
          <button
            type="button"
            class="btn small danger"
            disabled={busy}
            onclick={() => {
              const target = confirming;
              confirming = null;
              if (target) removeWithAnimation(target.name);
            }}
          >
            Delete photo
          </button>
          <button
            type="button"
            class="btn small"
            disabled={busy}
            onclick={() => (confirming = null)}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  {/if}
{/if}

<style>
  .top {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
  }
  .top input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }
  .busy {
    opacity: 0.6;
  }
  .pending {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(8.5rem, 1fr));
    gap: var(--space-2);
    padding: 12px 0;
  }
  .pending li {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .pending img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
    border-radius: 10px;
  }
  .pending-actions {
    display: flex;
    gap: 4px;
  }
  .pending-actions .btn {
    flex: 1;
    padding: 0 6px;
  }
  .grid {
    list-style: none;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
    gap: 6px;
    max-height: 40dvh;
    overflow-y: auto;
    padding: 12px 0;
  }
  .tile {
    position: relative;
    display: block;
    width: 100%;
    aspect-ratio: 1;
    padding: 0;
    border: 2px solid transparent;
    border-radius: 10px;
    overflow: hidden;
    background: color-mix(in srgb, var(--on-stage) 8%, transparent);
    cursor: pointer;
  }
  .tile.on {
    border-color: var(--accent);
  }
  .tile img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .depth {
    position: absolute;
    right: 4px;
    bottom: 4px;
    padding: 1px 3px;
    border-radius: 6px;
    font-size: 11px;
    background: rgb(0 0 0 / 0.6);
  }
  .editor {
    display: flex;
    gap: var(--space-3);
    margin: 4px 0 12px;
    padding: var(--space-2);
    border-radius: 12px;
    background: color-mix(in srgb, var(--on-stage) 6%, transparent);
  }
  .preview {
    width: 96px;
    height: 96px;
    object-fit: cover;
    border-radius: 8px;
    flex: none;
  }
  .tools {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-content: flex-start;
  }
  .preview-wrap {
    position: relative;
    width: 96px;
    height: 96px;
    border-radius: 8px;
    overflow: hidden;
    flex: none;
  }
  .preview-wrap .preview {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .preview-wrap.deleting .preview {
    animation: photo-crumple 480ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
  }
  @keyframes photo-crumple {
    0% {
      transform: scale(1);
      opacity: 1;
      filter: none;
    }
    40% {
      transform: scale(0.6) translateY(12px) rotate(8deg);
      opacity: 0.8;
      filter: blur(1px);
    }
    100% {
      transform: scale(0.12) translateY(34px) rotate(16deg);
      opacity: 0;
      filter: blur(4px);
    }
  }
  .trash-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    pointer-events: none;
  }
  .trash-anim {
    position: relative;
    width: 44px;
    height: 48px;
    display: flex;
    flex-direction: column;
    align-items: center;
    animation: trash-bounce 640ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
  }
  .trash-lid {
    width: 36px;
    height: 12px;
    color: #e53935;
    transform-origin: 4px 10px;
    animation: lid-flip 520ms cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  }
  .trash-lid svg {
    width: 100%;
    height: 100%;
    display: block;
  }
  .trash-body {
    width: 34px;
    height: 36px;
    margin-top: -3px;
    color: #e53935;
  }
  .trash-body svg {
    width: 100%;
    height: 100%;
    display: block;
  }
  @keyframes lid-flip {
    0% {
      transform: rotate(0deg) translate(0, 0);
    }
    22% {
      transform: rotate(-44deg) translate(-4px, -6px);
    }
    65% {
      transform: rotate(-44deg) translate(-4px, -6px);
    }
    85% {
      transform: rotate(4deg) translate(0, 1px);
    }
    100% {
      transform: rotate(0deg) translate(0, 0);
    }
  }
  @keyframes trash-bounce {
    0% {
      transform: scale(0.7);
      opacity: 0;
    }
    20% {
      transform: scale(1.15);
      opacity: 1;
    }
    65% {
      transform: scale(1);
    }
    85% {
      transform: scale(1.1) translateY(-2px);
    }
    100% {
      transform: scale(0.9);
      opacity: 0.95;
    }
  }
  .scrim {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: var(--space-3);
  }
  .confirm-modal {
    background: var(--stage);
    color: var(--on-stage);
    border: 1px solid color-mix(in srgb, var(--on-stage) 12%, transparent);
    border-radius: 20px;
    padding: 24px;
    max-width: 360px;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.4);
    animation: modal-pop 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  @keyframes modal-pop {
    from {
      transform: scale(0.92);
      opacity: 0;
    }
    to {
      transform: scale(1);
      opacity: 1;
    }
  }
  .confirm-preview {
    width: 120px;
    height: 120px;
    object-fit: cover;
    border-radius: 14px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  }
  .confirm-modal h3 {
    margin: 0 0 8px;
    font-size: 1.25rem;
  }
  .confirm-desc {
    margin: 0 0 20px;
    font-size: 0.9rem;
    color: color-mix(in srgb, var(--on-stage) 70%, transparent);
    line-height: 1.4;
  }
  .confirm-actions {
    display: flex;
    flex-direction: column;
    width: 100%;
    gap: 8px;
  }
  .confirm-actions .btn {
    width: 100%;
    padding: 10px;
  }
</style>
