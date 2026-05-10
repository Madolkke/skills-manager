"use client";

export function GlobalCommandButton() {
  return (
    <button
      aria-label="Open command menu"
      className="commandMenuTrigger"
      onClick={() => window.dispatchEvent(new Event("skillhub:open-command-menu"))}
      type="button"
    >
      Cmd K
    </button>
  );
}
