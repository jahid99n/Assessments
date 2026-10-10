import { createContext, useContext, useEffect, useState } from "react";

const Runtime = createContext(null);
export function RuntimeProvider({ runtime, children }) {
  const [session, setSession] = useState({
    loading: true,
    user: null,
    error: "",
  });
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const user = await runtime.auth.session();
        if (alive) setSession({ loading: false, user, error: "" });
      } catch {
        if (alive)
          setSession({
            loading: false,
            user: null,
            error: "Your session could not be restored. Please sign in again.",
          });
      }
    };
    refresh();
    const unsubscribe = runtime.auth.subscribe(refresh);
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [runtime]);
  return (
    <Runtime.Provider value={{ ...runtime, ...session }}>
      {children}
    </Runtime.Provider>
  );
}
export const useRuntime = () => useContext(Runtime);
