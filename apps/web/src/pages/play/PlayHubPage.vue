<script setup lang="ts">
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  CompassOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { requestFableSpaceSsoTicket } from "@/features/auth/api";
import { useCurrentUser } from "@/features/auth/queries";
import { match3LaunchUrl } from "@/features/play/products";
import { staticAssetUrl } from "@/shared/assets/staticAssets";

const router = useRouter();
const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const openingPrivateSpace = ref(false);
const privateSpaceImageUrl = staticAssetUrl("/private-space-entry-b7d15288.png");
const match3Url = match3LaunchUrl("play-hub");

// Sends guests to authentication and signed-in users through the existing one-time SSO handoff.
// Parameters: none. Return value resolves after routing, redirect, or error feedback; side effect changes browser location.
async function openPrivateSpace(): Promise<void> {
  if (!currentUser.value) {
    await router.push({ name: "auth", query: { redirect: "/play" } });
    return;
  }
  if (openingPrivateSpace.value) {
    return;
  }

  openingPrivateSpace.value = true;
  try {
    const ticket = await requestFableSpaceSsoTicket();
    window.location.assign(ticket.redirect_url);
  } catch {
    message.error("私密空间暂时无法进入，请稍后再试");
    openingPrivateSpace.value = false;
  }
}
</script>

<template>
  <div class="play-hub-page">
    <header class="play-hub-hero">
      <div class="play-hub-hero__copy">
        <span>PARALLEL PLAYGROUND · 02 WORLDS ONLINE</span>
        <h1>两条世界线，<br />等你进入。</h1>
        <p>这里收集平行线正在生长的可玩项目。保留各自的世界观与玩法，从同一个入口出发。</p>
        <div class="play-hub-hero__facts" aria-label="游乐场信息">
          <span><CheckCircleOutlined aria-hidden="true" />2 个项目已开放</span>
          <span><SafetyCertificateOutlined aria-hidden="true" />私密空间安全登录</span>
        </div>
      </div>

      <div class="play-hub-orbit" aria-hidden="true">
        <div class="play-hub-orbit__ring"></div>
        <div class="play-hub-orbit__world play-hub-orbit__world--fable"><i></i></div>
        <div class="play-hub-orbit__world play-hub-orbit__world--match">
          <i></i><i></i><i></i><i></i>
        </div>
        <span>PLAY</span>
      </div>
    </header>

    <main class="product-grid" aria-label="可玩项目">
      <article class="product-card product-card--fable">
        <div class="product-card__visual">
          <img :src="privateSpaceImageUrl" alt="" width="1008" height="576" decoding="async" />
          <span class="product-card__number">01</span>
          <span class="product-card__state"><i></i>已开放</span>
        </div>
        <div class="product-card__body">
          <div class="product-card__meta">
            <span>叙事空间</span>
            <span>账号互通</span>
          </div>
          <h2>私密空间</h2>
          <p>一处更安静、更具沉浸感的独立空间。用你的平行线账号进入，继续探索属于自己的故事。</p>
          <ul>
            <li><LockOutlined aria-hidden="true" />登录用户均可体验</li>
            <li><CompassOutlined aria-hidden="true" />一次性 SSO 安全跳转</li>
          </ul>
          <button
            class="product-card__cta"
            type="button"
            :disabled="openingPrivateSpace"
            :aria-busy="openingPrivateSpace"
            @click="openPrivateSpace"
          >
            {{ openingPrivateSpace ? "正在进入…" : currentUser ? "进入私密空间" : "登录后进入" }}
            <ArrowRightOutlined aria-hidden="true" />
          </button>
        </div>
      </article>

      <article class="product-card product-card--match">
        <div class="product-card__visual match-board">
          <span class="product-card__number">02</span>
          <span class="product-card__state"><i></i>公开游玩</span>
          <div class="match-board__grid" aria-hidden="true">
            <i></i><i></i><i></i><i></i>
            <i></i><i></i><i></i><i></i>
            <i></i><i></i><i></i><i></i>
          </div>
          <div class="match-board__score">
            <small>NEXT MOVE</small>
            <strong>+ 300</strong>
          </div>
        </div>
        <div class="product-card__body">
          <div class="product-card__meta">
            <span>休闲益智</span>
            <span>无需登录</span>
          </div>
          <h2>平行消消乐</h2>
          <p>随时开一局的轻量消除游戏。观察色块、连出组合，让忙碌的思绪在几分钟里重新排好队。</p>
          <ul>
            <li><ThunderboltOutlined aria-hidden="true" />打开即玩，无需注册</li>
            <li><CheckCircleOutlined aria-hidden="true" />独立站点，适配移动端</li>
          </ul>
          <a class="product-card__cta" :href="match3Url">
            开始消消乐
            <ArrowRightOutlined aria-hidden="true" />
          </a>
        </div>
      </article>
    </main>

    <footer class="play-hub-footer">
      <span>更多世界正在接近交点</span>
      <p>新的实验、故事和小游戏会继续从这里开放。</p>
    </footer>
  </div>
</template>

<style scoped lang="scss" src="./PlayHubPage.scss"></style>
