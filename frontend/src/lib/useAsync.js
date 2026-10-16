import { useCallback, useEffect, useState } from "react";

/**
 * Run an async loader whenever `deps` change and keep {data, error, loading}.
 * `reload()` refetches quietly (no loading flash), e.g. after an action or on a timer.
 */
export function useAsync(loader, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const run = useCallback(loader, deps);

  useEffect(() => {
    let active = true; // ignore a slow response that arrives after deps changed
    setState((s) => ({ ...s, loading: true }));
    run().then(
      (data) => active && setState({ data, error: null, loading: false }),
      (error) => active && setState({ data: null, error, loading: false }),
    );
    return () => {
      active = false;
    };
  }, [run]);

  const reload = useCallback(
    () =>
      run().then(
        (data) => setState({ data, error: null, loading: false }),
        (error) => setState((s) => ({ ...s, error, loading: false })),
      ),
    [run],
  );

  return { ...state, reload };
}
