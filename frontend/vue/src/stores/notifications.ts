import { computed, reactive, ref } from "vue";
import { acceptHMRUpdate, defineStore, storeToRefs } from "pinia";
import { apiRequest } from "../api";
import type { NotificationDelivery, NotificationRule, NotificationTarget } from "../types";
import { useI18nStore } from "./i18n";
import { usePresentationStore } from "./presentation";
import { useUiStore } from "./ui";

export const useNotificationsStore = defineStore("notifications", () => {
  const uiStore = useUiStore();
  const { message } = storeToRefs(uiStore);
  const { t } = useI18nStore();
  const { withLoading } = uiStore;
  const presentationStore = () => usePresentationStore();

  const notificationTargets = ref<NotificationTarget[]>([]);

  const notificationRules = ref<NotificationRule[]>([]);

  const notificationDeliveries = ref<NotificationDelivery[]>([]);

  const notificationTargetForm = reactive({
    id: "",
    channel: "webhook",
    name: "",
    url: "",
    token: "",
    enabled: true,
  });

  const notificationRuleForm = reactive({
    id: "",
    name: "",
    event_types: "",
    printer_ids: "",
    severities: "",
    quiet_start: "",
    quiet_end: "",
    repeat_suppression_minutes: 30,
    enabled: true,
  });

  const notificationChannelOptions = computed(() => [
    { label: "Webhook", value: "webhook" },
    { label: "ntfy", value: "ntfy" },
  ]);

  async function loadNotifications() {
    const [targets, rules, deliveries] = await Promise.all([
      apiRequest<NotificationTarget[]>("/notifications/targets"),
      apiRequest<NotificationRule[]>("/notifications/rules"),
      apiRequest<NotificationDelivery[]>("/notifications/deliveries?limit=50"),
    ]);
    notificationTargets.value = targets;
    notificationRules.value = rules;
    notificationDeliveries.value = deliveries;
  }


  async function saveNotificationTarget() {
    const payload = {
      channel: notificationTargetForm.channel,
      name: notificationTargetForm.name || notificationTargetForm.channel,
      enabled: notificationTargetForm.enabled,
      config: {
        url: notificationTargetForm.url,
        token: notificationTargetForm.token || undefined,
      },
    };
    await withLoading(async () => {
      const id = notificationTargetForm.id;
      await apiRequest(id ? `/notifications/targets/${id}` : "/notifications/targets", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      resetNotificationTargetForm();
      await loadNotifications();
      message.value = t("notifications.saved");
    });
  }


  function editNotificationTarget(target: NotificationTarget) {
    notificationTargetForm.id = String(target.id);
    notificationTargetForm.channel = target.channel;
    notificationTargetForm.name = target.name;
    notificationTargetForm.url = String(target.display_config?.url || target.display_config?.topic_url || target.config?.url || "");
    notificationTargetForm.token = "";
    notificationTargetForm.enabled = target.enabled;
  }


  function resetNotificationTargetForm() {
    notificationTargetForm.id = "";
    notificationTargetForm.channel = "webhook";
    notificationTargetForm.name = "";
    notificationTargetForm.url = "";
    notificationTargetForm.token = "";
    notificationTargetForm.enabled = true;
  }


  async function deleteNotificationTarget(target: NotificationTarget) {
    await withLoading(async () => {
      await apiRequest(`/notifications/targets/${target.id}`, { method: "DELETE" });
      await loadNotifications();
    });
  }


  async function testNotificationTarget(target: NotificationTarget) {
    await withLoading(async () => {
      await apiRequest(`/notifications/targets/${target.id}/test`, { method: "POST" });
      await loadNotifications();
      message.value = t("notifications.testSent");
    });
  }


  async function saveNotificationRule() {
    const policy: Record<string, unknown> = {};
    if (notificationRuleForm.quiet_start) policy.quiet_start = notificationRuleForm.quiet_start;
    if (notificationRuleForm.quiet_end) policy.quiet_end = notificationRuleForm.quiet_end;
    if (notificationRuleForm.repeat_suppression_minutes) {
      policy.repeat_suppression_minutes = Number(notificationRuleForm.repeat_suppression_minutes);
    }
    const payload = {
      name: notificationRuleForm.name || t("notifications.defaultRuleName"),
      enabled: notificationRuleForm.enabled,
      event_types: presentationStore().splitCsv(notificationRuleForm.event_types),
      printer_ids: presentationStore().splitCsv(notificationRuleForm.printer_ids).map(Number).filter(Number.isFinite),
      severities: presentationStore().splitCsv(notificationRuleForm.severities),
      quiet_policy: policy,
    };
    await withLoading(async () => {
      const id = notificationRuleForm.id;
      await apiRequest(id ? `/notifications/rules/${id}` : "/notifications/rules", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      resetNotificationRuleForm();
      await loadNotifications();
      message.value = t("notifications.ruleSaved");
    });
  }


  function editNotificationRule(rule: NotificationRule) {
    notificationRuleForm.id = String(rule.id);
    notificationRuleForm.name = rule.name;
    notificationRuleForm.event_types = (rule.event_types || []).join(", ");
    notificationRuleForm.printer_ids = (rule.printer_ids || []).join(", ");
    notificationRuleForm.severities = (rule.severities || []).join(", ");
    notificationRuleForm.quiet_start = String(rule.quiet_policy?.quiet_start || "");
    notificationRuleForm.quiet_end = String(rule.quiet_policy?.quiet_end || "");
    notificationRuleForm.repeat_suppression_minutes = Number(rule.quiet_policy?.repeat_suppression_minutes || 30);
    notificationRuleForm.enabled = rule.enabled;
  }


  function resetNotificationRuleForm() {
    notificationRuleForm.id = "";
    notificationRuleForm.name = "";
    notificationRuleForm.event_types = "";
    notificationRuleForm.printer_ids = "";
    notificationRuleForm.severities = "";
    notificationRuleForm.quiet_start = "";
    notificationRuleForm.quiet_end = "";
    notificationRuleForm.repeat_suppression_minutes = 30;
    notificationRuleForm.enabled = true;
  }


  async function deleteNotificationRule(rule: NotificationRule) {
    await withLoading(async () => {
      await apiRequest(`/notifications/rules/${rule.id}`, { method: "DELETE" });
      await loadNotifications();
    });
  }


  return {
    notificationTargets,
    notificationRules,
    notificationDeliveries,
    notificationTargetForm,
    notificationRuleForm,
    notificationChannelOptions,
    loadNotifications,
    saveNotificationTarget,
    editNotificationTarget,
    resetNotificationTargetForm,
    deleteNotificationTarget,
    testNotificationTarget,
    saveNotificationRule,
    editNotificationRule,
    resetNotificationRuleForm,
    deleteNotificationRule,
  };
});

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useNotificationsStore, import.meta.hot));
}
