<script setup lang="ts">
import { message } from "ant-design-vue";
import { ref } from "vue";

import { requestFableSpaceSsoTicket } from "@/features/auth/api";
import { staticAssetUrl } from "@/shared/assets/staticAssets";

withDefaults(
  defineProps<{
    variant?: "rail" | "menu";
  }>(),
  {
    variant: "rail",
  },
);

const opening = ref(false);
const entryImageUrl = staticAssetUrl("/private-space-entry-b7d15288.png");

// Requests a short-lived backend ticket and transfers the authorized browser to FableSpace.
// Parameters: none. Return value: resolves after navigation starts or the error is shown; side effect: changes page location.
async function openFableSpace(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  try {
    const ticket = await requestFableSpaceSsoTicket();
    window.location.assign(ticket.redirect_url);
  } catch {
    message.error("私密空间暂时无法进入，请稍后再试");
    opening.value = false;
  }
}
</script>

<template>
  <button
    type="button"
    class="fablespace-entry"
    :class="`fablespace-entry--${variant}`"
    :disabled="opening"
    :aria-busy="opening"
    aria-label="进入 FableSpace 私密空间"
    @click="openFableSpace"
  >
    <img
      :src="entryImageUrl"
      alt=""
      width="1008"
      height="576"
      decoding="async"
      aria-hidden="true"
    />
  </button>
</template>

<style scoped lang="scss" src="./FableSpaceEntryButton.scss"></style>
