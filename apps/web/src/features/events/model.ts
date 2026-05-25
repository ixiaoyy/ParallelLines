import type { components } from "@/shared/api/generated";

export type EventItem = components["schemas"]["EventResponse"];
export type EventCreateRequest = components["schemas"]["EventCreateRequest"];
export type EventRsvpRequest = components["schemas"]["EventRsvpRequest"];
export type EventRsvp = components["schemas"]["EventRsvpResponse"];

export function localEventTime(event: EventItem): string {
  const formatter = new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: event.timezone || undefined,
  });
  return `${formatter.format(new Date(event.start_at))} - ${formatter.format(new Date(event.end_at))}`;
}
