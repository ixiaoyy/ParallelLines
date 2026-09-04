<script setup lang="ts">
import { computed } from "vue";

import type { PersonaKind } from "@/entities/user/model";
import { operatorIdentity } from "@/features/users/operatorIdentity";
import UiBadge from "@/shared/ui/Badge.vue";

const props = defineProps<{
  isPersona?: boolean | null;
  kind?: PersonaKind | null;
}>();
const identity = computed(() => operatorIdentity(props.isPersona, props.kind));
</script>

<template>
  <UiBadge
    v-if="identity"
    class="operator-identity"
    tone="gray"
    :title="identity.description"
    :data-persona-kind="identity.kind ?? 'managed'"
  >
    {{ identity.label }}
  </UiBadge>
</template>

<style scoped>
.operator-identity {
  flex: 0 0 auto;
  margin: 0;
  color: var(--text);
  background: var(--bg-subtle);
  white-space: nowrap;
  line-height: 1.45;
}
</style>
