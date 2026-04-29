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

export interface DeviceCapabilities {
  model_family: string;
  model_hint?: string | null;
  known: boolean;
  supports_ams?: boolean | null;
  supports_ams_ht?: boolean | null;
  supports_chamber_temperature?: boolean | null;
  supports_aux_fan?: boolean | null;
  supports_camera_fields?: boolean | null;
  has_carbon_rods?: boolean | null;
  xy_motion?: string | null;
  recommended_maintenance: string[];
  visible_fields: string[];
  evidence: Record<string, any>;
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

export interface HmsCodeStats {
  short_code: string;
  printer_id?: number | null;
  days: number;
  recent_count: number;
  active_count: number;
  recovered_count: number;
  affected_printers: number[];
  last_seen_at?: string | null;
  last_recovered_at?: string | null;
  high_frequency: boolean;
  recent_events: Record<string, any>[];
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
  average_duration_seconds?: number | null;
  longest_duration_seconds?: number | null;
  success_rate?: number;
  failure_rate?: number;
  cancelled_rate?: number;
  by_printer: Record<string, any>[];
  by_date?: Record<string, any>[];
  by_failure_reason?: Record<string, any>[];
  by_hms?: Record<string, any>[];
}

export interface PrintLogAnalytics extends PrintLogSummary {
  bucket: string;
  printer_id?: number | null;
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
  target_type?: string;
  target_label?: string | null;
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

export interface TimelapseNote {
  id: number;
  printer_id: number;
  path: string;
  favorite: boolean;
  note?: string | null;
  cached_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationTarget {
  id: number;
  channel: string;
  name: string;
  enabled: boolean;
  config: Record<string, any>;
  display_config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationRule {
  id: number;
  name: string;
  enabled: boolean;
  event_types: string[];
  printer_ids: number[];
  severities: string[];
  quiet_policy: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationDelivery {
  id: number;
  target_id?: number | null;
  rule_id?: number | null;
  event_id?: number | null;
  printer_id?: number | null;
  event_type: string;
  status: string;
  error_summary?: string | null;
  response_status?: number | null;
  sent_at?: string | null;
  created_at: string;
}

export interface StorageUsageArea {
  total_bytes?: number | null;
  free_bytes?: number | null;
  used_bytes?: number | null;
  used_percent?: number | null;
}

export interface StorageSummary {
  printer_id: number;
  file_count: number;
  total_size: number;
  by_type: Record<string, number>;
  storage_usage?: {
    internal?: StorageUsageArea;
    external?: StorageUsageArea;
    timelapse_path?: string | null;
    store_path_type?: string | number | null;
    store_hpd_type?: string | number | null;
    current_target?: string | null;
  };
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

export interface FilamentBrand {
  id: number;
  name: string;
  aliases?: string[];
  note?: string | null;
  default_empty_spool_weight_g?: number | null;
  type_series_count?: number;
  sku_count?: number;
  spool_count?: number;
  created_at: string;
  updated_at: string;
}

export interface FilamentTypeSeries {
  id: number;
  brand_id: number;
  brand_name?: string | null;
  material_type: string;
  series_name: string;
  empty_spool_weight_g?: number | null;
  config?: Record<string, any>;
  note?: string | null;
  brand_ids: number[];
  brands: Record<string, any>[];
  sku_count: number;
  spool_count: number;
  created_at: string;
  updated_at: string;
}

export interface FilamentColorMapping {
  id: number;
  brand_id?: number | null;
  brand_name?: string | null;
  type_series_id?: number | null;
  material_type?: string | null;
  series_name?: string | null;
  material?: string | null;
  series?: string | null;
  color_name?: string | null;
  color_hex?: string | null;
  hex_value?: string | null;
  official_name?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FilamentSku {
  id: number;
  type_series_id?: number | null;
  brand_id?: number | null;
  brand_name?: string | null;
  material?: string | null;
  series?: string | null;
  color_name?: string | null;
  color_hex?: string | null;
  color_value?: string | null;
  nominal_weight_g: number;
  empty_spool_weight_g?: number | null;
  filament_diameter_mm: number;
  density_g_cm3?: number | null;
  tray_info_idx?: string | null;
  sealed_quantity: number;
  note?: string | null;
  type_series_ids?: number[];
  type_series?: Record<string, any>[];
  brands?: Record<string, any>[];
  opened_spool_count?: number;
  ams_spool_count?: number;
  created_at: string;
  updated_at: string;
}

export interface FilamentSpool {
  id: number;
  sku_id?: number | null;
  legacy_spool_id?: number | null;
  sku_label?: string | null;
  brand_id?: number | null;
  brand_name?: string | null;
  material?: string | null;
  series?: string | null;
  color_name?: string | null;
  color_hex?: string | null;
  color_value?: string | null;
  official_spool_uid?: string | null;
  identity_key?: string | null;
  tray_uuid?: string | null;
  tag_uid?: string | null;
  identity_source: string;
  nominal_weight_g?: number | null;
  actual_weight_g?: number | null;
  status: string;
  initial_net_weight_g?: number | null;
  current_remaining_g?: number | null;
  used_weight_g: number;
  empty_spool_weight_g?: number | null;
  opened_at?: string | null;
  first_loaded_at?: string | null;
  last_used_at?: string | null;
  current_printer_id?: number | null;
  current_ams_id?: string | null;
  current_tray_id?: string | null;
  manual_location?: string | null;
  storage_location?: string | null;
  manual_quantity_protected: boolean;
  last_weighed_g?: number | null;
  last_ams_remain_percent?: number | null;
  note?: string | null;
  config?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface FilamentSpoolEvent {
  id: number;
  spool_id?: number | null;
  sku_id?: number | null;
  printer_id?: number | null;
  ams_id?: string | null;
  tray_id?: string | null;
  event_type: string;
  previous?: Record<string, any> | null;
  current?: Record<string, any> | null;
  quantity_delta?: number | null;
  message: string;
  note?: string | null;
  data?: Record<string, any> | null;
  created_at: string;
}

export interface FilamentSpoolEvents {
  events: FilamentSpoolEvent[];
}

export interface FilamentColorMappingGap {
  sku_id: number;
  color_name?: string | null;
  color_hex?: string | null;
  missing: string[];
  type_series: Record<string, any>[];
  brands: Record<string, any>[];
}

export interface FilamentInventorySummary {
  totals: Record<string, number>;
  skus: Record<string, any>[];
  sealed_stock: Record<string, any>[];
  opened_spools: Record<string, any>[];
  ams_spools: Record<string, any>[];
  needs_location_spools: Record<string, any>[];
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
