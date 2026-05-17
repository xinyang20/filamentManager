import {
  Activity,
  Archive,
  Bell,
  Boxes,
  ClipboardList,
  Database,
  Gauge,
  HardDrive,
  LineChart,
  Settings,
  Wrench,
} from "lucide-vue-next";

export const viewKeys = [
  "overview",
  "dashboard",
  "events",
  "metrics",
  "printLog",
  "storage",
  "ams",
  "inventory",
  "maintenance",
  "notifications",
  "printers",
  "debug",
] as const;

export type ViewKey = (typeof viewKeys)[number];
export type InventoryPageKey = "stock" | "history" | "brands" | "types" | "skus" | "colors" | "officialColors";
export type NavGroupKey = "monitoring" | "assets" | "system";
export type SortDirection = "asc" | "desc";
export type InventoryDialogKey =
  | "brand"
  | "typeSeries"
  | "sku"
  | "colorMapping"
  | "spoolCreate"
  | "spoolDetail"
  | "stockAdjust"
  | "skuConfirm";

export const navItems = [
  { key: "overview", labelKey: "nav.overview", icon: Activity, group: "monitoring" },
  { key: "dashboard", labelKey: "nav.dashboard", icon: Gauge, group: "monitoring" },
  { key: "events", labelKey: "nav.events", icon: Bell, group: "monitoring" },
  { key: "metrics", labelKey: "nav.metrics", icon: LineChart, group: "monitoring" },
  { key: "printLog", labelKey: "nav.printLog", icon: ClipboardList, group: "monitoring" },
  { key: "maintenance", labelKey: "nav.maintenance", icon: Wrench, group: "monitoring" },
  { key: "ams", labelKey: "nav.ams", icon: Boxes, group: "assets" },
  { key: "inventory", labelKey: "nav.inventory", icon: Archive, group: "assets" },
  { key: "storage", labelKey: "nav.storage", icon: HardDrive, group: "assets" },
  { key: "notifications", labelKey: "nav.notifications", icon: Bell, group: "system" },
  { key: "printers", labelKey: "nav.printers", icon: Settings, group: "system" },
  { key: "debug", labelKey: "nav.debug", icon: Database, group: "system" },
] as const;

export const navGroups: { key: NavGroupKey; labelKey: string }[] = [
  { key: "monitoring", labelKey: "navGroup.monitoring" },
  { key: "assets", labelKey: "navGroup.assets" },
  { key: "system", labelKey: "navGroup.system" },
];

export const slotChangeKinds = ["material", "remain", "rfid", "calibration"] as const;

export const experimentalFeatureDefaults = {
  timelapse: false,
  maintenance: false,
  printLog: false,
  notifications: false,
};

export type ExperimentalFeatureKey = keyof typeof experimentalFeatureDefaults;

export const experimentalFeatureViews: Partial<Record<ViewKey, ExperimentalFeatureKey>> = {
  storage: "timelapse",
  maintenance: "maintenance",
  printLog: "printLog",
  notifications: "notifications",
};
