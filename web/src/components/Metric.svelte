<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
  import { settle } from "../lib/settle";

  interface Props {
    label: string;
    value: string;
    sub?: string;
  }
  let { label, value, sub }: Props = $props();
</script>

<div class="metric">
  <span class="label">{label}</span>
  <span class="value" use:settle={value}
    >{value}{#if sub}<i>{sub}</i>{/if}</span
  >
</div>

<style>
  .metric {
    display: flex;
    flex-direction: column;
    gap: var(--space-label);
  }
  .label {
    font-size: var(--type-caption);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--on-card-faint);
  }
  .value {
    font-size: var(--type-md);
    font-weight: var(--weight-label);
  }
  .value i {
    font-style: normal;
    color: var(--on-card-faint);
    margin-left: 0.35em;
  }
</style>
