import { expect, type Page, test } from "@playwright/test";

const timestamp = "2026-04-30T10:00:00Z";

const printer = {
  id: 1,
  name: "Synthetic Printer",
  host: "192.0.2.10",
  port: 8883,
  serial: "SYNTHETIC123",
  access_code: "****1234",
  tls_enabled: true,
  certificate_verify: false,
  enabled: true,
  connection_status: "connected",
  last_sync_at: timestamp,
  last_error: null,
};

const filamentBrand = {
  id: 1,
  name: "Bambu",
  aliases: ["BL"],
  default_empty_spool_weight_g: 250,
  type_series_count: 1,
  sku_count: 1,
  spool_count: 3,
  note: "Synthetic brand",
};

const typeSeries = {
  id: 1,
  brand_id: 1,
  brand_name: "Bambu",
  material_type: "PLA",
  series_name: "Matte",
  empty_spool_weight_g: 250,
  sku_count: 1,
  spool_count: 3,
  brands: [filamentBrand],
  note: "Daily filament",
};

const filamentSku = {
  id: 1,
  brand_id: 1,
  brand_name: "Bambu",
  type_series_id: 1,
  material: "PLA",
  series: "Matte",
  color_name: "Signal Green",
  color_hex: "#00AE42",
  color_value: "#00AE42",
  nominal_weight_g: 1000,
  empty_spool_weight_g: 250,
  filament_diameter_mm: 1.75,
  tray_info_idx: "GFL00",
  sealed_quantity: 2,
  brands: [filamentBrand],
  type_series: [typeSeries],
  note: "Primary SKU",
};

const filamentSpools = [
  {
    id: 10,
    sku_id: 1,
    sku_label: "Bambu PLA Matte Signal Green 1000g",
    brand_id: 1,
    brand_name: "Bambu",
    type_series_id: 1,
    material: "PLA",
    series: "Matte",
    color_name: "Signal Green",
    color_hex: "#00AE42",
    color_value: "#00AE42",
    status: "loaded_in_ams",
    initial_weight_g: 1000,
    current_remaining_g: 620,
    actual_weight_g: 620,
    current_printer_id: 1,
    current_ams_id: "0",
    current_tray_id: "0",
    last_ams_remain_percent: 62,
    note: "Loaded spool",
    config: {},
  },
  {
    id: 11,
    sku_id: 1,
    sku_label: "Bambu PLA Matte Signal Green 1000g",
    brand_id: 1,
    brand_name: "Bambu",
    type_series_id: 1,
    material: "PLA",
    series: "Matte",
    color_name: "Signal Green",
    color_hex: "#00AE42",
    color_value: "#00AE42",
    status: "opened_in_storage",
    initial_weight_g: 1000,
    current_remaining_g: 840,
    actual_weight_g: 840,
    manual_location: "Shelf A1",
    last_ams_remain_percent: null,
    note: "Opened stock",
    config: {},
  },
  {
    id: 12,
    sku_id: 1,
    sku_label: "Bambu PLA Matte Signal Green 1000g",
    brand_id: 1,
    brand_name: "Bambu",
    type_series_id: 1,
    material: "PLA",
    series: "Matte",
    color_name: "Signal Green",
    color_hex: "#00AE42",
    color_value: "#00AE42",
    status: "archived",
    initial_weight_g: 1000,
    current_remaining_g: 0,
    actual_weight_g: 0,
    last_printer_id: 1,
    last_ams_id: "0",
    last_tray_id: "1",
    archived_at: timestamp,
    note: "Used up",
    config: {},
  },
];

const amsSlot = {
  id: 101,
  printer_id: 1,
  printer_name: "Synthetic Printer",
  ams_id: "0",
  tray_id: "0",
  user_tray_id: "0",
  slot_index: 0,
  material: "PLA",
  series: "Matte",
  color: "#00AE42",
  tray_color: "#00AE42",
  color_name: "Signal Green",
  state_name: "Loaded",
  slot_state: "loaded",
  remain: 62,
  k: 0.02,
  cali_idx: 1,
  rfid_status_name: "Ready",
  filament_spool_id: 10,
  spool_id: 10,
  is_active: true,
  is_loaded: true,
  raw: {},
};

const amsOverview = {
  summary: {
    ams_count: 1,
    slot_count: 2,
    loaded_count: 1,
    empty_count: 1,
    transitioning_count: 0,
  },
  units: [
    {
      ams_id: "0",
      display_name: "Main AMS",
      ams_type_name: "AMS",
      temperature: 25.3,
      humidity: 3,
      humidity_raw: 3,
      active_slot: "0",
      dry_status_name: "Normal",
      sw_ver: "1.0.0",
      updated_at: timestamp,
      slots: [
        amsSlot,
        {
          id: 102,
          printer_id: 1,
          ams_id: "0",
          tray_id: "1",
          user_tray_id: "1",
          slot_index: 1,
          material: "",
          color: "",
          state_name: "Empty",
          slot_state: "empty",
          remain: null,
          is_active: false,
          is_loaded: false,
          raw: {},
        },
      ],
    },
  ],
};

const dashboard = {
  printer,
  state: {
    gcode_state: "RUNNING",
    mc_percent: 42,
    subtask_name: "Calibration cube",
    layer_num: 12,
    total_layer_num: 48,
    remaining_time: 35,
  },
  device_snapshot: {
    derived_status: { actual_printing: true, user_state: "RUNNING", heating_bed: false },
    temperatures: { nozzle: 218, nozzle_target: 220, bed: 62, bed_target: 65, chamber: 31 },
    fans: { cooling_fan_speed: { raw: "8", percent: 53 } },
    network: { wifi_signal: -48, ip: "192.0.2.10" },
    hardware: { nozzle_type: "HS01", nozzle_diameter: "0.4", extruder_count: 1 },
    camera: {
      ipcam_record: true,
      timelapse: false,
      resolution: "1920x1080",
      rtsp_url: "rtsp://192.0.2.10/live/very/long/path/that/should/not/render",
    },
    camera_options: {
      first_layer_inspector: true,
      printing_monitor: true,
      raw_cfg: "enabled",
    },
    ams_status: { ams_status_main_name: "Ready" },
    data_coverage: {
      push_status: { received: true, last_updated: timestamp },
      get_version: { received: true, last_updated: timestamp },
    },
    hms_errors: [
      {
        code: "0300_1000",
        short_code: "0300",
        severity: "warning",
        severity_name: "Warning",
        active: true,
        actionable: true,
        module_name: "AMS",
        message_zh: "测试告警",
        suggestion_zh: "检查 AMS",
      },
    ],
  },
  ams_units: amsOverview.units,
  ams_slots: amsOverview.units[0].slots,
  recent_events: [],
};

const summary = [
  {
    printer,
    state: {
      gcode_state: "RUNNING",
      mc_percent: 42,
      subtask_name: "Calibration cube",
      layer_current: 12,
      layer_total: 48,
    },
    device_snapshot: dashboard.device_snapshot,
    maintenance_due_count: 1,
  },
];

const events = [
  {
    id: 501,
    type: "print.started",
    severity: "info",
    active: true,
    source: "test",
    printer_id: 1,
    spool_id: 10,
    created_at: timestamp,
    message: "Print started",
    data: { print_name: "Calibration cube", gcode_file: "cube.gcode" },
  },
  {
    id: 502,
    type: "hms.active",
    severity: "warning",
    active: true,
    source: "test",
    printer_id: 1,
    created_at: timestamp,
    message: "AMS warning",
    data: { short_code: "0300", message_zh: "测试告警", message: "AMS warning" },
  },
];

const metrics = [
  { id: 1, metric: "temperature.nozzle", value_float: 210, unit: "celsius", sampled_at: "2026-04-30T09:55:00Z" },
  { id: 2, metric: "temperature.nozzle", value_float: 218, unit: "celsius", sampled_at: timestamp },
  { id: 3, metric: "fan.cooling_fan_speed.percent", value_float: 53, unit: "percent", sampled_at: timestamp },
  { id: 4, metric: "network.wifi_signal", value_float: -48, unit: "dBm", sampled_at: timestamp },
  { id: 5, metric: "ams.0.temperature", value_float: 25, unit: "celsius", sampled_at: timestamp },
  { id: 6, metric: "ams.0.humidity", value_float: 3, unit: "percent", sampled_at: timestamp },
];

const printLogList = {
  total: 1,
  items: [
    {
      id: 701,
      printer_id: 1,
      printer_name_snapshot: "Synthetic Printer",
      print_name: "Calibration cube.gcode",
      gcode_file: "cube.gcode",
      status: "succeeded",
      started_at: "2026-04-30T09:00:00Z",
      ended_at: timestamp,
      duration_seconds: 3600,
      max_progress: 100,
      final_progress: 100,
      layer_current: 48,
      layer_total: 48,
      failure_reason: null,
    },
  ],
};

const storageFiles = [
  {
    path: "/timelapse/demo_timelapse.mp4",
    name: "demo_timelapse.mp4",
    size: 1048576,
    modified_at: timestamp,
    type: "timelapse",
    source: "ftps",
  },
];

const maintenanceOverview = {
  due_count: 1,
  soon_count: 0,
  ok_count: 1,
  total_items: 2,
  printers: [
    {
      printer_id: 1,
      printer_name: "Synthetic Printer",
      due_count: 1,
      soon_count: 0,
      ok_count: 1,
    },
  ],
};

const maintenanceItems = [
  {
    id: 801,
    printer_id: 1,
    due_status: "due",
    target_type: "printer",
    target_label: "Toolhead",
    interval: 100,
    current_print_hours: 125,
    hours_since_last: 125,
    remaining_hours: -25,
    last_performed_at: "2026-04-01T10:00:00Z",
    maintenance_type: {
      id: 1,
      name: "Nozzle Cleaning",
      description: "Clean nozzle residue",
      category: "printer",
    },
  },
  {
    id: 802,
    printer_id: 1,
    due_status: "ok",
    target_type: "ams",
    target_label: "AMS 0",
    interval: 200,
    current_print_hours: 125,
    hours_since_last: 20,
    remaining_hours: 180,
    last_performed_at: "2026-04-20T10:00:00Z",
    maintenance_type: {
      id: 2,
      name: "AMS Desiccant",
      description: "Refresh desiccant",
      category: "ams",
    },
  },
];

const notificationTargets = [
  {
    id: 901,
    channel: "webhook",
    name: "Webhook Target",
    enabled: true,
    display_config: "https://example.invalid/hook",
  },
];

const notificationRules = [
  {
    id: 902,
    name: "Critical Events",
    event_types: ["hms.active"],
    printer_ids: [1],
    severities: ["warning"],
    enabled: true,
  },
];

async function installApiMocks(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.clear();
    window.localStorage.setItem(
      "filamentManager.experimentalFeatures",
      JSON.stringify({ timelapse: true, maintenance: true, printLog: true, notifications: true }),
    );
  });

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const method = request.method();

    if (path === "/events/stream") {
      await route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body: "" });
      return;
    }

    if (method !== "GET") {
      await route.fulfill({ json: { ok: true } });
      return;
    }

    if (path === "/printers") return route.fulfill({ json: [printer] });
    if (path === "/dashboard/summary") return route.fulfill({ json: summary });
    if (path === "/printers/1/dashboard") return route.fulfill({ json: dashboard });
    if (path === "/printers/1/capabilities") {
      return route.fulfill({ json: { visible_fields: ["camera", "chamber_temperature"] } });
    }
    if (path === "/printers/1/camera/capabilities") {
      return route.fulfill({ json: { available: false, detail: "mock camera disabled" } });
    }
    if (path === "/printers/1/state") return route.fulfill({ json: dashboard.state });
    if (path === "/printers/1/ams/overview") return route.fulfill({ json: amsOverview });
    if (path === "/printers/1/ams/slots") return route.fulfill({ json: [amsSlot] });
    if (path === "/printers/1/ams/0/sensor-history") {
      return route.fulfill({ json: { ams_id: "0", hours: 24, points: [{ sampled_at: timestamp, temperature: 25, humidity: 3 }] } });
    }
    if (path === "/printers/1/metrics") return route.fulfill({ json: metrics });
    if (path === "/print-log") return route.fulfill({ json: printLogList });
    if (path === "/print-log/summary") {
      return route.fulfill({ json: { total: 1, succeeded: 1, failed: 0, total_duration_seconds: 3600 } });
    }
    if (path === "/print-log/analytics") {
      return route.fulfill({
        json: {
          success_rate: 1,
          failure_rate: 0,
          average_duration_seconds: 3600,
          longest_duration_seconds: 3600,
          by_date: [{ bucket: "2026-04-30", total: 1 }],
          by_failure_reason: [],
        },
      });
    }
    if (path === "/printers/1/storage/files") return route.fulfill({ json: storageFiles });
    if (path === "/printers/1/storage/summary") {
      return route.fulfill({
        json: {
          storage_usage: {
            internal: { total_bytes: 1000000000, used_bytes: 250000000, free_bytes: 750000000, used_percent: 25 },
            external: null,
            current_target: "internal",
          },
        },
      });
    }
    if (path === "/printers/1/timelapse/notes") {
      return route.fulfill({
        json: [
          {
            path: "/timelapse/demo_timelapse.mp4",
            note: "Factory run",
            favorite: true,
            cached_metadata: { resolution: "1920x1080", cover_cache: "ready" },
          },
        ],
      });
    }
    if (path === "/events") return route.fulfill({ json: events });
    if (path === "/hms/codes") return route.fulfill({ json: [] });
    if (path === "/filament/brands") return route.fulfill({ json: [filamentBrand] });
    if (path === "/filament/type-series") return route.fulfill({ json: [typeSeries] });
    if (path === "/filament/color-mappings") {
      return route.fulfill({
        json: [
          {
            id: 301,
            brand_id: 1,
            brand_name: "Bambu",
            type_series_id: 1,
            material: "PLA",
            material_type: "PLA",
            series: "Matte",
            series_name: "Matte",
            color_hex: "#00AE42",
            hex_value: "#00AE42",
            color_name: "Bambu Green",
            official_name: "Bambu Green",
            note: "Official green",
          },
        ],
      });
    }
    if (path === "/filament/color-mapping-gaps") return route.fulfill({ json: [] });
    if (path === "/filament/skus") return route.fulfill({ json: [filamentSku] });
    if (path === "/filament/spools") return route.fulfill({ json: filamentSpools });
    if (path === "/filament/inventory/summary") {
      return route.fulfill({
        json: {
          totals: {
            sku_count: 1,
            sealed_quantity: 2,
            sealed_weight_g: 2000,
            opened_spool_count: 2,
            opened_weight_g: 1460,
            ams_spool_count: 1,
            total_weight_g: 3460,
          },
          by_material: [{ material: "PLA", weight_g: 3460, spool_count: 3 }],
        },
      });
    }
    if (path === "/filament/spools/10/events" || path === "/filament/spools/11/events" || path === "/filament/spools/12/events") {
      return route.fulfill({ json: { spool_id: 10, events: [] } });
    }
    if (path === "/maintenance/overview") return route.fulfill({ json: maintenanceOverview });
    if (path === "/printers/1/maintenance") return route.fulfill({ json: maintenanceItems });
    if (path === "/debug/raw-mqtt") {
      return route.fulfill({ json: [{ id: 1, topic: "device/report", payload: { print: { gcode_state: "RUNNING" } } }] });
    }
    if (path === "/system/info") {
      return route.fulfill({
        json: {
          app_version: "0.1.0-test",
          uptime_seconds: 3600,
          database_size_bytes: 4096,
          storage_size_bytes: 1048576,
          cpu_percent: 12,
          memory: { project_rss_bytes: 2097152 },
          configured_printers: 1,
          online_printers: 1,
        },
      });
    }
    if (path === "/notifications/targets") return route.fulfill({ json: notificationTargets });
    if (path === "/notifications/rules") return route.fulfill({ json: notificationRules });
    if (path === "/notifications/deliveries") {
      return route.fulfill({
        json: [{ id: 903, event_type: "hms.active", status: "sent", error_summary: null, created_at: timestamp }],
      });
    }

    await route.fulfill({ json: null });
  });
}

async function openApp(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "总览", level: 1 })).toBeVisible();
}

async function switchTo(page: Page, label: string) {
  await page.getByRole("button", { name: label, exact: true }).click();
  await expect(page.getByRole("heading", { name: label, level: 1 })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await installApiMocks(page);
});

test("renders overview and navigates to printer configuration", async ({ page }) => {
  await openApp(page);

  await expect(page.getByText("Synthetic Printer").first()).toBeVisible();
  await expect(page.getByText("Calibration cube")).toBeVisible();
  await expect(page.getByText("42%")).toBeVisible();

  await switchTo(page, "打印机配置");
  await expect(page.getByLabel("名称")).toHaveValue("Synthetic Printer");
  await expect(page.getByLabel("主机")).toHaveValue("192.0.2.10");
  await expect(page.getByLabel("序列号")).toHaveValue("SYNTHETIC123");
});

test("renders dashboard camera status without leaking the RTSP URL", async ({ page }) => {
  await openApp(page);
  await switchTo(page, "设备大屏");

  await expect(page.getByText("Calibration cube").first()).toBeVisible();
  await expect(page.getByText("HS01")).toBeVisible();

  const rtspRow = page.locator(".camera-status-grid .camera-info-item").filter({ hasText: "RTSP 推流" });
  await expect(rtspRow).toContainText("开启");
  await expect(rtspRow).not.toContainText("rtsp://");
});

test("renders events and opens the event detail modal", async ({ page }) => {
  await openApp(page);
  await switchTo(page, "事件中心");

  await expect(page.getByText("打印开始：cube.gcode")).toBeVisible();
  await page.getByRole("button", { name: "详情" }).first().click();
  await expect(page.getByRole("heading", { name: /事件详情/ })).toBeVisible();
  await expect(page.getByText("Print started")).toBeVisible();
});

test("renders print log and metric charts", async ({ page }) => {
  await openApp(page);

  await switchTo(page, "打印日志");
  await expect(page.getByRole("heading", { name: "打印分析" })).toBeVisible();
  await expect(page.getByText("Calibration cube.gcode")).toBeVisible();
  await expect(page.getByText("1小时 0分钟").first()).toBeVisible();

  await switchTo(page, "历史趋势");
  await expect(page.getByRole("heading", { name: "温度历史" })).toBeVisible();
  await expect(page.getByText("喷嘴").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "AMS 温湿度" })).toBeVisible();
});

test("renders storage timelapse cards and notes", async ({ page }) => {
  await openApp(page);
  await switchTo(page, "延迟摄影");

  await expect(page.getByRole("heading", { name: "延迟摄影视频" })).toBeVisible();
  await expect(page.getByText("demo_timelapse.mp4")).toBeVisible();
  await expect(page.getByPlaceholder("本地备注")).toHaveValue("Factory run");
  await expect(page.getByRole("heading", { name: "按日期分组" })).toBeVisible();
});

test("renders AMS units and opens slot details", async ({ page }) => {
  await openApp(page);
  await switchTo(page, "AMS");

  await page.getByRole("button", { name: "折叠 / 展开" }).click();
  await expect(page.getByRole("heading", { name: "Main AMS" })).toBeVisible();
  await expect(page.getByText("PLA · Matte · Signal Green").first()).toBeVisible();

  await page.locator(".ams-slot-card").filter({ hasText: "PLA" }).getByTitle("详情").click();
  await expect(page.getByRole("heading", { name: "槽位详情" })).toBeVisible();
  await expect(page.getByText("AMS 0 / 槽位 0")).toBeVisible();
});

test("renders inventory tabs and opens a create-brand modal", async ({ page }) => {
  await openApp(page);
  await switchTo(page, "耗材");

  await expect(page.getByRole("heading", { name: "库存分析" })).toBeVisible();
  await expect(page.getByText("Bambu · Matte · PLA · Bambu Green").first()).toBeVisible();

  await page.getByRole("button", { name: "SKU" }).click();
  await expect(page.getByRole("heading", { name: "SKU" })).toBeVisible();
  await expect(page.getByText("Bambu Green").first()).toBeVisible();

  await page.getByRole("tablist").getByRole("button", { name: "品牌", exact: true }).click();
  await expect(page.getByText("Synthetic brand")).toBeVisible();
  await page.getByTitle("新增品牌").click();
  await expect(page.getByRole("heading", { name: "新增品牌" })).toBeVisible();
});

test("renders maintenance, notifications and debug pages", async ({ page }) => {
  await openApp(page);

  await switchTo(page, "维护");
  await expect(page.getByText("Nozzle Cleaning")).toBeVisible();
  await expect(page.getByText("Clean nozzle residue")).toBeVisible();

  await switchTo(page, "通知");
  await expect(page.getByRole("heading", { name: "通知目标" })).toBeVisible();
  await expect(page.getByText("Webhook Target")).toBeVisible();
  await expect(page.getByText("Critical Events")).toBeVisible();

  await switchTo(page, "调试");
  await expect(page.getByRole("heading", { name: "系统信息" })).toBeVisible();
  await expect(page.getByText("0.1.0-test")).toBeVisible();
  await expect(page.getByRole("heading", { name: "本地导出" })).toBeVisible();
});
