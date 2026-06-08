<script setup lang="ts">
import { CalendarOutlined, CloseCircleOutlined, DeleteOutlined, RedoOutlined } from "@ant-design/icons-vue";
import { computed, reactive, ref } from "vue";

import { canAccessModeration } from "@/features/auth/permissions";
import type { EventItem } from "@/features/events/model";
import { useCurrentUser } from "@/features/auth/queries";
import { localEventTime } from "@/features/events/model";
import {
  useCreateEvent,
  useDeleteEvent,
  useEvents,
  useRsvpEvent,
  useUpdateEventLifecycle,
} from "@/features/events/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const eventsQuery = useEvents();
const events = computed(() => eventsQuery.data.value ?? []);
const createEvent = useCreateEvent();
const rsvpEvent = useRsvpEvent();
const updateEventLifecycle = useUpdateEventLifecycle();
const deleteEvent = useDeleteEvent();
const eventActionStatus = ref("");
const formStatus = ref("");
const formStatusTone = ref<"error" | "success">("error");
const form = reactive({
  title: "",
  startAt: "",
  endAt: "",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
});

function submitEvent() {
  const validationMessage = eventFormValidationMessage();
  if (validationMessage) {
    formStatus.value = validationMessage;
    formStatusTone.value = "error";
    return;
  }

  const title = form.title.trim();
  const timezone = form.timezone.trim();
  createEvent.mutate(
    {
      title,
      start_at: new Date(form.startAt).toISOString(),
      end_at: new Date(form.endAt).toISOString(),
      timezone,
      description: "由日历页面创建的社区活动。",
    },
    {
      onSuccess: () => {
        form.title = "";
        form.startAt = "";
        form.endAt = "";
        formStatus.value = "活动已发布";
        formStatusTone.value = "success";
      },
      onError: () => {
        formStatus.value = "发布失败，请检查时间范围和登录状态后重试";
        formStatusTone.value = "error";
      },
    },
  );
}

// Validate the event creation form before sending it to the API.
// Key parameters: none; values are read from reactive form state. Return value:
// user-facing error text, or null when the form can be submitted. Side effects:
// none.
function eventFormValidationMessage(): string | null {
  if (!form.title.trim()) {
    return "请先填写活动标题。";
  }
  if (!form.startAt) {
    return "请选择活动开始时间。";
  }
  if (!form.endAt) {
    return "请选择活动结束时间。";
  }
  if (!form.timezone.trim()) {
    return "请填写活动时区，例如 Asia/Shanghai。";
  }

  const startAt = new Date(form.startAt);
  const endAt = new Date(form.endAt);
  if (Number.isNaN(startAt.getTime()) || Number.isNaN(endAt.getTime())) {
    return "请检查活动开始和结束时间。";
  }
  if (endAt <= startAt) {
    return "结束时间必须晚于开始时间。";
  }
  return null;
}

// Decide whether the current user can manage a specific event card.
// Key parameter: event DTO from the API. Return value: true for the creator or
// global moderators. Side effects: none.
function canManageEvent(event: EventItem): boolean {
  const user = currentUser.value;
  return Boolean(user && (user.id === event.created_by_id || canAccessModeration(user)));
}

// Build the RSVP button label from event lifecycle and current RSVP state.
// Key parameter: event DTO from the API. Return value: display text for the
// button. Side effects: none.
function eventRsvpLabel(event: EventItem): string {
  if (event.status === "canceled") {
    return "活动已终止";
  }
  return event.my_rsvp_status === "going" ? "已报名" : "报名参加";
}

// Toggle an event between active and terminated states after user confirmation.
// Key parameter: event DTO from the API. Return value: none. Side effects:
// sends an authenticated lifecycle mutation and updates page feedback.
function toggleEventLifecycle(event: EventItem) {
  if (!canManageEvent(event) || updateEventLifecycle.isPending.value) {
    return;
  }

  const nextStatus = event.status === "canceled" ? "scheduled" : "canceled";
  const confirmed = window.confirm(
    nextStatus === "canceled" ? "确定终止这个活动吗？终止后将不能继续报名。" : "确定恢复这个活动吗？",
  );
  if (!confirmed) {
    return;
  }

  updateEventLifecycle.mutate(
    { eventId: event.id, payload: { status: nextStatus } },
    {
      onSuccess: () => {
        eventActionStatus.value = nextStatus === "canceled" ? "活动已终止" : "活动已恢复";
      },
      onError: () => {
        eventActionStatus.value = "活动状态更新失败，请确认权限后重试";
      },
    },
  );
}

// Delete an event after user confirmation.
// Key parameter: event DTO from the API. Return value: none. Side effects:
// sends an authenticated delete mutation and updates page feedback.
function deleteCalendarEvent(event: EventItem) {
  if (!canManageEvent(event) || deleteEvent.isPending.value) {
    return;
  }

  const confirmed = window.confirm("确定删除这个活动吗？删除后报名记录也会一起移除。");
  if (!confirmed) {
    return;
  }

  deleteEvent.mutate(event.id, {
    onSuccess: () => {
      eventActionStatus.value = "活动已删除";
    },
    onError: () => {
      eventActionStatus.value = "删除失败，请确认权限后重试";
    },
  });
}
</script>

<template>
  <div class="events-page">
    <UiCard class="events-hero">
      <h1>社区日历</h1>
      <p>集中展示活动、报名人数、截止时间和本地时区时间；支持 iCal 订阅。</p>
      <a class="ical-link" href="/api/v1/events/calendar.ics" aria-label="订阅社区日历 iCal">
        <CalendarOutlined aria-hidden="true" />
        <span>订阅 iCal</span>
      </a>
    </UiCard>

    <UiCard v-if="currentUser" class="event-form">
      <h2>创建活动</h2>
      <form novalidate @input="formStatus = ''" @submit.prevent="submitEvent">
        <label class="event-field event-field--title">
          <span>标题</span>
          <input
            v-model="form.title"
            placeholder="活动标题"
            aria-label="活动标题"
            aria-describedby="event-form-status"
            :aria-invalid="Boolean(formStatus && formStatusTone === 'error' && !form.title.trim())"
            required
          />
        </label>
        <label class="event-field">
          <span>开始时间</span>
          <input
            v-model="form.startAt"
            type="datetime-local"
            aria-label="活动开始时间"
            aria-describedby="event-form-status"
            :aria-invalid="Boolean(formStatus && formStatusTone === 'error' && !form.startAt)"
            required
          />
        </label>
        <label class="event-field">
          <span>结束时间</span>
          <input
            v-model="form.endAt"
            type="datetime-local"
            aria-label="活动结束时间"
            aria-describedby="event-form-status"
            :aria-invalid="Boolean(formStatus && formStatusTone === 'error' && !form.endAt)"
            required
          />
        </label>
        <label class="event-field event-field--timezone">
          <span>时区</span>
          <input
            v-model="form.timezone"
            placeholder="Asia/Shanghai"
            aria-label="活动时区"
            aria-describedby="event-form-status"
            :aria-invalid="Boolean(formStatus && formStatusTone === 'error' && !form.timezone.trim())"
            required
          />
        </label>
        <UiButton class="event-form__submit" type="submit" :disabled="createEvent.isPending.value">发布活动</UiButton>
        <p
          v-if="formStatus"
          id="event-form-status"
          class="event-form-status"
          :class="`event-form-status--${formStatusTone}`"
          role="status"
        >
          {{ formStatus }}
        </p>
      </form>
    </UiCard>

    <UiCard v-if="eventsQuery.isLoading.value" class="events-state">正在加载活动…</UiCard>
    <UiCard v-else-if="eventsQuery.isError.value" class="events-state events-state--error">
      活动日历暂时不可用。
    </UiCard>
    <template v-else>
      <UiCard v-if="eventActionStatus" class="events-state" role="status">
        {{ eventActionStatus }}
      </UiCard>
      <section class="event-list" aria-label="活动列表">
        <UiCard v-for="event in events" :key="event.id" class="event-card">
          <div class="event-card__topline">
            <span class="event-time">{{ localEventTime(event) }}</span>
            <span v-if="event.status === 'canceled'" class="event-status">已终止</span>
          </div>
          <h2>{{ event.title }}</h2>
          <p>{{ event.description || "暂无活动说明。" }}</p>
          <div class="event-card__footer">
            <small>
              {{ event.timezone }} · 已报名 {{ event.going_count }}
              <template v-if="event.capacity"> / {{ event.capacity }}</template>
            </small>
            <div class="event-card__actions">
              <div v-if="canManageEvent(event)" class="event-admin-actions" aria-label="活动管理">
                <UiButton
                  tone="subtle"
                  :disabled="updateEventLifecycle.isPending.value"
                  @click="toggleEventLifecycle(event)"
                >
                  <template #icon>
                    <RedoOutlined v-if="event.status === 'canceled'" aria-hidden="true" />
                    <CloseCircleOutlined v-else aria-hidden="true" />
                  </template>
                  {{ event.status === "canceled" ? "恢复活动" : "终止活动" }}
                </UiButton>
                <UiButton
                  tone="danger"
                  :disabled="deleteEvent.isPending.value"
                  @click="deleteCalendarEvent(event)"
                >
                  <template #icon>
                    <DeleteOutlined aria-hidden="true" />
                  </template>
                  {{ deleteEvent.isPending.value ? "删除中…" : "删除" }}
                </UiButton>
              </div>
              <UiButton
                v-if="currentUser"
                class="event-rsvp-button"
                tone="subtle"
                :disabled="event.status === 'canceled' || rsvpEvent.isPending.value"
                @click="rsvpEvent.mutate({ eventId: event.id, payload: { status: 'going' } })"
              >
                {{ eventRsvpLabel(event) }}
              </UiButton>
            </div>
          </div>
        </UiCard>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss" src="./EventsPage.scss"></style>
