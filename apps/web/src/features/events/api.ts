import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  EventCreateRequest,
  EventItem,
  EventLifecycleRequest,
  EventRsvp,
  EventRsvpRequest,
} from "./model";

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

// Persist an event lifecycle status change, such as administrator termination.
// Key parameters: event id and lifecycle payload. Return value: updated event.
// Side effects: sends an authenticated API request.
export function updateEventLifecycle(
  eventId: string,
  payload: EventLifecycleRequest,
): Promise<EventItem> {
  return apiPut<EventItem, EventLifecycleRequest>(
    `/events/${encodeURIComponent(eventId)}/lifecycle`,
    payload,
  );
}

// Delete one event through the authenticated events API.
// Key parameter: event id. Return value: deleted event snapshot from the API.
// Side effects: sends an authenticated API request.
export function deleteEvent(eventId: string): Promise<EventItem> {
  return apiDelete<EventItem>(`/events/${encodeURIComponent(eventId)}`);
}

export function rsvpEvent(eventId: string, payload: EventRsvpRequest): Promise<EventRsvp> {
  return apiPut<EventRsvp, EventRsvpRequest>(`/events/${encodeURIComponent(eventId)}/rsvp`, payload);
}
