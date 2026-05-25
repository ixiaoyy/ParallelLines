<script setup lang="ts">
import { computed } from "vue";

import { extensionHref, extensionLabel } from "@/features/plugins/model";
import { useSiteExtensions } from "@/features/plugins/queries";

const props = defineProps<{
  slotName: string;
  compact?: boolean;
}>();

const extensionsQuery = useSiteExtensions();
const extensions = computed(() =>
  (extensionsQuery.data.value ?? []).filter((extension) => extension.slot === props.slotName),
);
</script>

<template>
  <div v-if="extensions.length" class="plugin-slot" :class="{ 'plugin-slot--compact': compact }">
    <template v-for="extension in extensions" :key="`${extension.plugin_id}:${extension.key}`">
      <RouterLink
        v-if="extensionHref(extension)"
        class="plugin-slot__entry"
        :to="extensionHref(extension) ?? '/'"
        :title="extension.description"
      >
        {{ extensionLabel(extension) }}
      </RouterLink>
      <span v-else class="plugin-slot__entry" :title="extension.description">
        {{ extensionLabel(extension) }}
      </span>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./PluginSlot.scss"></style>
