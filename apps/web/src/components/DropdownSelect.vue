<script setup lang="ts">
import clsx from "clsx";
import { Check, ChevronDown } from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import type { DropdownSelectGroup, DropdownSelectOption } from "./dropdown";

type DropdownSelectEntry = {
  option: DropdownSelectOption;
  groupLabel?: string;
  index: number;
};

const props = withDefaults(defineProps<{
  modelValue?: string | null;
  options?: DropdownSelectOption[];
  groups?: DropdownSelectGroup[];
  placeholder?: string;
  ariaLabel?: string;
  disabled?: boolean;
  compact?: boolean;
}>(), {
  modelValue: "",
  options: () => [],
  groups: () => [],
  placeholder: "请选择",
  ariaLabel: "选择选项",
  disabled: false,
  compact: false,
});

const emit = defineEmits<{
  "update:modelValue": [value: string];
  change: [option: DropdownSelectOption | null];
}>();

const root = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const open = ref(false);
const activeIndex = ref(-1);
const id = useId();
const listboxId = `${id}-listbox`;

const entries = computed<DropdownSelectEntry[]>(() => {
  const sourceGroups = props.groups.length > 0 ? props.groups : [{ options: props.options }];
  const next: DropdownSelectEntry[] = [];
  for (const group of sourceGroups) {
    for (const option of group.options) next.push({ option, groupLabel: group.label, index: next.length });
  }
  return next;
});

const groupedEntries = computed(() => {
  const sourceGroups = props.groups.length > 0 ? props.groups : [{ options: props.options }];
  let cursor = 0;
  return sourceGroups
    .map((group) => ({
      label: group.label,
      entries: group.options.map((option) => ({ option, groupLabel: group.label, index: cursor++ })),
    }))
    .filter((group) => group.entries.length > 0);
});

const selectedEntry = computed(() => entries.value.find((entry) => entry.option.value === props.modelValue) ?? null);
const activeEntryId = computed(() => {
  const entry = entries.value[activeIndex.value];
  return entry ? optionId(entry.index) : undefined;
});

watch(() => props.modelValue, () => {
  if (!open.value) activeIndex.value = selectedEntry.value?.index ?? firstEnabledIndex();
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", closeOnOutsidePointer);
});

/** 打开下拉面板，并让当前选中项成为键盘导航的起点。 */
async function openMenu(preferredIndex = selectedEntry.value?.index ?? firstEnabledIndex()): Promise<void> {
  if (props.disabled || entries.value.length === 0) return;
  open.value = true;
  activeIndex.value = enabledIndexNear(preferredIndex);
  document.addEventListener("pointerdown", closeOnOutsidePointer);
  await nextTick();
}

/** 关闭面板，可选地把焦点还给触发按钮。 */
function closeMenu(restoreFocus = false): void {
  open.value = false;
  document.removeEventListener("pointerdown", closeOnOutsidePointer);
  if (restoreFocus) trigger.value?.focus();
}

/** 切换面板开合状态。 */
function toggleMenu(): void {
  if (open.value) closeMenu();
  else void openMenu();
}

/** 选中一个可用选项，并向父组件同步值。 */
function choose(entry: DropdownSelectEntry): void {
  if (entry.option.disabled) return;
  emit("update:modelValue", entry.option.value);
  emit("change", entry.option);
  closeMenu(true);
}

/** 处理方向键、Enter、Space 和 Escape 等常用下拉键盘操作。 */
function handleKeydown(event: KeyboardEvent): void {
  if (props.disabled) return;
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    if (!open.value) {
      void openMenu(event.key === "ArrowDown" ? firstEnabledIndex() : lastEnabledIndex());
      return;
    }
    moveActive(event.key === "ArrowDown" ? 1 : -1);
  }
  if (event.key === "Home" || event.key === "End") {
    event.preventDefault();
    activeIndex.value = event.key === "Home" ? firstEnabledIndex() : lastEnabledIndex();
  }
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!open.value) {
      void openMenu();
      return;
    }
    const entry = entries.value[activeIndex.value];
    if (entry) choose(entry);
  }
  if (event.key === "Escape" && open.value) {
    event.preventDefault();
    closeMenu(true);
  }
}

/** 将当前高亮项移动到下一个可用选项。 */
function moveActive(delta: 1 | -1): void {
  if (entries.value.every((entry) => entry.option.disabled)) return;
  let next = activeIndex.value;
  for (let checked = 0; checked < entries.value.length; checked += 1) {
    next = (next + delta + entries.value.length) % entries.value.length;
    if (!entries.value[next]?.option.disabled) {
      activeIndex.value = next;
      return;
    }
  }
}

/** 鼠标移入选项时同步键盘高亮位置。 */
function activate(entry: DropdownSelectEntry): void {
  if (!entry.option.disabled) activeIndex.value = entry.index;
}

/** 点击组件外部时关闭面板。 */
function closeOnOutsidePointer(event: PointerEvent): void {
  const target = event.target;
  if (!(target instanceof Node) || root.value?.contains(target)) return;
  closeMenu();
}

/** 返回指定位置附近的可用选项索引。 */
function enabledIndexNear(index: number): number {
  if (!entries.value[index]?.option.disabled) return index;
  const next = entries.value.find((entry) => !entry.option.disabled);
  return next?.index ?? -1;
}

/** 返回第一个可用选项索引。 */
function firstEnabledIndex(): number {
  return entries.value.find((entry) => !entry.option.disabled)?.index ?? -1;
}

/** 返回最后一个可用选项索引。 */
function lastEnabledIndex(): number {
  for (let index = entries.value.length - 1; index >= 0; index -= 1) {
    if (!entries.value[index]?.option.disabled) return index;
  }
  return -1;
}

/** 生成稳定的选项 id，用于 aria-activedescendant。 */
function optionId(index: number): string {
  return `${id}-option-${index}`;
}
</script>

<template>
  <div
    ref="root"
    :class="clsx('dropdown-select', compact && 'compact', open && 'open', disabled && 'disabled')"
    @keydown="handleKeydown"
  >
    <button
      ref="trigger"
      class="dropdown-trigger"
      type="button"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      :aria-controls="listboxId"
      aria-haspopup="listbox"
      @click="toggleMenu"
    >
      <span class="dropdown-trigger-copy">
        <span :class="clsx('dropdown-value', !selectedEntry && 'placeholder')">{{ selectedEntry?.option.label ?? placeholder }}</span>
        <small v-if="selectedEntry?.option.description">{{ selectedEntry.option.description }}</small>
      </span>
      <ChevronDown class="dropdown-chevron" :size="18" />
    </button>
    <Transition name="dropdown-menu">
      <div
        v-if="open"
        :id="listboxId"
        class="dropdown-popover"
        role="listbox"
        :aria-label="ariaLabel"
        :aria-activedescendant="activeEntryId"
      >
        <template v-for="group in groupedEntries" :key="group.label ?? 'default'">
          <div v-if="group.label" class="dropdown-group-label">{{ group.label }}</div>
          <button
            v-for="entry in group.entries"
            :id="optionId(entry.index)"
            :key="`${entry.index}:${entry.option.value}`"
            :class="clsx('dropdown-option', selectedEntry?.index === entry.index && 'selected', activeIndex === entry.index && 'active')"
            type="button"
            role="option"
            :aria-selected="selectedEntry?.index === entry.index"
            :disabled="entry.option.disabled"
            @mouseenter="activate(entry)"
            @click="choose(entry)"
          >
            <span>
              <strong>{{ entry.option.label }}</strong>
              <small v-if="entry.option.description">{{ entry.option.description }}</small>
            </span>
            <Check v-if="selectedEntry?.index === entry.index" :size="16" />
          </button>
        </template>
      </div>
    </Transition>
  </div>
</template>
