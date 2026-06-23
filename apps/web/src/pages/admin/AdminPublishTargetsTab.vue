<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { PublishGateCheckDefinition, PublishGateCheckId, PublishGateExpression, PublishTarget } from "../../types";
import AdminGateNodeEditor from "./AdminGateNodeEditor.vue";

const props = defineProps<{ targets: PublishTarget[]; checks: PublishGateCheckDefinition[] }>();
const emit = defineEmits<{ update: [targetId: string, payload: { enabled: boolean; gate_expression: PublishGateExpression }] }>();

const selectedTargetId = ref("");
const enabledDraft = ref(true);
const expressionDraft = ref<PublishGateExpression>(defaultExpression());

const selectedTarget = computed(() => props.targets.find((target) => target.id === selectedTargetId.value) ?? props.targets[0] ?? null);
const checkOptions = computed(() => props.checks);
const checkById = computed(() => new Map(props.checks.map((check) => [check.id, check])));

watch(
  () => props.targets,
  () => {
    if (!selectedTargetId.value && props.targets.length) selectedTargetId.value = props.targets[0].id;
    if (selectedTargetId.value && !props.targets.some((target) => target.id === selectedTargetId.value)) {
      selectedTargetId.value = props.targets[0]?.id ?? "";
    }
    syncDraft();
  },
  { immediate: true },
);

watch(selectedTargetId, syncDraft);

function syncDraft(): void {
  const target = selectedTarget.value;
  if (!target) return;
  enabledDraft.value = target.enabled;
  expressionDraft.value = cloneExpression(target.gate_expression || defaultExpression());
}

function save(): void {
  const target = selectedTarget.value;
  if (!target) return;
  emit("update", target.id, { enabled: enabledDraft.value, gate_expression: expressionDraft.value });
}

function addCheck(group: PublishGateExpression): void {
  if (group.type !== "group") return;
  const check = checkOptions.value[0];
  if (!check) return;
  group.children.push({ type: "check", check_id: check.id, params: defaultParams(check) });
}

function addGroup(group: PublishGateExpression): void {
  if (group.type !== "group") return;
  group.children.push({ type: "group", op: "and", children: [{ type: "check", check_id: "min_responses", params: { min: 1 } }] });
}

function removeChild(group: PublishGateExpression, index: number): void {
  if (group.type !== "group" || group.children.length <= 1) return;
  group.children.splice(index, 1);
}

function updateGroupOp(group: PublishGateExpression, value: "and" | "or"): void {
  if (group.type !== "group") return;
  group.op = value;
}

function updateCheckId(node: PublishGateExpression, value: string): void {
  if (node.type !== "check") return;
  const definition = checkById.value.get(value as PublishGateCheckId);
  if (!definition) return;
  node.check_id = definition.id;
  node.params = defaultParams(definition);
}

function updateParam(node: PublishGateExpression, name: string, value: number): void {
  if (node.type !== "check") return;
  node.params = { ...(node.params ?? {}), [name]: value };
}

function defaultParams(check: PublishGateCheckDefinition): Record<string, unknown> {
  return Object.fromEntries(check.params_schema.map((param) => [param.name, param.default ?? param.min ?? 0]));
}

function defaultExpression(): PublishGateExpression {
  return {
    type: "group",
    op: "and",
    children: [
      { type: "check", check_id: "min_responses", params: { min: 1 } },
      { type: "check", check_id: "no_negative_score", params: {} },
    ],
  };
}

function cloneExpression(expression: PublishGateExpression): PublishGateExpression {
  return JSON.parse(JSON.stringify(expression)) as PublishGateExpression;
}

function expressionSummary(expression: PublishGateExpression): string {
  if (expression.type === "check") return checkById.value.get(expression.check_id)?.label ?? expression.check_id;
  const op = expression.op === "and" ? "全部满足" : "任一满足";
  return `${op} · ${expression.children.length} 条规则`;
}
</script>

<template>
  <div class="admin-split-layout publish-target-settings">
    <aside class="admin-side-panel">
      <div class="panel-title-row compact">
        <div>
          <h2>发布源</h2>
          <p>固定发布源只可启停，并配置门禁表达式。</p>
        </div>
      </div>
      <div class="admin-list">
        <button
          v-for="target in targets"
          :key="target.id"
          type="button"
          :class="{ active: selectedTarget?.id === target.id }"
          @click="selectedTargetId = target.id"
        >
          <strong>{{ target.name }}</strong>
          <span>{{ target.enabled ? "启用" : "禁用" }} · {{ expressionSummary(target.gate_expression) }}</span>
        </button>
      </div>
    </aside>

    <section v-if="selectedTarget" class="primary-panel admin-card publish-gate-panel">
      <div class="panel-title-row">
        <div>
          <h2>{{ selectedTarget.name }}</h2>
          <p>{{ selectedTarget.description }}</p>
        </div>
        <label class="switch-line">
          <input v-model="enabledDraft" type="checkbox" />
          <span>{{ enabledDraft ? "启用" : "禁用" }}</span>
        </label>
      </div>

      <div class="publish-gate-editor">
        <AdminGateNodeEditor
          :node="expressionDraft"
          :checks="checkOptions"
          :check-by-id="checkById"
          root
          @add-check="addCheck"
          @add-group="addGroup"
          @remove-child="removeChild"
          @update-group-op="updateGroupOp"
          @update-check-id="updateCheckId"
          @update-param="updateParam"
        />
      </div>

      <div class="button-row">
        <button class="secondary-button" type="button" @click="syncDraft">重置</button>
        <button class="primary-button" type="button" @click="save">保存发布源配置</button>
      </div>
    </section>
  </div>
</template>
