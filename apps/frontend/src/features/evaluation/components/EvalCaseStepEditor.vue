<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import clsx from "clsx";
import { computed, ref, watch } from "vue";
import DropdownSelect from "../../../components/DropdownSelect.vue";
import type { DropdownSelectGroup, DropdownSelectOption } from "../../../components/dropdown";
import type { EvalAssertionTemplate, EvalCaseStep, EvalStepAssertion } from "../../../types";
import type { StepValidation } from "../lib/evalCaseForm";

const categoryOrder = ["语义判定", "Agent 输出", "Opencode 过程", "工作目录文件"];

const props = defineProps<{
  step: EvalCaseStep;
  index: number;
  groupedTemplates: Array<{ category: string; items: EvalAssertionTemplate[] }>;
  validation?: StepValidation;
  showValidation: boolean;
}>();
const emit = defineEmits<{
  title: [value: string];
  input: [value: string];
  addAssertion: [];
  removeAssertion: [assertionId: string];
  template: [payload: { assertionId: string; templateId: string }];
  param: [payload: { assertionId: string; name: string; value: string | number }];
}>();

const categoryFilter = ref("all");
const collapsedAssertionIds = ref<Set<string>>(new Set());
const templateQuery = ref("");
const sortedGroups = computed(() => [...props.groupedTemplates].sort((left, right) => categoryRank(left.category) - categoryRank(right.category) || left.category.localeCompare(right.category)));
const categoryOptions = computed<DropdownSelectOption[]>(() => [
  { value: "all", label: "全部分类", description: `${templateCount(sortedGroups.value)} 个模板` },
  ...sortedGroups.value.map((group) => ({ value: group.category, label: group.category, description: `${group.items.length} 个模板` })),
]);
const matchedTemplateGroups = computed<DropdownSelectGroup[]>(() => {
  const query = normalizeFilterText(templateQuery.value);
  return sortedGroups.value
    .filter((group) => categoryFilter.value === "all" || group.category === categoryFilter.value)
    .map((group) => ({
      label: group.category,
      options: group.items.filter((template) => templateMatches(template, query)).map(templateOption),
    }))
    .filter((group) => group.options.length > 0);
});
const filteredTemplateCount = computed(() => templateCount(matchedTemplateGroups.value));

watch(() => props.groupedTemplates.map((group) => `${group.category}:${group.items.map((item) => item.id).join(",")}`).join("|"), () => {
  if (categoryFilter.value !== "all" && !sortedGroups.value.some((group) => group.category === categoryFilter.value)) {
    categoryFilter.value = "all";
  }
}, { immediate: true });

watch(() => props.step, () => {
  collapsedAssertionIds.value = new Set();
});

watch(() => props.step.assertions.map((assertion) => assertion.id).join("|"), () => {
  const activeIds = new Set(props.step.assertions.map((assertion, index) => assertionKey(assertion, index)));
  collapsedAssertionIds.value = new Set([...collapsedAssertionIds.value].filter((id) => activeIds.has(id)));
});

/** 读取指定判断条件参数值，保证输入控件始终收到可显示的字符串或数字。 */
function paramValue(assertion: EvalStepAssertion, name: string): string | number {
  const value = assertion.assertion_params[name];
  return typeof value === "number" || typeof value === "string" ? value : "";
}

/** 为本地新建但尚未保存的判断条件生成稳定折叠 key。 */
function assertionKey(assertion: EvalStepAssertion, index: number): string {
  return assertion.id || `assertion-${index + 1}`;
}

/** 判断当前判断条件是否处于折叠态。 */
function assertionCollapsed(assertion: EvalStepAssertion, index: number): boolean {
  return collapsedAssertionIds.value.has(assertionKey(assertion, index));
}

/** 切换单个判断条件的折叠状态。 */
function toggleAssertion(assertion: EvalStepAssertion, index: number): void {
  const key = assertionKey(assertion, index);
  const next = new Set(collapsedAssertionIds.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  collapsedAssertionIds.value = next;
}

/** 按产品指定顺序排列已知分类，未知分类稳定追加在末尾。 */
function categoryRank(category: string): number {
  const index = categoryOrder.indexOf(category);
  return index >= 0 ? index : categoryOrder.length;
}

/** 根据模板 id 查找完整模板定义。 */
function templateFor(id: string): EvalAssertionTemplate | undefined {
  for (const group of props.groupedTemplates) {
    const template = group.items.find((item) => item.id === id);
    if (template) return template;
  }
}

/** 当前判断条件的模板下拉分组，确保当前选择不会被过滤条件隐藏。 */
function templateGroupsFor(assertion: EvalStepAssertion): DropdownSelectGroup[] {
  const groups = matchedTemplateGroups.value.map((group) => ({ ...group, options: [...group.options] }));
  const selected = templateFor(assertion.assertion_template_id);
  if (selected && !groups.some((group) => group.options.some((option) => option.value === selected.id))) {
    groups.unshift({ label: "当前选择", options: [templateOption(selected)] });
  }
  return groups;
}

/** 计算模板参数摘要，帮助用户快速判断选择后要填写什么。 */
function paramSummary(template: EvalAssertionTemplate): string {
  const total = template.params_schema.length;
  const required = template.params_schema.filter((param) => param.required).length;
  if (!total) return "无需填写参数";
  if (required === total) return `${total} 个必填参数`;
  if (!required) return `${total} 个可选参数`;
  return `${required} 个必填 / ${total} 个参数`;
}

/** 将模板定义转换为下拉选项，复用下拉组件的分组展示能力。 */
function templateOption(template: EvalAssertionTemplate): DropdownSelectOption {
  return {
    value: template.id,
    label: template.name,
    description: `${paramSummary(template)} · ${template.description}`,
  };
}

/** 判断模板是否匹配当前关键词过滤器。 */
function templateMatches(template: EvalAssertionTemplate, query: string): boolean {
  if (!query) return true;
  return normalizeFilterText([template.name, template.description, template.category, template.id].join(" ")).includes(query);
}

/** 统一过滤文本，避免大小写和前后空白影响匹配。 */
function normalizeFilterText(value: string): string {
  return value.trim().toLowerCase();
}

/** 统计模板数量，兼容模板组和下拉选项组。 */
function templateCount(groups: Array<{ items?: unknown[]; options?: unknown[] }>): number {
  return groups.reduce((total, group) => total + (group.items?.length ?? group.options?.length ?? 0), 0);
}
</script>

<template>
  <section class="scenario-step-editor">
    <header class="scenario-editor-head">
      <div>
        <span>当前步骤 {{ index + 1 }}</span>
        <h3>{{ step.title || `步骤 ${index + 1}` }}</h3>
      </div>
      <small :class="clsx(showValidation && !validation?.complete && 'invalid')">{{ validation?.message ?? "编辑中" }}</small>
    </header>

    <label class="field-label">
      步骤标题
      <input :value="step.title" :placeholder="`步骤 ${index + 1}`" @input="emit('title', ($event.target as HTMLInputElement).value)">
    </label>

    <label class="field-label">
      输入给 Agent
      <textarea :value="step.input" placeholder="这一轮发送给 Agent 的内容，例如：请根据当前目录生成 README.md" required @input="emit('input', ($event.target as HTMLTextAreaElement).value)" />
    </label>

    <section class="scenario-template-panel">
      <div class="scenario-panel-heading">
        <div>
          <strong>判断条件</strong>
          <span>{{ step.assertions.length }} 个条件，全部通过才算本步骤通过</span>
        </div>
        <button class="secondary-button compact" type="button" @click="emit('addAssertion')">添加判断条件</button>
      </div>

      <div class="assertion-filter-row">
        <label class="field-label compact">
          分类过滤
          <DropdownSelect v-model="categoryFilter" :options="categoryOptions" aria-label="判断模板分类过滤" compact />
        </label>
        <label class="field-label compact">
          关键词过滤
          <input v-model="templateQuery" placeholder="按名称、说明或模板 ID 过滤">
        </label>
      </div>

      <div class="scenario-assertion-list">
        <article
          v-for="(assertion, assertionIndex) in step.assertions"
          :key="assertionKey(assertion, assertionIndex)"
          :class="clsx('scenario-assertion-card', assertionCollapsed(assertion, assertionIndex) && 'collapsed')"
        >
          <header>
            <button
              class="scenario-assertion-summary"
              type="button"
              :aria-expanded="!assertionCollapsed(assertion, assertionIndex)"
              @click="toggleAssertion(assertion, assertionIndex)"
            >
              <div>
                <strong>判断条件 {{ assertionIndex + 1 }}</strong>
                <span>{{ templateFor(assertion.assertion_template_id)?.category ?? "未加载" }}</span>
              </div>
              <ChevronDown :class="clsx(!assertionCollapsed(assertion, assertionIndex) && 'open')" :size="16" />
            </button>
            <button class="secondary-button compact" type="button" :disabled="step.assertions.length === 1" @click="emit('removeAssertion', assertion.id)">删除</button>
          </header>

          <Transition name="history-collapse">
            <div v-if="!assertionCollapsed(assertion, assertionIndex)" class="scenario-assertion-body">
              <label class="field-label compact">
                判断模板
                <DropdownSelect
                  :model-value="assertion.assertion_template_id"
                  :groups="templateGroupsFor(assertion)"
                  :placeholder="filteredTemplateCount ? '选择判断模板' : '没有匹配的模板'"
                  aria-label="判断模板"
                  @update:model-value="emit('template', { assertionId: assertion.id, templateId: $event })"
                />
                <span class="field-help">当前筛选出 {{ filteredTemplateCount }} 个模板。切换模板后，本条件的参数会自动刷新。</span>
              </label>

              <div class="assertion-template-summary">
                <span>当前判断条件</span>
                <strong>{{ templateFor(assertion.assertion_template_id)?.name ?? "模板加载中" }}</strong>
                <p>{{ templateFor(assertion.assertion_template_id)?.description ?? "正在加载可用判断模板..." }}</p>
              </div>

              <section class="scenario-param-grid">
                <label v-for="param in templateFor(assertion.assertion_template_id)?.params_schema ?? []" :key="param.name" class="field-label">
                  {{ param.label }}
                  <textarea
                    v-if="param.type === 'textarea'"
                    :value="paramValue(assertion, param.name)"
                    :placeholder="param.placeholder"
                    :required="param.required"
                    @input="emit('param', { assertionId: assertion.id, name: param.name, value: ($event.target as HTMLTextAreaElement).value })"
                  />
                  <input
                    v-else-if="param.type === 'number'"
                    :value="paramValue(assertion, param.name)"
                    type="number"
                    step="0.01"
                    :min="param.min ?? undefined"
                    :max="param.max ?? undefined"
                    :required="param.required"
                    @input="emit('param', { assertionId: assertion.id, name: param.name, value: Number(($event.target as HTMLInputElement).value) })"
                  >
                  <input
                    v-else
                    :value="paramValue(assertion, param.name)"
                    :placeholder="param.placeholder"
                    :required="param.required"
                    @input="emit('param', { assertionId: assertion.id, name: param.name, value: ($event.target as HTMLInputElement).value })"
                  >
                  <span v-if="param.help" class="field-help">{{ param.help }}</span>
                </label>
              </section>
            </div>
          </Transition>
        </article>
      </div>
    </section>
  </section>
</template>
