<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Check, ChevronDown } from "lucide-vue-next";

type SelectValue = string | number | null;

interface SelectOption {
  label: string;
  value: SelectValue;
  disabled?: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: SelectValue;
    options: SelectOption[];
    placeholder?: string;
    disabled?: boolean;
  }>(),
  {
    placeholder: "",
    disabled: false,
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: SelectValue];
  change: [value: SelectValue];
}>();

const root = ref<HTMLElement | null>(null);
const open = ref(false);
const activeIndex = ref(-1);

const selectedOption = computed(() => props.options.find((option) => option.value === props.modelValue));
const activeOption = computed(() => props.options[activeIndex.value]);

function toggle() {
  if (props.disabled) return;
  open.value = !open.value;
  if (open.value) {
    activeIndex.value = Math.max(0, props.options.findIndex((option) => option.value === props.modelValue));
  }
}

function close() {
  open.value = false;
}

function selectOption(option: SelectOption) {
  if (option.disabled) return;
  emit("update:modelValue", option.value);
  emit("change", option.value);
  close();
}

function onPointerDown(event: PointerEvent) {
  if (!open.value) return;
  if (root.value?.contains(event.target as Node)) return;
  close();
}

function onKeydown(event: KeyboardEvent) {
  if (props.disabled) return;
  if (event.key === "Escape") {
    close();
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (open.value && activeOption.value) selectOption(activeOption.value);
    else toggle();
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    if (!open.value) open.value = true;
    moveActive(event.key === "ArrowDown" ? 1 : -1);
  }
}

function moveActive(delta: number) {
  if (!props.options.length) return;
  let next = activeIndex.value;
  for (let count = 0; count < props.options.length; count += 1) {
    next = (next + delta + props.options.length) % props.options.length;
    if (!props.options[next]?.disabled) {
      activeIndex.value = next;
      return;
    }
  }
}

onMounted(() => window.addEventListener("pointerdown", onPointerDown, true));
onBeforeUnmount(() => window.removeEventListener("pointerdown", onPointerDown, true));
</script>

<template>
  <div ref="root" class="app-select" :class="{ open, disabled }">
    <button
      class="app-select-button"
      type="button"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
      @keydown="onKeydown"
    >
      <span>{{ selectedOption?.label || placeholder }}</span>
      <ChevronDown :size="16" />
    </button>
    <Transition name="select-pop">
      <div v-if="open" class="app-select-menu" role="listbox">
        <button
          v-for="(option, index) in options"
          :key="`${option.value}-${option.label}`"
          class="app-select-option"
          :class="{ selected: option.value === modelValue, active: index === activeIndex }"
          :disabled="option.disabled"
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          @mouseenter="activeIndex = index"
          @click="selectOption(option)"
        >
          <Check v-if="option.value === modelValue" :size="16" />
          <span v-else class="app-select-check-spacer"></span>
          <span>{{ option.label }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>
