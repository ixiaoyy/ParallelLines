import type { components } from "@/shared/api/generated";
import { currentLocale } from "@/shared/i18n/locale";

export type EventItem = components["schemas"]["EventResponse"];
export type EventCreateRequest = components["schemas"]["EventCreateRequest"];
export type EventLifecycleRequest = components["schemas"]["EventLifecycleRequest"];
export type EventRsvpRequest = components["schemas"]["EventRsvpRequest"];
export type EventRsvp = components["schemas"]["EventRsvpResponse"];

export function localEventTime(event: EventItem): string {
  // 仅本地化卡片时间的显示，保留活动时区及起止时间数据。
  const formatter = new Intl.DateTimeFormat(currentLocale.value, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: event.timezone || undefined,
  });
  return `${formatter.format(new Date(event.start_at))} - ${formatter.format(new Date(event.end_at))}`;
}
