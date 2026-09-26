"use client";

import { useEffect, useRef, useState } from "react";
import { useDebouncedValue } from "@/lib/hooks/useDebouncedValue";

/**
 * The search box in the control panel.
 *
 * Typing updates the field immediately and the caller 300 ms later, so the list does
 * not refetch on every keystroke. `/` focuses it from anywhere on the page, which is
 * the shortcut Odoo users already expect.
 */
export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, 300);
  const input = useRef<HTMLInputElement>(null);
  const lastEmitted = useRef(value);

  // Tell the caller once the typing has settled.
  useEffect(() => {
    if (debounced !== lastEmitted.current) {
      lastEmitted.current = debounced;
      onChange(debounced);
    }
  }, [debounced, onChange]);

  // Follow the URL when it changes from elsewhere, e.g. "Clear filters" or a back button.
  useEffect(() => {
    if (value !== lastEmitted.current) {
      lastEmitted.current = value;
      setDraft(value);
    }
  }, [value]);

  useEffect(() => {
    const focusOnSlash = (event: KeyboardEvent) => {
      const target = event.target;
      const typingElsewhere =
        target instanceof HTMLElement &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (event.key === "/" && !typingElsewhere) {
        event.preventDefault();
        input.current?.focus();
      }
    };
    document.addEventListener("keydown", focusOnSlash);
    return () => document.removeEventListener("keydown", focusOnSlash);
  }, []);

  return (
    <div className="flex items-center gap-2 rounded border border-line bg-white px-2.5 py-1.5 focus-within:border-accent-500">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden className="text-ink-muted">
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
        <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      <input
        ref={input}
        type="search"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-ink-muted"
      />
      {draft === "" && (
        <kbd className="hidden shrink-0 rounded border border-line px-1 text-[10px] text-ink-muted sm:block">
          /
        </kbd>
      )}
    </div>
  );
}
