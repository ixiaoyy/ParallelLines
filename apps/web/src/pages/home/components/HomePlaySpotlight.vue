<script setup lang="ts">
import { ArrowRightOutlined } from "@ant-design/icons-vue";
</script>

<template>
  <section class="home-play-spotlight" aria-labelledby="home-play-title">
    <div class="home-play-spotlight__copy">
      <span>PLAYGROUND · NEW</span>
      <h2 id="home-play-title">讨论之外，也一起玩一会儿。</h2>
      <p>两个独立世界已经开放：进入私密空间展开故事，或来一局轻松的消消乐。</p>
      <RouterLink :to="{ name: 'play-hub' }">
        探索游乐场
        <ArrowRightOutlined aria-hidden="true" />
      </RouterLink>
    </div>

    <div class="home-play-spotlight__worlds" aria-hidden="true">
      <div class="mini-world mini-world--fable">
        <span>01</span>
        <strong>私密空间</strong>
        <i></i>
      </div>
      <div class="world-connector">
        <span></span><span></span><span></span>
      </div>
      <div class="mini-world mini-world--match">
        <span>02</span>
        <strong>消消乐</strong>
        <div><i></i><i></i><i></i><i></i></div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./HomePlaySpotlight.scss"></style>
