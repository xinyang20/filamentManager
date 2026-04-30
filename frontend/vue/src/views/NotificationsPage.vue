<script setup lang="ts">
import { appViewRefs, type AppViewContext } from "../app/viewContext";
import {
  Activity,
  AlertCircle,
  Archive,
  Bell,
  Boxes,
  Camera,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ClipboardList,
  Database,
  Download,
  Eye,
  EyeOff,
  FileDown,
  Gauge,
  LineChart,
  Loader2,
  Network,
  PencilLine,
  Plus,
  PlugZap,
  RefreshCw,
  Save,
  Search,
  Send,
  Settings,
  ShieldAlert,
  Star,
  Thermometer,
  Trash2,
  Unplug,
  Upload,
  Wrench,
  X,
} from "lucide-vue-next";
import AppSelect from "../components/AppSelect.vue";
import MetricChart from "../components/MetricChart.vue";

const props = defineProps<{ ctx: AppViewContext }>();
const {
  activeView,
  deleteNotificationRule,
  deleteNotificationTarget,
  displayCell,
  editNotificationRule,
  editNotificationTarget,
  formatCell,
  message,
  notificationChannelOptions,
  notificationDeliveries,
  notificationRuleForm,
  notificationRules,
  notificationTargetForm,
  notificationTargets,
  saveNotificationRule,
  saveNotificationTarget,
  softCell,
  t,
  testNotificationTarget,
} = appViewRefs(props.ctx);
</script>

<template>
<section class="view">
        <div class="grid two wide">
          <section class="panel">
            <div class="panel-header"><h3>{{ t("notifications.targets") }}</h3><Send :size="18" /></div>
            <div class="form-grid compact-form">
              <AppSelect v-model="notificationTargetForm.channel" :options="notificationChannelOptions" />
              <input v-model="notificationTargetForm.name" :placeholder="t('form.name')" />
              <input v-model="notificationTargetForm.url" :placeholder="t('notifications.url')" />
              <input v-model="notificationTargetForm.token" :placeholder="t('notifications.token')" type="password" />
              <label class="checkbox"><input v-model="notificationTargetForm.enabled" type="checkbox" /> {{ t("common.active") }}</label>
              <button class="primary" type="button" @click="saveNotificationTarget"><Save :size="17" />{{ t("common.save") }}</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.details") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!notificationTargets.length"><td colspan="5" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="target in notificationTargets" :key="target.id">
                    <td>{{ target.name }}</td>
                    <td>{{ target.channel }}</td>
                    <td>{{ target.enabled ? t("common.active") : t("common.inactive") }}</td>
                    <td>{{ formatCell(target.display_config) }}</td>
                    <td>
                      <button class="icon-button compact" type="button" :title="t('table.actions')" @click="editNotificationTarget(target)"><PencilLine :size="14" /></button>
                      <button class="icon-button compact" type="button" :title="t('notifications.test')" @click="testNotificationTarget(target)"><Send :size="14" /></button>
                      <button class="icon-button compact danger" type="button" :title="t('common.delete')" @click="deleteNotificationTarget(target)"><Trash2 :size="14" /></button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header"><h3>{{ t("notifications.rules") }}</h3><Bell :size="18" /></div>
            <div class="form-grid compact-form">
              <input v-model="notificationRuleForm.name" :placeholder="t('form.name')" />
              <input v-model="notificationRuleForm.event_types" :placeholder="t('notifications.eventTypes')" />
              <input v-model="notificationRuleForm.printer_ids" :placeholder="t('notifications.printerIds')" />
              <input v-model="notificationRuleForm.severities" :placeholder="t('notifications.severities')" />
              <input v-model="notificationRuleForm.quiet_start" type="time" />
              <input v-model="notificationRuleForm.quiet_end" type="time" />
              <input v-model.number="notificationRuleForm.repeat_suppression_minutes" type="number" min="0" />
              <label class="checkbox"><input v-model="notificationRuleForm.enabled" type="checkbox" /> {{ t("common.active") }}</label>
              <button class="primary" type="button" @click="saveNotificationRule"><Save :size="17" />{{ t("common.save") }}</button>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>{{ t("table.name") }}</th><th>{{ t("notifications.eventTypes") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.actions") }}</th></tr></thead>
                <tbody>
                  <tr v-if="!notificationRules.length"><td colspan="4" class="empty">{{ t("common.empty") }}</td></tr>
                  <tr v-for="rule in notificationRules" :key="rule.id">
                    <td>{{ rule.name }}</td>
                    <td>{{ (rule.event_types || []).join(', ') || t("common.none") }}</td>
                    <td>{{ rule.enabled ? t("common.active") : t("common.inactive") }}</td>
                    <td>
                      <button class="icon-button compact" type="button" @click="editNotificationRule(rule)"><PencilLine :size="14" /></button>
                      <button class="icon-button compact danger" type="button" @click="deleteNotificationRule(rule)"><Trash2 :size="14" /></button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
        <section class="panel">
          <div class="panel-header"><h3>{{ t("notifications.deliveries") }}</h3><Database :size="18" /></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>{{ t("table.time") }}</th><th>{{ t("table.type") }}</th><th>{{ t("table.status") }}</th><th>{{ t("table.message") }}</th></tr></thead>
              <tbody>
                <tr v-if="!notificationDeliveries.length"><td colspan="4" class="empty">{{ t("common.empty") }}</td></tr>
                <tr v-for="delivery in notificationDeliveries" :key="delivery.id">
                  <td>{{ formatCell(delivery.created_at) }}</td>
                  <td>{{ delivery.event_type }}</td>
                  <td>{{ displayCell(delivery.status) }}</td>
                  <td>{{ softCell(delivery.error_summary) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>
</template>
