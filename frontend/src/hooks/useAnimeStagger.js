import { useEffect, useRef } from "react";
import anime from "animejs";

/**
 * Staggered fade-up entry for child elements.
 * Mark children with data-stagger="" to opt in.
 * Re-triggers when any value in `deps` changes (e.g. data loaded).
 *
 * Usage:
 *   const listRef = useAnimeStagger([findings]);
 *   <ul ref={listRef}>
 *     {items.map(item => <li key={item.id} data-stagger="">...</li>)}
 *   </ul>
 */
export function useAnimeStagger(deps = []) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    const items = ref.current.querySelectorAll("[data-stagger]");
    if (!items.length) return;

    // Reset before animating so re-triggers look clean
    anime.set(items, { opacity: 0, translateY: 10 });

    anime({
      targets: items,
      opacity: [0, 1],
      translateY: [10, 0],
      duration: 280,
      delay: anime.stagger(32, { start: 40 }),
      easing: "cubicBezier(0.16, 1, 0.30, 1)",
    });
  // deps is intentionally dynamic - caller controls when to re-trigger
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return ref;
}
