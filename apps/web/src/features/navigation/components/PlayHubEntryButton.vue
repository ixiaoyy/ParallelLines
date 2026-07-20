<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "rail" | "menu";
  }>(),
  {
    variant: "rail",
  },
);

</script>

<template>
  <RouterLink
    class="play-hub-entry"
    :class="`play-hub-entry--${variant}`"
    :to="{ name: 'play-hub' }"
    aria-label="进入平行线游乐场，探索私密空间和消消乐"
  >
    <span class="play-hub-entry__copy">
      <small>PLAYGROUND / 02</small>
      <strong>平行线游乐场</strong>
      <em>私密空间 · 消消乐</em>
    </span>
    <span class="play-hub-entry__tiles" aria-hidden="true">
      <i></i><i></i><i></i><i></i>
    </span>
    <span class="play-hub-entry__arrow" aria-hidden="true">↗</span>
  </RouterLink>
</template>

<style scoped lang="scss" src="./PlayHubEntryButton.scss"></style>
