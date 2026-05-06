import { computed, ref } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";

export const useUiStore = defineStore("ui", () => {
  const message = ref("");
  const error = ref("");
  const realtimeDisconnected = ref(false);
  const activeLoadingCount = ref(0);
  const loading = computed(() => activeLoadingCount.value > 0);
  let loadingTokenSeq = 0;
  const activeLoadingTokens = new Set<number>();

  async function withLoading(action: () => Promise<void>) {
    const token = beginLoading();
    const watchdog = window.setTimeout(() => finishLoading(token), 20000);
    error.value = "";
    message.value = "";
    try {
      await action();
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err);
    } finally {
      window.clearTimeout(watchdog);
      finishLoading(token);
    }
  }

  function beginLoading() {
    const token = ++loadingTokenSeq;
    activeLoadingTokens.add(token);
    activeLoadingCount.value = activeLoadingTokens.size;
    return token;
  }

  function finishLoading(token: number) {
    if (!activeLoadingTokens.delete(token)) return;
    activeLoadingCount.value = activeLoadingTokens.size;
  }

  return {
    error,
    loading,
    message,
    realtimeDisconnected,
    withLoading,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useUiStore, import.meta.hot));
}
