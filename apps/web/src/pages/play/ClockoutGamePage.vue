<template>
  <!-- 原游戏独占视口，隔离其固定定位与全局样式，并保留游戏内的全屏操作。 -->
  <iframe
    class="clockout-game-page"
    src="/games/clockout/index.html"
    title="准点下班 · 18 关完整版"
    allow="fullscreen"
    allowfullscreen
  />
</template>

<style scoped>
.clockout-game-page {
  display: block;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  border: 0;
  background: #0d252e;
}
</style>
