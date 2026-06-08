import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";

import { createEvent, deleteEvent, fetchEvents, rsvpEvent, updateEventLifecycle } from "./api";
import type {
  EventCreateRequest,
  EventItem,
  EventLifecycleRequest,
  EventRsvp,
  EventRsvpRequest,
} from "./model";

export function useEvents() {
  return useQuery<EventItem[], Error>({
    queryKey: queryKeys.events(),
    queryFn: () => fetchEvents(),
    staleTime: 30_000,
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation<EventItem, Error, EventCreateRequest>({
    mutationFn: createEvent,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

// Provide the authenticated mutation used to terminate or restore a calendar event.
// Key parameters: event id plus lifecycle payload. Return value: Vue Query mutation.
// Side effects: invalidates the events query after the API write succeeds.
export function useUpdateEventLifecycle() {
  const queryClient = useQueryClient();
  return useMutation<EventItem, Error, { eventId: string; payload: EventLifecycleRequest }>({
    mutationFn: ({ eventId, payload }) => updateEventLifecycle(eventId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

// Provide the authenticated mutation used to delete a calendar event.
// Key parameter: event id. Return value: Vue Query mutation.
// Side effects: invalidates the events query after the API write succeeds.
export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation<EventItem, Error, string>({
    mutationFn: deleteEvent,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

export function useRsvpEvent() {
  const queryClient = useQueryClient();
  return useMutation<EventRsvp, Error, { eventId: string; payload: EventRsvpRequest }>({
    mutationFn: ({ eventId, payload }) => rsvpEvent(eventId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}
