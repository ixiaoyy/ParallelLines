<script setup lang="ts">
import { FontAwesomeIcon } from "@fortawesome/vue-fontawesome";

import { catalogIcons } from "./catalogIcons";
import type { CatalogIconName } from "./catalogIcons";

defineProps<{ name: CatalogIconName }>();
</script>

<template>
  <FontAwesomeIcon class="catalog-icon" :icon="catalogIcons[name]" aria-hidden="true" focusable="false" />
</template>

<style scoped>
.catalog-icon { display: block; width: 1.2em; height: 1em; flex: 0 0 auto; overflow: visible; }
</style>
