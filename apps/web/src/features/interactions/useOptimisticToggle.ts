import { ref, toValue, watch } from "vue";
import type { MaybeRefOrGetter } from "vue";

export interface OptimisticToggleOptions<TResponse> {
  active: MaybeRefOrGetter<boolean>;
  count: MaybeRefOrGetter<number>;
  enabled: () => boolean;
  commit: (active: boolean) => Promise<TResponse>;
  readActive: (response: TResponse) => boolean;
  readCount: (response: TResponse) => number;
  onDisabled?: () => void;
  mockWhenDisabled?: boolean;
}

export function useOptimisticToggle<TResponse>(options: OptimisticToggleOptions<TResponse>) {
  const active = ref(toValue(options.active));
  const count = ref(toValue(options.count));
  const pending = ref(false);

  watch(
    () => [toValue(options.active), toValue(options.count)] as const,
    ([nextActive, nextCount]) => {
      if (!pending.value) {
        active.value = nextActive;
        count.value = nextCount;
      }
    },
  );

  async function toggle() {
    const previousActive = active.value;
    const previousCount = count.value;
    const nextActive = !active.value;

    active.value = nextActive;
    count.value = Math.max(0, count.value + (nextActive ? 1 : -1));

    if (!options.enabled()) {
      options.onDisabled?.();
      if (options.mockWhenDisabled === false) {
        active.value = previousActive;
        count.value = previousCount;
      }
      return;
    }

    pending.value = true;
    try {
      const response = await options.commit(nextActive);
      active.value = options.readActive(response);
      count.value = options.readCount(response);
    } catch {
      active.value = previousActive;
      count.value = previousCount;
    } finally {
      pending.value = false;
    }
  }

  return {
    active,
    count,
    pending,
    toggle,
  };
}
