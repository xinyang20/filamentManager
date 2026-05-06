import { useAppContextStore } from "../stores/appContext";

type AppContextStore = ReturnType<typeof useAppContextStore>;

export function useBootstrap(appStore: AppContextStore = useAppContextStore()) {
  return {
    startBootstrap: appStore.bootstrap,
  };
}
