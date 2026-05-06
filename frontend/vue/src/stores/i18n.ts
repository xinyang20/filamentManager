import { ref } from "vue";
import { acceptHMRUpdate, defineStore } from "pinia";
import translations from "../i18n.json";

type Locale = keyof typeof translations;

export const useI18nStore = defineStore("i18n", () => {
  const locale = ref<Locale>("zh-CN");

  function t(key: string, vars: Record<string, string | number> = {}) {
    const table = translations[locale.value] as Record<string, string>;
    const fallback = translations["zh-CN"] as Record<string, string>;
    let text = table[key] || fallback[key] || key;
    for (const [name, value] of Object.entries(vars)) {
      text = text.replace(`{${name}}`, String(value));
    }
    return text;
  }

  function navLabel(key: string) {
    return t(`nav.${key}`);
  }

  return {
    locale,
    navLabel,
    t,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useI18nStore, import.meta.hot));
}
