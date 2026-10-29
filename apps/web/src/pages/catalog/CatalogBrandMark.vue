<template>
  <span class="catalog-brand-mark" aria-hidden="true"><img src="/logo-lines-mark.png" alt="" width="512" height="512" decoding="async" /></span>
</template>

<style scoped>
/* Display the existing official mark, including an 8px source safety margin.
   Source pixels and path stay unchanged; the window removes canvas whitespace. */
.catalog-brand-mark { position: relative; display: block; width: var(--catalog-brand-mark-size, 52px); aspect-ratio: 440 / 363; flex: 0 0 auto; overflow: hidden; mix-blend-mode: multiply; }
.catalog-brand-mark img { position: absolute; display: block; width: 116.363636%; height: auto; max-width: none; left: -8.181818%; top: -21.487603%; }
</style>
