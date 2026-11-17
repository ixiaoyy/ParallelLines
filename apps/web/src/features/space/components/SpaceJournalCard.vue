<script setup lang="ts">
import { computed } from "vue";

import { resolveApiAssetUrl } from "@/shared/api/client";
import UiAvatar from "@/shared/ui/Avatar.vue";

import {
  formatCentsToYuan,
  getLedgerCategoryMeta,
  getMoodMeta,
  getWeatherMeta,
  SPACE_REACTIONS,
  type SpaceChecklistItem,
  type SpaceJournalItem,
  type SpaceReactionKind,
} from "../model";

const props = withDefaults(
  defineProps<{
    entry: SpaceJournalItem;
    editable?: boolean;
    showAuthor?: boolean;
    showFollow?: boolean;
    isFollowing?: boolean;
    followBusy?: boolean;
  }>(),
  {
    editable: false,
    showAuthor: false,
    showFollow: false,
    isFollowing: false,
    followBusy: false,
  },
);

const emit = defineEmits<{
  togglePin: [entry: SpaceJournalItem];
  toggleVisibility: [entry: SpaceJournalItem];
  toggleChecklist: [entry: SpaceJournalItem, itemId: string];
  toggleFollow: [entry: SpaceJournalItem];
  like: [entry: SpaceJournalItem];
  react: [entry: SpaceJournalItem, kind: SpaceReactionKind];
  remove: [entry: SpaceJournalItem];
  selectTag: [tag: string];
}>();

const moodMeta = computed(() => getMoodMeta(props.entry.mood));
const weatherMeta = computed(() => getWeatherMeta(props.entry.weather));

const formattedDayParts = computed(() => {
  const parts = props.entry.entry_date.split("-");
  const month = parts[1] ?? "01";
  const day = parts[2] ?? "01";
  return {
    day,
    monthLabel: `${Number(month)}月`,
    full: props.entry.entry_date,
  };
});

const checklistProgress = computed(() => {
  const list = props.entry.checklist ?? [];
  if (!list.length) return null;
  const doneCount = list.filter((item) => item.done).length;
  return {
    doneCount,
    total: list.length,
    percent: Math.round((doneCount * 100) / list.length),
  };
});

const singleLedgerMeta = computed(() => {
  const snap = props.entry.ledger_snapshot?.single_entry;
  if (!snap) return null;
  return {
    ...snap,
    meta: getLedgerCategoryMeta(snap.category),
  };
});

function handleChecklistClick(item: SpaceChecklistItem) {
  if (!props.editable) return;
  emit("toggleChecklist", props.entry, item.id);
}
</script>

<template>
  <article
    class="space-journal-card"
    :class="[
      `space-journal-card--${entry.card_theme || 'paper'}`,
      { 'is-pinned': entry.is_pinned },
    ]"
  >
    <div class="space-journal-card__tape" aria-hidden="true"></div>

    <header class="space-journal-card__header">
      <div class="space-journal-card__date-stamp" :title="formattedDayParts.full">
        <strong>{{ formattedDayParts.day }}</strong>
        <span>{{ formattedDayParts.monthLabel }}</span>
      </div>

      <div class="space-journal-card__meta-main">
        <div v-if="showAuthor && entry.author" class="space-journal-card__author">
          <RouterLink
            class="space-journal-card__author-link"
            :to="{ name: 'user-profile', params: { id: entry.author.id } }"
          >
            <UiAvatar
              :name="entry.author.display_name || entry.author.username"
              :src="resolveApiAssetUrl(entry.author.avatar_url)"
              size="sm"
            />
            <strong>{{ entry.author.display_name || entry.author.username }}</strong>
            <span>@{{ entry.author.username }}</span>
            <em v-if="entry.author.current_status" class="space-journal-card__author-status">
              {{ entry.author.current_status }}
            </em>
          </RouterLink>
          <button
            v-if="showFollow"
            type="button"
            class="space-journal-card__follow-btn"
            :class="{ 'is-following': isFollowing }"
            :disabled="followBusy"
            @click="emit('toggleFollow', entry)"
          >
            {{ isFollowing ? "已关注" : "+ 关注" }}
          </button>
        </div>

        <div class="space-journal-card__stickers">
          <span
            class="space-sticker space-sticker--mood"
            :style="{ '--sticker-fg': moodMeta.color, '--sticker-bg': moodMeta.softBg }"
          >
            <em>{{ moodMeta.emoji }}</em>
            <b>{{ moodMeta.label }}</b>
          </span>

          <span class="space-sticker space-sticker--weather">
            <em>{{ weatherMeta.emoji }}</em>
            <b>{{ weatherMeta.label }}</b>
          </span>

          <span v-if="entry.location" class="space-sticker space-sticker--location">
            <em>📍</em>
            <b>{{ entry.location }}</b>
          </span>

          <span v-if="entry.is_pinned" class="space-sticker space-sticker--pin">
            <em>📌</em>
            <b>置顶手账</b>
          </span>

          <span
            class="space-sticker space-sticker--vis"
            :class="entry.visibility === 'private' ? 'is-private' : 'is-public'"
          >
            <em>{{ entry.visibility === "private" ? "🔒" : entry.visibility === "friends" ? "👥" : "🌐" }}</em>
            <b>{{ entry.visibility === "private" ? "仅自己" : entry.visibility === "friends" ? "互关好友" : "公开" }}</b>
          </span>

          <span v-if="entry.unlock_at" class="space-sticker space-sticker--capsule">
            <em>⏳</em>
            <b>{{ entry.is_locked ? `${entry.unlock_at} 拆封` : `已拆封` }}</b>
          </span>
        </div>
      </div>
    </header>

    <div v-if="entry.is_locked" class="space-journal-card__capsule-seal">
      <span class="capsule-wax" aria-hidden="true">💌</span>
      <div>
        <strong>封存中的时间胶囊</strong>
        <p>写给未来自己的信，将于 <b>{{ entry.unlock_at }}</b> 自动拆封展示。</p>
      </div>
    </div>

    <div v-else class="space-journal-card__body">
      <h3 v-if="entry.title" class="space-journal-card__title">{{ entry.title }}</h3>
      <p class="space-journal-card__content">{{ entry.content }}</p>

      <!-- 内嵌打卡/待办清单 -->
      <div v-if="entry.checklist && entry.checklist.length" class="space-journal-card__checklist">
        <div class="space-journal-card__checklist-head">
          <span>小目标打卡</span>
          <em v-if="checklistProgress">
            {{ checklistProgress.doneCount }} / {{ checklistProgress.total }}（{{ checklistProgress.percent }}%）
          </em>
        </div>
        <ul>
          <li
            v-for="item in entry.checklist"
            :key="item.id"
            :class="{ 'is-done': item.done, 'is-interactive': editable }"
            @click="handleChecklistClick(item)"
          >
            <span class="space-check-box" aria-hidden="true">{{ item.done ? "✓" : "" }}</span>
            <span class="space-check-text">{{ item.text }}</span>
          </li>
        </ul>
      </div>

      <!-- 内嵌单笔账单快照 -->
      <div v-if="singleLedgerMeta" class="space-journal-card__ledger-pill">
        <span
          class="space-ledger-pill__icon"
          :style="{ backgroundColor: singleLedgerMeta.meta.softBg, color: singleLedgerMeta.meta.color }"
        >
          {{ singleLedgerMeta.meta.emoji }}
        </span>
        <div class="space-ledger-pill__info">
          <strong>{{ singleLedgerMeta.meta.label }}</strong>
          <span v-if="singleLedgerMeta.note">{{ singleLedgerMeta.note }}</span>
        </div>
        <b
          class="space-ledger-pill__amount"
          :class="singleLedgerMeta.kind === 'income' ? 'is-income' : 'is-expense'"
        >
          {{
            formatCentsToYuan(
              singleLedgerMeta.kind === "income"
                ? singleLedgerMeta.amount_cents
                : -singleLedgerMeta.amount_cents,
              true,
            )
          }}
        </b>
      </div>

      <!-- 内嵌月度收支小结卡 -->
      <div
        v-else-if="entry.ledger_snapshot && entry.ledger_snapshot.month"
        class="space-journal-card__monthly-bill"
      >
        <div class="space-monthly-bill__head">
          <span>📊 {{ entry.ledger_snapshot.month }} 账单小结卡</span>
          <em>共 {{ entry.ledger_snapshot.entry_count ?? 0 }} 笔记录</em>
        </div>
        <div v-if="!entry.ledger_snapshot.hide_exact_amount" class="space-monthly-bill__totals">
          <div>
            <span>当月支出</span>
            <strong>{{ formatCentsToYuan(entry.ledger_snapshot.total_expense_cents ?? 0) }}</strong>
          </div>
          <div v-if="entry.ledger_snapshot.total_income_cents">
            <span>当月收入</span>
            <strong class="is-income">
              {{ formatCentsToYuan(entry.ledger_snapshot.total_income_cents ?? 0, true) }}
            </strong>
          </div>
        </div>
        <div
          v-if="entry.ledger_snapshot.top_categories?.length"
          class="space-monthly-bill__bars"
        >
          <div
            v-for="cat in entry.ledger_snapshot.top_categories"
            :key="cat.category"
            class="space-monthly-bill__bar-row"
          >
            <span class="bar-label">
              {{ getLedgerCategoryMeta(cat.category).emoji }}
              {{ getLedgerCategoryMeta(cat.category).label }}
            </span>
            <div class="bar-track">
              <i
                :style="{
                  width: `${Math.min(100, Math.max(6, cat.ratio_percent))}%`,
                  backgroundColor: getLedgerCategoryMeta(cat.category).color,
                }"
              ></i>
            </div>
            <b class="bar-pct">{{ cat.ratio_percent }}%</b>
          </div>
        </div>
      </div>

      <!-- 配图九宫格 -->
      <div
        v-if="entry.media_urls && entry.media_urls.length"
        class="space-journal-card__media"
        :class="`cols-${Math.min(3, entry.media_urls.length)}`"
      >
        <a
          v-for="(imgUrl, idx) in entry.media_urls"
          :key="`${imgUrl}-${idx}`"
          :href="resolveApiAssetUrl(imgUrl)"
          target="_blank"
          rel="noopener noreferrer"
          class="space-journal-card__photo"
        >
          <img
            :src="resolveApiAssetUrl(imgUrl)"
            alt="手账配图"
            loading="lazy"
            decoding="async"
          />
        </a>
      </div>

      <!-- 标签胶囊 -->
      <div v-if="entry.tags && entry.tags.length" class="space-journal-card__tags">
        <button
          v-for="tag in entry.tags"
          :key="tag"
          type="button"
          class="space-tag-chip"
          @click="emit('selectTag', tag)"
        >
          #{{ tag }}
        </button>
      </div>
    </div>

    <footer class="space-journal-card__footer">
      <div class="space-journal-card__reactions">
        <button
          v-for="r in SPACE_REACTIONS"
          :key="r.key"
          type="button"
          class="space-card-action space-card-action--reaction"
          :class="{ 'has-count': (entry.reactions?.[r.key] ?? 0) > 0 }"
          :title="r.label"
          @click="emit('react', entry, r.key)"
        >
          <span aria-hidden="true">{{ r.emoji }}</span>
          <small>{{ r.label }}</small>
          <b v-if="(entry.reactions?.[r.key] ?? 0) > 0">{{ entry.reactions?.[r.key] }}</b>
        </button>
      </div>

      <div v-if="editable" class="space-journal-card__owner-actions">
        <button
          type="button"
          class="space-card-action"
          :title="entry.is_pinned ? '取消置顶' : '置顶此篇手账'"
          @click="emit('togglePin', entry)"
        >
          {{ entry.is_pinned ? "取消置顶" : "📌 置顶" }}
        </button>
        <button
          type="button"
          class="space-card-action"
          :title="entry.visibility === 'private' ? '设为公开到空间' : '设为仅自己可见'"
          @click="emit('toggleVisibility', entry)"
        >
          {{ entry.visibility === "private" ? "🌐 设为公开" : "🔒 设为私密" }}
        </button>
        <button
          type="button"
          class="space-card-action space-card-action--danger"
          @click="emit('remove', entry)"
        >
          删除
        </button>
      </div>
    </footer>
  </article>
</template>

<style scoped lang="scss">
.space-journal-card {
  position: relative;
  display: grid;
  gap: 0.9rem;
  padding: 1.25rem 1.25rem 1.05rem;
  border-radius: 1.25rem;
  border: 1px solid var(--border);
  background: #fffdf9;
  box-shadow: 0 8px 24px rgba(51, 65, 85, 0.06);
  transition:
    transform 180ms ease,
    box-shadow 180ms ease,
    border-color 180ms ease;
  overflow: hidden;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(51, 65, 85, 0.09);
  }

  &.is-pinned {
    border-color: color-mix(in srgb, var(--primary) 38%, var(--border));
  }
}

.space-journal-card__author {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.space-journal-card__follow-btn {
  flex-shrink: 0;
  padding: 0.2rem 0.65rem;
  border: 1px solid var(--theme-soft-border, rgba(64, 158, 255, 0.35));
  border-radius: var(--radius-pill);
  background: var(--theme-soft-bg, rgba(64, 158, 255, 0.1));
  color: var(--primary);
  font-size: 0.72rem;
  font-weight: 800;
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

  &.is-following {
    border-color: var(--border);
    background: var(--bg-subtle);
    color: var(--muted);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.space-journal-card__author-status {
  font-style: normal;
  padding: 0.1rem 0.5rem;
  border-radius: var(--radius-pill);
  background: var(--theme-soft-bg, rgba(64, 158, 255, 0.1));
  color: var(--primary);
  font-size: 0.7rem;
  font-weight: 800;
}

.space-sticker--capsule {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.space-journal-card__capsule-seal {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 1.1rem 1rem;
  border-radius: 1rem;
  border: 1px dashed rgba(245, 158, 11, 0.45);
  background: linear-gradient(135deg, rgba(255, 251, 235, 0.9), rgba(254, 243, 199, 0.45));

  .capsule-wax {
    font-size: 1.8rem;
    line-height: 1;
  }

  strong {
    font-size: 0.92rem;
    color: #92400e;
  }

  p {
    margin: 0.2rem 0 0;
    font-size: 0.8rem;
    color: #b45309;
  }
}

.space-journal-card__reactions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.space-card-action--reaction {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.24rem 0.58rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.72);
  font-size: 0.74rem;

  small { font-size: 0.72rem; color: var(--text); font-weight: 700; }
  b { color: var(--primary); font-weight: 900; }

  &.has-count {
    border-color: var(--theme-soft-border, rgba(64, 158, 255, 0.35));
    background: var(--theme-soft-bg, rgba(64, 158, 255, 0.08));
  }
}

.space-journal-card--paper {
  background: linear-gradient(180deg, #fffdf9 0%, #ffffff 100%);
}

.space-journal-card--grid {
  background-color: #fcfdff;
  background-image:
    linear-gradient(to right, rgba(148, 163, 184, 0.11) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(148, 163, 184, 0.11) 1px, transparent 1px);
  background-size: 20px 20px;
}

.space-journal-card--sky {
  background: linear-gradient(165deg, #f0f9ff 0%, #ffffff 68%);
  border-color: #bae6fd;
}

.space-journal-card--mint {
  background: linear-gradient(165deg, #f0fdf4 0%, #ffffff 68%);
  border-color: #bbf7d0;
}

.space-journal-card--sunset {
  background: linear-gradient(165deg, #fff7ed 0%, #ffffff 68%);
  border-color: #fed7aa;
}

.space-journal-card--lavender {
  background: linear-gradient(165deg, #f5f3ff 0%, #ffffff 68%);
  border-color: #ddd6fe;
}

.space-journal-card__tape {
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%) rotate(-1.5deg);
  width: 4.6rem;
  height: 1.15rem;
  border-radius: 3px;
  background: rgba(64, 158, 255, 0.14);
  border: 1px dashed rgba(64, 158, 255, 0.28);
  pointer-events: none;
}

.space-journal-card__header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.85rem;
  align-items: center;
}

.space-journal-card__date-stamp {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 3.1rem;
  height: 3.1rem;
  border-radius: 0.9rem;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  box-shadow: 0 2px 8px rgba(51, 65, 85, 0.05);
  line-height: 1.05;

  strong {
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--title);
  }

  span {
    margin-top: 0.12rem;
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--muted);
  }
}

.space-journal-card__meta-main {
  display: grid;
  gap: 0.42rem;
  min-width: 0;
}

.space-journal-card__author-link {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  text-decoration: none;
  color: var(--title);

  strong {
    font-size: 0.9rem;
    font-weight: 700;
  }

  span {
    font-size: 0.78rem;
    color: var(--muted);
  }
}

.space-journal-card__stickers {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-items: center;
}

.space-sticker {
  display: inline-flex;
  align-items: center;
  gap: 0.26rem;
  padding: 0.2rem 0.56rem;
  border-radius: var(--radius-pill);
  font-size: 0.75rem;
  font-weight: 700;
  background: rgba(241, 245, 249, 0.85);
  color: var(--text);

  em {
    font-style: normal;
    font-size: 0.85rem;
    line-height: 1;
  }

  b {
    font-weight: 700;
  }
}

.space-sticker--mood {
  background: var(--sticker-bg, #fff7ed);
  color: var(--sticker-fg, #ea580c);
}

.space-sticker--pin {
  background: #fef3c7;
  color: #b45309;
}

.space-sticker--vis.is-private {
  background: #f1f5f9;
  color: #64748b;
}

.space-sticker--vis.is-public {
  background: rgba(64, 158, 255, 0.12);
  color: var(--primary);
}

.space-journal-card__body {
  display: grid;
  gap: 0.72rem;
}

.space-journal-card__title {
  margin: 0;
  font-size: 1.04rem;
  font-weight: 800;
  color: var(--title);
  line-height: 1.4;
}

.space-journal-card__content {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.72;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
}

.space-journal-card__checklist {
  display: grid;
  gap: 0.45rem;
  padding: 0.72rem 0.85rem;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.78);
  border: 1px dashed var(--border-strong);

  &-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.76rem;
    font-weight: 700;
    color: var(--muted);

    em {
      font-style: normal;
      color: var(--primary);
    }
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.36rem;
  }

  li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.86rem;
    color: var(--title);

    &.is-interactive {
      cursor: pointer;
    }

    &.is-done .space-check-text {
      text-decoration: line-through;
      color: var(--muted);
    }

    &.is-done .space-check-box {
      background: var(--primary);
      border-color: var(--primary);
      color: #ffffff;
    }
  }
}

.space-check-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 0.32rem;
  border: 1.5px solid var(--border-strong);
  font-size: 0.72rem;
  font-weight: 800;
  flex-shrink: 0;
}

.space-journal-card__ledger-pill {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.62rem 0.82rem;
  border-radius: 0.9rem;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid var(--border);
}

.space-ledger-pill__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.1rem;
  height: 2.1rem;
  border-radius: 0.65rem;
  font-size: 1.05rem;
  flex-shrink: 0;
}

.space-ledger-pill__info {
  display: grid;
  min-width: 0;
  flex: 1;

  strong {
    font-size: 0.84rem;
    color: var(--title);
  }

  span {
    font-size: 0.76rem;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.space-ledger-pill__amount {
  font-size: 0.96rem;
  font-weight: 800;

  &.is-expense {
    color: #ea580c;
  }

  &.is-income {
    color: #10b981;
  }
}

.space-journal-card__monthly-bill {
  display: grid;
  gap: 0.65rem;
  padding: 0.85rem 0.95rem;
  border-radius: 0.95rem;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border);
}

.space-monthly-bill__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  font-weight: 800;
  color: var(--title);

  em {
    font-style: normal;
    font-weight: 600;
    color: var(--muted);
  }
}

.space-monthly-bill__totals {
  display: flex;
  gap: 1.2rem;

  div {
    display: grid;
    gap: 0.1rem;
  }

  span {
    font-size: 0.73rem;
    color: var(--muted);
  }

  strong {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--title);

    &.is-income {
      color: #10b981;
    }
  }
}

.space-monthly-bill__bars {
  display: grid;
  gap: 0.38rem;
}

.space-monthly-bill__bar-row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr) 2.5rem;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.76rem;

  .bar-label {
    color: var(--text);
    font-weight: 600;
    white-space: nowrap;
  }

  .bar-track {
    height: 0.42rem;
    border-radius: 999px;
    background: var(--bg-subtle);
    overflow: hidden;

    i {
      display: block;
      height: 100%;
      border-radius: 999px;
    }
  }

  .bar-pct {
    text-align: right;
    color: var(--muted);
  }
}

.space-journal-card__media {
  display: grid;
  gap: 0.5rem;

  &.cols-1 {
    grid-template-columns: minmax(0, 280px);
  }

  &.cols-2 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  &.cols-3 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.space-journal-card__photo {
  display: block;
  aspect-ratio: 4 / 3;
  border-radius: 0.8rem;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--bg-subtle);

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
}

.space-journal-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
}

.space-tag-chip {
  padding: 0.18rem 0.56rem;
  border-radius: var(--radius-pill);
  border: 1px solid rgba(64, 158, 255, 0.22);
  background: var(--theme-soft-bg, rgba(64, 158, 255, 0.1));
  color: var(--primary);
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 150ms ease;

  &:hover {
    background: var(--theme-soft-bg-hover, rgba(64, 158, 255, 0.18));
  }
}

.space-journal-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-top: 0.65rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.28);
}

.space-journal-card__owner-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.space-card-action {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  padding: 0.26rem 0.62rem;
  border-radius: var(--radius-pill);
  border: 1px solid transparent;
  background: rgba(241, 245, 249, 0.8);
  color: var(--text);
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 150ms ease,
    color 150ms ease;

  &:hover {
    background: var(--bg-selected);
    color: var(--primary);
  }

  &--like b {
    font-weight: 800;
  }

  &--danger:hover {
    background: var(--danger-bg);
    color: var(--danger);
  }
}

@media (max-width: 640px) {
  .space-journal-card {
    padding: 1rem 0.92rem 0.88rem;
    border-radius: 1.05rem;
  }

  .space-journal-card__date-stamp {
    min-width: 2.75rem;
    height: 2.75rem;
  }
}
</style>
