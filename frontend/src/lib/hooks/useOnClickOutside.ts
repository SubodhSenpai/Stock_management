"use client";

import { useEffect, type RefObject } from "react";

/**
 * Close a dropdown when the user clicks away or presses Escape.
 *
 * Used by the nav menus, the user menu and the product picker, so all three dismiss the
 * same way.
 */
export function useOnClickOutside(
  ref: RefObject<HTMLElement | null>,
  onDismiss: () => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return;

    const handlePointer = (event: MouseEvent | TouchEvent) => {
      const target = event.target;
      if (target instanceof Node && !ref.current?.contains(target)) onDismiss();
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDismiss();
    };

    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("touchstart", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("touchstart", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [enabled, onDismiss, ref]);
}
