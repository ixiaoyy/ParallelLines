<script setup lang="ts">
defineProps<{ title: string; description: string }>();
</script>

<template>
  <a-empty class="empty-state" :description="null">
    <div class="orb" aria-hidden="true" />
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <slot />
  </a-empty>
</template>

<style scoped>
.empty-state {
  display: grid;
  justify-items: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
  color: var(--text);
}

.orb {
  width: 3rem;
  height: 3rem;
  border-radius: 1.2rem;
  background: linear-gradient(
    135deg,
    rgba(var(--primary-rgb), 0.22),
    rgba(var(--accent-lime-rgb), 0.22)
  );
}

h3 {
  margin: 0;
  color: var(--title);
}

p {
  max-width: 30rem;
  margin: 0;
}
</style>
