<script setup lang="ts">
import { ArrowRightOutlined, BarChartOutlined, GithubOutlined, HeartFilled, TrophyFilled } from "@ant-design/icons-vue";
import { computed } from "vue";

const props = withDefaults(defineProps<{
  title: string;
  variant?: "authors" | "contributors";
  entries: Array<{
    key: string;
    name: string;
    rank: number;
    url?: string;
    authorKey?: string;
    cover?: string;
    metric: string;
    detail?: string;
    isHeartMetric?: boolean;
    sourceUrl?: string;
  }>;
  hasMore: boolean;
  moreLabel: string;
}>(), {
  variant: "authors",
});

const emit = defineEmits<{
  showGames: [authorKey: string];
  loadMore: [];
}>();

// 领奖台仅展示真实前三名；搜索后的首条结果不能变成新冠军。
const podium = computed(() => props.entries.filter((entry) => entry.rank <= 3));
const rows = computed(() => props.entries.filter((entry) => entry.rank > 3));
</script>

<template>
  <section class="catalog-leaderboard" :class="`catalog-leaderboard--${variant}`" :aria-label="title">
    <div v-if="$slots.tools" class="catalog-leaderboard__tools"><slot name="tools" /></div>
    <p v-if="!entries.length" class="catalog-leaderboard__empty" role="status">没有找到匹配的作者。</p>
    <section v-if="podium.length" class="catalog-leaderboard__panel catalog-leaderboard__panel--podium" :aria-label="`${title}前三名`">
      <header class="catalog-leaderboard__heading">
        <h2><img src="/catalog/night-arcade-v1/trophy-medal.webp" alt="" aria-hidden="true" />{{ variant === "authors" ? "TOP 3 创作者" : "TOP 3 贡献者" }}</h2>
        <p class="catalog-leaderboard__motto" aria-hidden="true"><template v-if="variant === 'authors'">PLAY INDIE <HeartFilled /> SUPPORT CREATORS</template><template v-else><HeartFilled /> CONTRIBUTORS MAKE<br />A BRIGHTER PLAYGROUND</template></p>
      </header>
      <ol class="catalog-podium" :aria-label="`${title}前三名`">
        <li v-for="entry in podium" :key="entry.key" class="catalog-podium__place" :class="`catalog-podium__place--${entry.rank}`" :data-rank="entry.rank" :value="entry.rank">
          <img v-if="entry.rank === 1" class="catalog-podium__crown" src="/catalog/night-arcade-v1/gold-crown.webp" alt="" aria-hidden="true" />
          <div class="catalog-podium__card">
            <div class="catalog-podium__art" :class="{ 'catalog-podium__art--source': entry.sourceUrl }">
              <!-- 来源贡献使用独立开源装饰，不借用作者游戏封面或推算作品数。 -->
              <GithubOutlined v-if="entry.sourceUrl" class="catalog-podium__source-art" aria-hidden="true" />
              <img v-else-if="entry.cover" :src="entry.cover" alt="" decoding="async" />
              <TrophyFilled v-else class="catalog-podium__art-fallback" aria-hidden="true" />
              <span class="catalog-podium__medal" :aria-label="`第${entry.rank}名`"><img src="/catalog/night-arcade-v1/trophy-medal.webp" alt="" aria-hidden="true" /><b aria-hidden="true">{{ entry.rank }}</b></span>
            </div>
            <div class="catalog-podium__identity">
              <a v-if="entry.url" class="catalog-podium__name" :href="entry.url" target="_blank" rel="noopener noreferrer">{{ entry.name }}</a>
              <strong v-else class="catalog-podium__name">{{ entry.name }}</strong>
              <span v-if="entry.detail" class="catalog-podium__detail">{{ entry.detail }}</span>
              <span class="catalog-podium__metric"><HeartFilled v-if="entry.isHeartMetric" aria-hidden="true" /><GithubOutlined v-else-if="entry.sourceUrl" aria-hidden="true" />{{ entry.metric }}</span>
              <a v-if="entry.sourceUrl" class="catalog-leaderboard__open" :href="entry.sourceUrl" target="_blank" rel="noopener noreferrer">查看清单 <ArrowRightOutlined aria-hidden="true" /></a>
              <button v-else-if="entry.authorKey" type="button" class="catalog-leaderboard__open" :aria-label="`查看${entry.name}的作品`" @click="emit('showGames', entry.authorKey)">查看作品 <ArrowRightOutlined aria-hidden="true" /></button>
            </div>
          </div>
          <div class="catalog-podium__step" aria-hidden="true"><span>{{ entry.rank }}</span></div>
        </li>
      </ol>
    </section>
    <section v-if="rows.length" class="catalog-leaderboard__panel catalog-leaderboard__panel--list" :aria-label="`${title}其他名次`">
      <header class="catalog-leaderboard__heading">
        <h2><BarChartOutlined aria-hidden="true" />{{ variant === "authors" ? "其他作者" : "其他贡献者" }}</h2>
        <p class="catalog-leaderboard__motto" aria-hidden="true"><template v-if="variant === 'authors'">MORE CREATORS <HeartFilled /> MORE FUN</template><template v-else>MORE CONTRIBUTIONS <HeartFilled /> A BRIGHTER TOMORROW</template></p>
      </header>
      <ol class="catalog-leaderboard__list" :aria-label="`${title}其他名次`">
        <li v-for="entry in rows" :key="entry.key" class="catalog-leaderboard__row" :class="{ 'catalog-leaderboard__row--has-cover': entry.cover || entry.sourceUrl }" :data-rank="entry.rank" :value="entry.rank">
          <span class="catalog-leaderboard__rank">{{ entry.rank }}</span>
          <div v-if="entry.sourceUrl" class="catalog-leaderboard__cover catalog-leaderboard__cover--source" aria-hidden="true"><GithubOutlined /></div>
          <img v-else-if="entry.cover" class="catalog-leaderboard__cover" :src="entry.cover" alt="" loading="lazy" decoding="async" />
          <div class="catalog-leaderboard__identity">
            <a v-if="entry.url" :href="entry.url" target="_blank" rel="noopener noreferrer">{{ entry.name }}</a><strong v-else>{{ entry.name }}</strong>
            <small v-if="entry.detail">{{ entry.detail }}</small>
          </div>
          <span class="catalog-leaderboard__metric"><HeartFilled v-if="entry.isHeartMetric" aria-hidden="true" /><GithubOutlined v-else-if="entry.sourceUrl" aria-hidden="true" />{{ entry.metric }}</span>
          <a v-if="entry.sourceUrl" class="catalog-leaderboard__open" :href="entry.sourceUrl" target="_blank" rel="noopener noreferrer">查看清单 <ArrowRightOutlined aria-hidden="true" /></a>
          <button v-else-if="entry.authorKey" type="button" class="catalog-leaderboard__open" :aria-label="`查看${entry.name}的作品`" @click="emit('showGames', entry.authorKey)">查看作品 <ArrowRightOutlined aria-hidden="true" /></button>
        </li>
      </ol>
    </section>
    <button v-if="hasMore" type="button" class="catalog-leaderboard__more" @click="emit('loadMore')">{{ moreLabel }}</button>
  </section>
</template>

<style scoped lang="scss" src="./CatalogLeaderboard.scss"></style>
