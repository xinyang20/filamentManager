<script setup lang="ts">
import { navGroups, navItems, type NavGroupKey, type ViewKey } from "../app/navigation";
import logoUrl from "../assets/brand/filament-manager-logo.svg";

const props = defineProps<{
  activeView: ViewKey;
  isViewEnabled: (view: ViewKey) => boolean;
  translate: (key: string) => string;
}>();

const emit = defineEmits<{
  "switch-view": [view: ViewKey];
}>();

function navItemsByGroup(group: NavGroupKey) {
  return navItems.filter((item) => item.group === group && props.isViewEnabled(item.key));
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">
        <img class="brand-logo" :src="logoUrl" alt="" />
      </div>
      <div>
        <div class="brand-name">{{ translate("app.name") }}</div>
        <div class="brand-sub">{{ translate("app.subtitle") }}</div>
      </div>
    </div>
    <nav class="nav-list">
      <div v-for="group in navGroups" :key="group.key" class="nav-group">
        <div class="nav-group-label">{{ translate(group.labelKey) }}</div>
        <button
          v-for="item in navItemsByGroup(group.key)"
          :key="item.key"
          class="nav-item"
          :class="{ active: activeView === item.key }"
          type="button"
          @click="emit('switch-view', item.key)"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ translate(item.labelKey) }}</span>
        </button>
      </div>
    </nav>
    <div class="sidebar-footer">
      <div class="mini-label">{{ translate("app.api") }}</div>
      <div class="mono">/api</div>
    </div>
  </aside>
</template>
