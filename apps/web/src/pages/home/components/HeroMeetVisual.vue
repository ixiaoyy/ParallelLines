<template>
  <div class="hero-meet" aria-hidden="true">
    <svg
      class="hero-meet__svg"
      viewBox="0 0 300 200"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="不同地方的人在此相遇"
    >
      <rect width="300" height="200" rx="18" fill="#f8fafc" />

      <!-- 汇聚路径 -->
      <g class="hero-meet__paths" stroke-linecap="round">
        <path d="M 58 52 C 95 78, 118 92, 150 102" stroke="#6dd0fa" stroke-width="2.2" opacity="0.55" />
        <path d="M 242 52 C 205 78, 182 92, 150 102" stroke="#fb923c" stroke-width="2.2" opacity="0.55" />
        <path d="M 58 148 C 95 122, 118 108, 150 102" stroke="#a3e635" stroke-width="2.2" opacity="0.55" />
        <path d="M 242 148 C 205 122, 182 108, 150 102" stroke="#a78bfa" stroke-width="2.2" opacity="0.55" />
      </g>

      <!-- 中心：相遇相知 -->
      <circle cx="150" cy="102" r="30" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.2" />
      <circle cx="138" cy="100" r="14" fill="#6dd0fa" fill-opacity="0.82" />
      <circle cx="162" cy="100" r="14" fill="#a3e635" fill-opacity="0.82" />
      <circle cx="150" cy="108" r="9" fill="#409eff" fill-opacity="0.35" />
      <path
        d="M 146 106 C 148 103, 152 103, 154 106 C 152 109, 148 109, 146 106 Z"
        fill="#409eff"
        fill-opacity="0.5"
      />

      <!-- 四方人物 -->
      <g class="hero-meet__person hero-meet__person--nw">
        <circle cx="58" cy="52" r="22" fill="#e0f2fe" />
        <circle cx="58" cy="46" r="7" fill="#409eff" />
        <path d="M 47 58 Q 58 66 69 58" stroke="#409eff" stroke-width="5" stroke-linecap="round" fill="none" />
      </g>
      <g class="hero-meet__person hero-meet__person--ne">
        <circle cx="242" cy="52" r="22" fill="#ffedd5" />
        <circle cx="242" cy="46" r="7" fill="#ea580c" />
        <path d="M 231 58 Q 242 66 253 58" stroke="#ea580c" stroke-width="5" stroke-linecap="round" fill="none" />
      </g>
      <g class="hero-meet__person hero-meet__person--sw">
        <circle cx="58" cy="148" r="22" fill="#ecfccb" />
        <circle cx="58" cy="142" r="7" fill="#65a30d" />
        <path d="M 47 154 Q 58 162 69 154" stroke="#65a30d" stroke-width="5" stroke-linecap="round" fill="none" />
      </g>
      <g class="hero-meet__person hero-meet__person--se">
        <circle cx="242" cy="148" r="22" fill="#ede9fe" />
        <circle cx="242" cy="142" r="7" fill="#7c3aed" />
        <path d="M 231 154 Q 242 162 253 154" stroke="#7c3aed" stroke-width="5" stroke-linecap="round" fill="none" />
      </g>

      <!-- 方位点缀 -->
      <circle cx="58" cy="52" r="3" fill="#6dd0fa" fill-opacity="0.5" />
      <circle cx="242" cy="52" r="3" fill="#fb923c" fill-opacity="0.5" />
      <circle cx="58" cy="148" r="3" fill="#a3e635" fill-opacity="0.5" />
      <circle cx="242" cy="148" r="3" fill="#a78bfa" fill-opacity="0.5" />
    </svg>
  </div>
</template>

<style scoped>
.hero-meet {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
}

.hero-meet__svg {
  display: block;
  width: min(100%, 22rem);
  height: auto;
}

.hero-meet__paths path {
  stroke-dasharray: 6 4;
  animation: hero-meet-flow 4s ease-in-out infinite;
}

.hero-meet__paths path:nth-child(2) {
  animation-delay: 0.4s;
}

.hero-meet__paths path:nth-child(3) {
  animation-delay: 0.8s;
}

.hero-meet__paths path:nth-child(4) {
  animation-delay: 1.2s;
}

@keyframes hero-meet-flow {
  0%,
  100% {
    stroke-dashoffset: 0;
    opacity: 0.45;
  }

  50% {
    stroke-dashoffset: -12;
    opacity: 0.7;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-meet__paths path {
    animation: none;
  }
}
</style>
