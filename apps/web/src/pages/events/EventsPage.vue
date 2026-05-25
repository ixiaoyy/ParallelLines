<script setup lang="ts">
import { computed, reactive } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import { localEventTime } from "@/features/events/model";
import { useCreateEvent, useEvents, useRsvpEvent } from "@/features/events/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const eventsQuery = useEvents();
const events = computed(() => eventsQuery.data.value ?? []);
const createEvent = useCreateEvent();
const rsvpEvent = useRsvpEvent();
const form = reactive({
  title: "",
  startAt: "",
  endAt: "",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
});

function submitEvent() {
  if (!form.title || !form.startAt || !form.endAt) {
    return;
  }
  createEvent.mutate(
    {
      title: form.title,
      start_at: new Date(form.startAt).toISOString(),
      end_at: new Date(form.endAt).toISOString(),
      timezone: form.timezone,
      description: "由日历页面创建的社区活动。",
    },
    {
      onSuccess: () => {
        form.title = "";
        form.startAt = "";
        form.endAt = "";
      },
    },
  );
}
</script>

<template>
  <div class="events-page">
    <UiCard class="events-hero">
      <h1>社区日历</h1>
      <p>集中展示活动、报名人数、截止时间和本地时区时间；支持 iCal 订阅。</p>
      <a class="ical-link" href="/api/v1/events/calendar.ics">订阅 iCal</a>
    </UiCard>

    <UiCard v-if="currentUser" class="event-form">
      <h2>创建活动</h2>
      <form @submit.prevent="submitEvent">
        <input v-model="form.title" placeholder="活动标题" />
        <input v-model="form.startAt" type="datetime-local" />
        <input v-model="form.endAt" type="datetime-local" />
        <input v-model="form.timezone" placeholder="Asia/Shanghai" />
        <UiButton type="submit" :disabled="createEvent.isPending.value">发布活动</UiButton>
      </form>
    </UiCard>

    <UiCard v-if="eventsQuery.isLoading.value" class="events-state">正在加载活动…</UiCard>
    <UiCard v-else-if="eventsQuery.isError.value" class="events-state events-state--error">
      活动日历暂时不可用。
    </UiCard>
    <section v-else class="event-list" aria-label="活动列表">
      <UiCard v-for="event in events" :key="event.id" class="event-card">
        <span class="event-time">{{ localEventTime(event) }}</span>
        <h2>{{ event.title }}</h2>
        <p>{{ event.description || "暂无活动说明。" }}</p>
        <small>
          {{ event.timezone }} · 已报名 {{ event.going_count }}
          <template v-if="event.capacity"> / {{ event.capacity }}</template>
        </small>
        <UiButton
          v-if="currentUser"
          tone="subtle"
          :disabled="rsvpEvent.isPending.value"
          @click="rsvpEvent.mutate({ eventId: event.id, payload: { status: 'going' } })"
        >
          {{ event.my_rsvp_status === "going" ? "已报名" : "报名参加" }}
        </UiButton>
      </UiCard>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./EventsPage.scss"></style>
