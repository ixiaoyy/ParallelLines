<script setup lang="ts">
import { EyeInvisibleOutlined, EyeOutlined } from "@ant-design/icons-vue";
import { computed, ref } from "vue";

withDefaults(
  defineProps<{
    modelValue: string;
    autocomplete?: string;
    disabled?: boolean;
    id?: string;
    inputmode?: "decimal" | "email" | "none" | "numeric" | "search" | "tel" | "text" | "url";
    maxlength?: number;
    name?: string;
    placeholder?: string;
  }>(),
  {
    autocomplete: undefined,
    disabled: false,
    id: undefined,
    inputmode: undefined,
    maxlength: undefined,
    name: undefined,
    placeholder: undefined,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: string];
}>();

const visible = ref(false);
const inputType = computed(() => (visible.value ? "text" : "password"));

function updateValue(event: Event) {
  emit("update:modelValue", (event.target as HTMLInputElement).value);
}
</script>

<template>
  <span class="password-field">
    <input
      :id="id"
      :autocomplete="autocomplete"
      :disabled="disabled"
      :inputmode="inputmode"
      :maxlength="maxlength"
      :name="name"
      :placeholder="placeholder"
      :type="inputType"
      :value="modelValue"
      @input="updateValue"
    />
    <button
      type="button"
      class="password-field__toggle"
      :aria-label="visible ? '隐藏密码' : '显示密码'"
      :aria-pressed="visible"
      :disabled="disabled"
      @click="visible = !visible"
    >
      <EyeInvisibleOutlined v-if="visible" aria-hidden="true" />
      <EyeOutlined v-else aria-hidden="true" />
    </button>
  </span>
</template>

<style scoped lang="scss">
.password-field {
  position: relative;
  display: block;
  width: 100%;
  color: var(--title);
}

.password-field input {
  width: 100%;
  min-height: 2.6rem;
  border: 1px solid var(--input-border);
  border-radius: 0.3rem;
  padding: 0 2.65rem 0 0.65rem;
  color: var(--title);
  background: var(--bg-surface);
  font: inherit;
}

.password-field input:focus {
  border-color: var(--btn-primary-border);
  outline: 2px solid var(--theme-focus-ring);
}

.password-field__toggle {
  position: absolute;
  top: 50%;
  right: 0.35rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: 0;
  border-radius: 999px;
  color: var(--muted);
  background: transparent;
  cursor: pointer;
  transform: translateY(-50%);
  transition:
    color 160ms ease,
    background 160ms ease;
}

.password-field__toggle:hover,
.password-field__toggle:focus-visible {
  color: var(--primary);
  background: rgba(var(--primary-rgb), 0.08);
  outline: none;
}

.password-field__toggle:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.password-field__toggle :deep(svg) {
  width: 1rem;
  height: 1rem;
}
</style>
