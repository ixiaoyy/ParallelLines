<template>
  <!-- 游戏独立加载，避免原页面的全局样式影响论坛及其他游戏。 -->
  <iframe
    class="melon-game-page"
    src="/games/melon/index.html"
    title="瓜体实验室 · 半流体西瓜游戏"
  />
</template>

<style scoped>
.melon-game-page {
  display: block;
  width: 100%;
  height: 100vh;
  height: 100dvh;
  border: 0;
  background: #f1f2ff;
}
</style>
