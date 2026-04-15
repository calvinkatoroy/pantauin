import { useEffect, useRef } from "react";
import anime from "animejs";

/**
 * Mechanical neon-flicker effect on a DOM element.
 * Re-triggers whenever `trigger` changes (e.g. current pathname).
 *
 * Usage:
 *   const flickerRef = useAnimeFlicker(pathname);
 *   <span ref={flickerRef}>Active Label</span>
 */
export function useAnimeFlicker(trigger) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current) return;
    // Simulate a fluorescent tube striking - 6-step opacity stutter
    anime({
      targets: ref.current,
      opacity: [0.15, 1, 0.45, 1, 0.72, 1],
      duration: 320,
      easing: "steps(6)",
    });
  }, [trigger]);

  return ref;
}
