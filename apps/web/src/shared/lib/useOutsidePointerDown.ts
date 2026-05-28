import { onBeforeUnmount, onMounted, type Ref } from "vue";

export function useOutsidePointerDown(
  root: Ref<HTMLElement | null>,
  onOutside: (event: PointerEvent) => void,
  enabled: () => boolean = () => true,
) {
  function handlePointerDown(event: PointerEvent) {
    if (!enabled()) {
      return;
    }

    const element = root.value;
    const target = event.target;
    if (!element || !(target instanceof Node) || element.contains(target)) {
      return;
    }

    onOutside(event);
  }

  onMounted(() => {
    document.addEventListener("pointerdown", handlePointerDown, true);
  });

  onBeforeUnmount(() => {
    document.removeEventListener("pointerdown", handlePointerDown, true);
  });
}
