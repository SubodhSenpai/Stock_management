"use client";

import { useEffect, useState } from "react";

/**
 * Follow a value, but only after it has stopped changing.
 *
 * Search boxes use this so a typed word is one request rather than one per keystroke.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
