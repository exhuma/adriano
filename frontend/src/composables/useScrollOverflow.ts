/**
 * Track whether a scroll container's content currently overflows it.
 *
 * The record sidebar is a sticky, height-capped scroll region at `md`
 * and up (docs/ui-review R-01). A region that scrolls must be
 * keyboard-scrollable (WCAG 2.1.1), which needs a tab stop when its
 * own content has no focusable element at the hidden end; a region
 * that does not scroll must not be a tab stop (docs/ui-review G-10).
 * This reports which case applies so the caller can set `tabindex`
 * only when it is needed.
 */
import { onBeforeUnmount, onMounted, ref, type Ref } from "vue";

/**
 * Observe `container` and `content` and report overflow.
 *
 * :param container: The height-capped, scrollable element.
 * :param content: Its inner wrapper, whose height is the content's
 *     natural height (observed so content changes are seen even when
 *     the capped container keeps its size).
 * :returns: `true` while the content is taller than the container.
 */
export function useScrollOverflow(
  container: Ref<HTMLElement | null>,
  content: Ref<HTMLElement | null>,
): Ref<boolean> {
  const overflows = ref(false);
  let observer: ResizeObserver | null = null;

  function update(): void {
    const el = container.value;
    overflows.value = el !== null && el.scrollHeight > el.clientHeight + 1;
  }

  onMounted(() => {
    observer = new ResizeObserver(update);
    for (const el of [container.value, content.value]) {
      if (el) {
        observer.observe(el);
      }
    }
    update();
  });

  onBeforeUnmount(() => {
    observer?.disconnect();
  });

  return overflows;
}
