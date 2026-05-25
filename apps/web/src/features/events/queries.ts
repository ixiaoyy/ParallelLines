import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";

import { createEvent, fetchEvents, rsvpEvent } from "./api";
import type { EventCreateRequest, EventItem, EventRsvp, EventRsvpRequest } from "./model";

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

export function useRsvpEvent() {
  const queryClient = useQueryClient();
  return useMutation<EventRsvp, Error, { eventId: string; payload: EventRsvpRequest }>({
    mutationFn: ({ eventId, payload }) => rsvpEvent(eventId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}
