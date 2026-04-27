export interface Printer {
  id: number;
  name: string;
  host: string;
  port: number;
  serial: string;
  access_code?: string | null;
  tls_enabled: boolean;
  certificate_verify: boolean;
  enabled: boolean;
  connection_status: string;
  last_sync_at?: string | null;
  last_error?: string | null;
}

export interface Dashboard {
  printer?: Printer;
  state?: Record<string, any> | null;
  device_snapshot?: Record<string, any> | null;
  ams_units?: Record<string, any>[];
  ams_slots?: Record<string, any>[];
  recent_events?: Record<string, any>[];
  recent_print_logs?: PrintLogEntry[];
  maintenance_due_count?: number;
}

export interface AmsOverviewSummary {
  ams_count: number;
  slot_count: number;
  loaded_count: number;
  empty_count: number;
  transitioning_count: number;
  unknown_type_count: number;
}

export interface AmsUnitOverview {
  ams_id: string;
  display_name?: string | null;
  ams_type_name: string;
  module_type?: unknown;
  sw_ver?: unknown;
  serial_number?: unknown;
  humidity?: string | null;
  humidity_raw?: unknown;
  temperature?: string | null;
  dry_status?: unknown;
  dry_status_name?: string | null;
  dry_sub_status?: unknown;
  dry_sub_status_name?: string | null;
  dry_sf_reason_names?: string[];
  active_slot?: Record<string, any> | null;
  updated_at: string;
  slots: Record<string, any>[];
}

export interface AmsOverview {
  summary: AmsOverviewSummary;
  units: AmsUnitOverview[];
}

export interface AmsSlotHistorySample {
  id: number;
  printer_id: number;
  ams_id: string;
  tray_id: string;
  state_name?: string | null;
  material?: string | null;
  color?: string | null;
  remain?: number | null;
  k?: string | null;
  cali_idx?: string | null;
  rfid_status?: string | null;
  sampled_at: string;
  raw_message_id?: number | null;
}

export interface AmsSensorHistory {
  printer_id: number;
  ams_id: string;
  hours: number;
  points: { sampled_at: string; temperature?: number | null; humidity?: number | null }[];
  temperature: { min?: number | null; max?: number | null; avg?: number | null };
  humidity: { min?: number | null; max?: number | null; avg?: number | null };
}

export interface HmsCodeInfo {
  short_code: string;
  module: string;
  severity: string;
  message_zh: string;
  message_en: string;
  suggestion_zh: string;
  suggestion_en: string;
  wiki_url?: string | null;
  known: boolean;
  actionable: boolean;
}

export interface UnifiedEvent {
  id: number;
  source: string;
  printer_id?: number | null;
  spool_id?: number | null;
  type: string;
  event_type: string;
  severity: string;
  active?: boolean | null;
  message: string;
  dedupe_key?: string | null;
  data?: Record<string, any> | null;
  created_at: string;
}

export interface DashboardSummaryItem {
  printer: Printer;
  state?: Record<string, any> | null;
  device_snapshot?: Record<string, any> | null;
  recent_print_logs?: PrintLogEntry[];
  maintenance_due_count?: number;
}

export interface PrintLogEntry {
  id: number;
  printer_id: number;
  printer_name_snapshot?: string | null;
  task_id?: string | null;
  print_name?: string | null;
  gcode_file?: string | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_seconds?: number | null;
  max_progress?: number | null;
  final_progress?: number | null;
  layer_current?: number | null;
  layer_total?: number | null;
  filament_summary?: Record<string, any>;
  hms_summary?: Record<string, any>[];
  failure_reason?: string | null;
}

export interface PrintLogList {
  total: number;
  limit: number;
  offset: number;
  items: PrintLogEntry[];
}

export interface PrintLogSummary {
  total: number;
  running: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  total_duration_seconds: number;
  by_printer: Record<string, any>[];
}

export interface MaintenanceType {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  interval_type: string;
  default_interval: number;
  icon?: string | null;
  wiki_url?: string | null;
}

export interface PrinterMaintenance {
  id: number;
  printer_id: number;
  printer_name?: string | null;
  maintenance_type: MaintenanceType;
  enabled: boolean;
  custom_interval?: number | null;
  interval: number;
  last_performed_at?: string | null;
  last_performed_print_hours: number;
  current_print_hours: number;
  hours_since_last: number;
  hours_until_due: number;
  due_status: string;
  history_count: number;
}

export interface MaintenanceOverview {
  total_items: number;
  due_count: number;
  soon_count: number;
  ok_count: number;
  printers: Record<string, any>[];
  items: PrinterMaintenance[];
}

export interface SystemInfo {
  app_version: string;
  uptime_seconds: number;
  database_size_bytes: number;
  storage_size_bytes: number;
  cpu_percent?: number | null;
  memory: Record<string, any>;
  configured_printers: number;
  online_printers: number;
}

export interface MetricSample {
  id: number;
  metric: string;
  value_float?: number | null;
  value_text?: string | null;
  unit?: string | null;
  details?: Record<string, any>;
  sampled_at: string;
}

export interface StorageFile {
  id: number;
  path: string;
  name: string;
  size?: number | null;
  modified_at?: string | null;
  type?: string | null;
  source: string;
}

export interface StorageSummary {
  printer_id: number;
  file_count: number;
  total_size: number;
  by_type: Record<string, number>;
  recent_files: StorageFile[];
  timelapse_files: StorageFile[];
  last_scan?: Record<string, any> | null;
}

export interface Spool {
  id: number;
  display_name: string;
  material?: string | null;
  series?: string | null;
  color?: string | null;
  status: string;
  sealed_quantity: number;
  current_printer_id?: number | null;
  current_ams_id?: string | null;
  current_tray_id?: string | null;
}

export interface DiscoveryCandidate {
  host: string;
  open_ports: number[];
  confidence: number;
  device_name?: string | null;
  model?: string | null;
  serial?: string | null;
  connection_mode?: string | null;
  bind_state?: string | null;
  secure_link?: string | null;
  firmware_version?: string | null;
  reason: string;
}
