<script setup lang="ts">
import type { RouteLocationRaw } from "vue-router";

defineProps<{
  id: string;
  title: string;
  mobileTitle?: string;
  description: string;
  linkLabel?: string;
  linkTo?: RouteLocationRaw;
  feed?: boolean;
}>();
</script>

<template>
  <section class="home-section-head" :class="{ 'home-section-head--feed': feed }" :aria-labelledby="id">
    <div>
      <h2 :id="id">
        <span :class="['section-title-desktop', { 'section-title-desktop--has-mobile': mobileTitle }]">
          {{ title }}
        </span>
        <span v-if="mobileTitle" class="section-title-mobile">{{ mobileTitle }}</span>
      </h2>
      <p>{{ description }}</p>
    </div>
    <RouterLink v-if="linkLabel && linkTo" class="section-link" :to="linkTo">{{ linkLabel }}</RouterLink>
  </section>
</template>

<style scoped lang="scss" src="./HomeSectionHead.scss"></style>

