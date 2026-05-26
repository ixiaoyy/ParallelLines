<template>
  <div class="hero-convergence" aria-hidden="true">
    <svg
      class="hero-convergence__svg"
      viewBox="0 0 380 220"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      shape-rendering="geometricPrecision"
    >
      <defs>
        <linearGradient id="hc-stage" x1="0" y1="0" x2="380" y2="220" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#ffffff" />
          <stop offset="100%" stop-color="#f0f9ff" />
        </linearGradient>
        <radialGradient id="hc-core" cx="50%" cy="52%" r="34%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
          <stop offset="70%" stop-color="#e0f2fe" stop-opacity="0.35" />
          <stop offset="100%" stop-color="#f8fafc" stop-opacity="0" />
        </radialGradient>
        <filter id="hc-soft" x="-8%" y="-8%" width="116%" height="116%">
          <feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#94a3b8" flood-opacity="0.08" />
        </filter>
      </defs>

      <rect width="380" height="220" rx="24" fill="url(#hc-stage)" />
      <rect width="380" height="220" rx="24" fill="url(#hc-core)" />

      <!-- 左下 → 右上（logo 左簇） -->
      <g class="hero-convergence__band hero-convergence__band--rise" filter="url(#hc-soft)" stroke-linecap="round">
        <line x1="22" y1="188" x2="128" y2="58" stroke="#5ecfff" stroke-width="11" />
        <line x1="48" y1="196" x2="148" y2="72" stroke="#fdba74" stroke-width="10" />
        <line x1="72" y1="190" x2="162" y2="66" stroke="#f87171" stroke-width="9" />
      </g>

      <!-- 右上 → 左下（交汇） -->
      <g class="hero-convergence__band hero-convergence__band--fall" filter="url(#hc-soft)" stroke-linecap="round">
        <line x1="168" y1="38" x2="286" y2="152" stroke="#fdba74" stroke-width="9" />
        <line x1="188" y1="32" x2="302" y2="142" stroke="#fde047" stroke-width="8" />
      </g>

      <!-- 右下 → 左上（logo 右簇） -->
      <g class="hero-convergence__band hero-convergence__band--lift" filter="url(#hc-soft)" stroke-linecap="round">
        <line x1="148" y1="198" x2="318" y2="32" stroke="#b8e635" stroke-width="11" />
        <line x1="172" y1="194" x2="334" y2="38" stroke="#60a5fa" stroke-width="10" />
        <line x1="196" y1="188" x2="348" y2="44" stroke="#fde047" stroke-width="9" />
        <line x1="220" y1="182" x2="360" y2="50" stroke="#7dd3fc" stroke-width="8" />
      </g>

      <!-- 交汇点 -->
      <circle cx="188" cy="108" r="22" fill="#ffffff" fill-opacity="0.9" />
      <circle cx="188" cy="108" r="10" fill="#6dd0fa" fill-opacity="0.28" />
      <circle cx="188" cy="108" r="4" fill="#409eff" />
    </svg>
  </div>
</template>

<style scoped>
.hero-convergence {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
}

.hero-convergence__svg {
  display: block;
  width: min(100%, 24rem);
  height: auto;
  overflow: visible;
}

.hero-convergence__band {
  opacity: 0.9;
}

.hero-convergence__band--rise {
  mix-blend-mode: multiply;
}

.hero-convergence__band--fall {
  mix-blend-mode: multiply;
}

.hero-convergence__band--lift {
  mix-blend-mode: multiply;
}
</style>
