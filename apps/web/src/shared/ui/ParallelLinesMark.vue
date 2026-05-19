<template>
  <svg
    class="parallel-lines-mark"
    viewBox="0 0 120 48"
    aria-hidden="true"
    focusable="false"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    shape-rendering="geometricPrecision"
  >
    <defs>
      <linearGradient id="parallel-lines-brand-gradient" x1="6" y1="24" x2="114" y2="24" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="var(--brand-blue)" />
        <stop offset="1" stop-color="var(--brand-cyan)" />
      </linearGradient>
    </defs>

    <g
      class="parallel-lines-mark__lines"
      stroke="url(#parallel-lines-brand-gradient)"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M8 12H62C73 12 79 18 91 18H112" />
      <path d="M8 18H66C75 18 80 22 90 22H112" />
      <path d="M8 24H78H112" />
      <path d="M8 30H66C75 30 80 26 90 26H112" />
      <path d="M8 36H62C73 36 79 30 91 30H112" />
    </g>
    <circle class="parallel-lines-mark__node" cx="78" cy="24" r="6.2" />
    <circle class="parallel-lines-mark__node-core" cx="78" cy="24" r="2.35" />
  </svg>
</template>

<style scoped>
.parallel-lines-mark {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.parallel-lines-mark__lines path {
  stroke-width: 5.25;
}

.parallel-lines-mark__node {
  fill: var(--bg-surface);
  stroke: var(--brand-cyan);
  stroke-width: 5.25;
}

.parallel-lines-mark__node-core {
  fill: var(--brand-cyan);
}
</style>
