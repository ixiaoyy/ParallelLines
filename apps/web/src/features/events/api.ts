import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type { EventCreateRequest, EventItem, EventRsvp, EventRsvpRequest } from "./model";

export function fetchEvents(params: { startAt?: string; endAt?: string } = {}): Promise<EventItem[]> {
  const query = new URLSearchParams();
  if (params.startAt) query.set("start_at", params.startAt);
  if (params.endAt) query.set("end_at", params.endAt);
  const suffix = query.toString() ? `?${query}` : "";
  return apiGet<EventItem[]>(`/events${suffix}`);
}

export function createEvent(payload: EventCreateRequest): Promise<EventItem> {
  return apiPost<EventItem, EventCreateRequest>("/events", payload);
}

export function rsvpEvent(eventId: string, payload: EventRsvpRequest): Promise<EventRsvp> {
  return apiPut<EventRsvp, EventRsvpRequest>(`/events/${encodeURIComponent(eventId)}/rsvp`, payload);
}
