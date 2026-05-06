import { useAppContextStore } from "../stores/appContext";

type AppContextStore = ReturnType<typeof useAppContextStore>;

export function useEventStream(appStore: AppContextStore = useAppContextStore()) {
  return {
    connectEventStream: appStore.connectEventStream,
    closeEventStream: appStore.closeEventStream,
  };
}
