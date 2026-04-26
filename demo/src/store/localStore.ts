import { useEffect, useState } from "react";
import { applyRouteToState } from "../domain/routes";
import { createInitialState } from "../domain/seed";
import type { AppState } from "../domain/types";
import { loadBackendState, resetBackendState } from "./backendState";

export function useLocalAppState() {
  const [state, setState] = useState<AppState>(() => applyRouteToState(createInitialState(), currentPath()));
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadBackendState({}, currentPath())
      .then((next) => {
        if (!cancelled) {
          setState(next);
          setReady(true);
        }
      })
      .catch(() => {
        // The Python backend is optional for the demo; keep local seed if it is not running.
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const reset = () => {
    resetBackendState()
      .then((next) => {
        setState(next);
      })
      .catch(() => {
        setState(createInitialState());
      });
  };

  return [state, setState, reset, ready] as const;
}

function currentPath() {
  return window.location.pathname;
}
