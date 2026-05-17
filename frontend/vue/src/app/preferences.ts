import {
  experimentalFeatureDefaults,
  experimentalFeatureViews,
  viewKeys,
  type ExperimentalFeatureKey,
  type InventoryPageKey,
  type ViewKey,
} from "./navigation";

export type ExperimentalFeatureSettings = Record<ExperimentalFeatureKey, boolean>;
export type OverviewControls = {
  search: string;
  filter: string;
  sort: string;
  density: string;
};
export type SectionLayout = { hidden?: boolean; collapsed?: boolean; order?: number };
export type SectionLayouts = Record<string, Record<string, SectionLayout>>;

export function loadExperimentalFeatureSettings(storage: Storage = window.localStorage): ExperimentalFeatureSettings {
  try {
    const stored = JSON.parse(storage.getItem("filamentManager.experimentalFeatures") || "{}");
    return {
      timelapse: stored.timelapse === true,
      maintenance: stored.maintenance === true,
      printLog: stored.printLog === true,
      notifications: stored.notifications === true,
    };
  } catch {
    return { ...experimentalFeatureDefaults };
  }
}

export function saveExperimentalFeatureSettings(
  settings: ExperimentalFeatureSettings,
  storage: Storage = window.localStorage,
) {
  storage.setItem("filamentManager.experimentalFeatures", JSON.stringify(settings));
}

export function loadOverviewControls(storage: Storage = window.localStorage): OverviewControls {
  try {
    const stored = JSON.parse(storage.getItem("filamentManager.overviewControls") || "{}");
    return {
      search: String(stored.search || ""),
      filter: String(stored.filter || "all"),
      sort: String(stored.sort || "attention"),
      density: String(stored.density || "standard"),
    };
  } catch {
    return defaultOverviewControls();
  }
}

export function defaultOverviewControls(): OverviewControls {
  return { search: "", filter: "all", sort: "attention", density: "standard" };
}

export function resolveInitialView(
  view: string | null,
  isEnabled: (view: ViewKey) => boolean,
): ViewKey {
  if (view === "filamentBrands" || view === "filamentSkus" || view === "filamentSpools") return "inventory";
  if (!viewKeys.includes(view as ViewKey)) return "overview";
  const next = view as ViewKey;
  return isEnabled(next) ? next : "overview";
}

export function resolveInitialInventoryPage(
  view: string | null,
  storage: Storage = window.localStorage,
): InventoryPageKey {
  if (view === "filamentBrands") return "brands";
  if (view === "filamentSkus") return "skus";
  if (view === "filamentSpools") return "stock";
  const stored = storage.getItem("filamentManager.inventoryPage");
  if (
    stored === "stock" ||
    stored === "history" ||
    stored === "brands" ||
    stored === "types" ||
    stored === "skus" ||
    stored === "colors" ||
    stored === "officialColors"
  ) return stored;
  return "stock";
}

export function isFilamentManagementView(view: ViewKey) {
  return view === "inventory";
}

export function isViewEnabled(view: ViewKey, features: ExperimentalFeatureSettings) {
  const feature = experimentalFeatureViews[view];
  return !feature || features[feature] === true;
}

export function loadSectionLayouts(storage: Storage = window.localStorage): SectionLayouts {
  try {
    const layouts = JSON.parse(storage.getItem("filamentManager.sectionLayouts") || "{}");
    if (layouts?.ams) {
      layouts.ams = Object.fromEntries(
        Object.entries(layouts.ams).filter(([key]) => !key.startsWith("ams.unit.")),
      );
    }
    return layouts;
  } catch {
    return {};
  }
}

export function saveSectionLayouts(layouts: SectionLayouts, storage: Storage = window.localStorage) {
  storage.setItem("filamentManager.sectionLayouts", JSON.stringify(layouts));
}

export function defaultSectionCollapsed(view: ViewKey, id: string) {
  return view === "ams" && id.startsWith("ams.unit.");
}

export function isTransientCollapsedSection(view: ViewKey, id: string) {
  return view === "ams" && id.startsWith("ams.unit.");
}
