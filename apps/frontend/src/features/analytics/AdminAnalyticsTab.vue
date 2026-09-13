<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from "vue";
import { withAppBase } from "../../lib/navigation";
import { drillMonth, presetRange, shanghaiToday } from "./dates";
import { useAnalytics } from "./useAnalytics";
import type { AnalyticsRange } from "./types";

const AnalyticsChart = defineAsyncComponent(() => import("./AnalyticsChart.vue"));
const { range, data, loading, error, load } = useAnalytics();
const draft = ref<AnalyticsRange>({ ...range.value });
const today = shanghaiToday();
const preset = ref("year");
const metrics = computed(() => data.value ? [
  { name: "当前 Skill 总量", value: data.value.metrics.total_skills, note: "包含归档 Skill" },
  { name: "期间新增 Skill", value: data.value.metrics.new_skills, note: "首次创建，不含版本更新" },
  { name: "访问次数 PV", value: data.value.metrics.pv, note: "成功进入 Skill 详情页" },
  { name: "访问人数 UV", value: data.value.metrics.uv, note: "所选期间按 actor 去重" },
] : []);

/** 提交日期筛选并保持已显示结果与其实际范围一致。 */
function apply(): void { void load({ ...draft.value }); }
/** 选择预设时同步日/月粒度。 */
function selectPreset(value: "current" | "previous" | "year"): void {
  preset.value = value; draft.value = presetRange(value); apply();
}
/** 点击月份下钻至当月日趋势。 */
function selectMonth(value: string): void { preset.value = "custom"; draft.value = drillMonth(value); apply(); }
/** 格式化指标并区分未采集与零。 */
function count(value: number | null): string { return value === null ? "未采集" : value.toLocaleString("zh-CN"); }
/** 用统一统计时区显示更新时间。 */
function timestamp(value: string): string { return new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" }); }
onMounted(apply);
</script>

<template>
  <div class="analytics-dashboard" :aria-busy="loading">
    <header class="analytics-heading"><div><p class="analytics-eyebrow">SKILLHUB · 运营数据</p><h1>运营看板</h1><p>了解内容增长与使用热度</p></div><button class="secondary-button" :disabled="loading" @click="apply">{{ loading ? '加载中…' : '刷新数据' }}</button></header>
    <section class="primary-panel analytics-filters" aria-label="统计日期筛选">
      <div class="analytics-presets"><button v-for="item in ([['current', '本月'], ['previous', '上月'], ['year', '近 12 个月']] as const)" :key="item[0]" :class="['secondary-button', { selected: preset === item[0] }]" @click="selectPreset(item[0])">{{ item[1] }}</button></div>
      <form class="analytics-dates" @submit.prevent="preset = 'custom'; apply()"><label>起始日期<input v-model="draft.start_date" aria-label="起始日期" type="date" min="2000-01-01" :max="today" required @change="preset = 'custom'" /></label><label>截止日期<input v-model="draft.end_date" aria-label="截止日期" type="date" :min="draft.start_date" :max="today" required @change="preset = 'custom'" /></label><label>统计粒度<select v-model="draft.granularity" aria-label="统计粒度"><option value="month">按月</option><option value="day">按日</option></select></label><button class="primary-button" type="submit">查询</button></form>
    </section>
    <div v-if="error" class="analytics-error" role="alert">{{ error }} <button class="secondary-button" @click="apply">重试</button></div>
    <p v-if="loading && !data" role="status">正在汇总运营数据…</p>
    <template v-if="data">
      <div class="analytics-period"><strong>{{ data.start_date }} 至 {{ data.end_date }}{{ data.end_date === today ? '（截至当前）' : '' }}</strong><span v-if="data.includes_demo" class="analytics-demo">包含模拟数据</span><span>北京时间 · 更新于 {{ timestamp(data.generated_at) }}</span></div>
      <section class="analytics-metrics"><article v-for="metric in metrics" :key="metric.name" class="primary-panel analytics-metric"><span>{{ metric.name }}</span><strong>{{ count(metric.value) }}</strong><small>{{ metric.note }}</small></article></section>
      <div class="analytics-plots">
        <section class="primary-panel analytics-panel"><h2>Skill 新增趋势</h2><p>{{ data.granularity === 'month' ? '点击月份查看日趋势' : '每日首次创建的 Skill 数量' }}</p><AnalyticsChart :rows="data.trend" kind="creation" :monthly="data.granularity === 'month'" @month="selectMonth" /></section>
        <section class="primary-panel analytics-panel"><h2>访问趋势</h2><p>UV 按各时间桶独立去重，不按日累加</p><AnalyticsChart :rows="data.trend" kind="visits" :monthly="data.granularity === 'month'" @month="selectMonth" /><p v-if="data.coverage !== 'complete'" class="analytics-note">{{ data.coverage === 'none' ? '所选期间尚未采集访问数据。' : '所选期间包含未采集时段，仅展示已有数据。' }}</p></section>
      </div>
      <section class="primary-panel analytics-panel"><h2>热门 Skill · Top 10</h2><p>按访问次数排序，已删除内容保留历史数据</p><div class="analytics-table-wrap"><table><thead><tr><th>排名</th><th>Skill</th><th>负责人</th><th>访问次数 PV</th><th>访问人数 UV</th></tr></thead><tbody><tr v-for="(item, index) in data.popular" :key="item.skill_id"><td>{{ index + 1 }}</td><td><span v-if="item.deleted">{{ item.name }} · 已删除</span><a v-else :href="withAppBase(`/?section=skills&skill=${encodeURIComponent(item.skill_id)}&tab=overview`)">{{ item.name }}</a></td><td>{{ item.owner_ref }}</td><td>{{ count(item.pv) }}</td><td>{{ count(item.uv) }}</td></tr></tbody></table></div><p v-if="!data.popular.length" class="analytics-empty">{{ data.coverage === 'none' ? '访问采集尚未覆盖此期间' : '此期间暂无 Skill 访问' }}</p></section>
      <details class="primary-panel analytics-panel"><summary>查看趋势数据表</summary><div class="analytics-table-wrap"><table><thead><tr><th>日期</th><th>新增 Skill</th><th>PV</th><th>UV</th><th>采集覆盖</th></tr></thead><tbody><tr v-for="row in data.trend" :key="row.date"><td>{{ row.date }}</td><td>{{ count(row.new_skills) }}</td><td>{{ count(row.pv) }}</td><td>{{ count(row.uv) }}</td><td>{{ { none: '未采集', partial: '部分采集', complete: '完整' }[row.coverage] }}</td></tr></tbody></table></div></details>
      <footer class="analytics-note"><p>{{ data.creation_history_note }}</p><p>正式访问采集开始：{{ timestamp(data.visits_started_at) }}<template v-if="data.demo_started_at">；模拟数据覆盖起点：{{ timestamp(data.demo_started_at) }}</template>。UV 统一按 actor 去重，访问量不代表执行次数。</p></footer>
    </template>
  </div>
</template>

<style scoped>
.analytics-dashboard { display: grid; gap: 20px; min-width: 0; }
.analytics-heading, .analytics-period { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.analytics-heading h1 { margin: 4px 0; font-size: 28px; }
.analytics-heading p, .analytics-panel p { color: var(--muted, #64748b); margin: 4px 0 10px; }
.analytics-eyebrow { font-size: 11px; letter-spacing: .15em; }
.analytics-filters { display: flex; justify-content: space-between; align-items: end; gap: 16px; padding: 18px; flex-wrap: wrap; }
.analytics-presets, .analytics-dates { display: flex; align-items: end; gap: 10px; flex-wrap: wrap; }
.analytics-dates label { display: grid; gap: 5px; font-size: 12px; }
.analytics-dates input, .analytics-dates select { padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; background: var(--surface, white); color: inherit; }
.analytics-presets .selected { border-color: #3b82f6; color: #2563eb; background: #eff6ff; }
.analytics-period { font-size: 12px; color: #64748b; }
.analytics-period strong { color: inherit; margin-right: auto; }
.analytics-demo { background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 5px; }
.analytics-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.analytics-metric { display: grid; gap: 12px; padding: 22px; border-top: 3px solid #3b82f6; }
.analytics-metric strong { font-size: 32px; font-variant-numeric: tabular-nums; }
.analytics-metric small { color: #64748b; }
.analytics-plots { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.analytics-panel { padding: 20px; min-width: 0; }
.analytics-panel h2 { font-size: 17px; margin: 0 0 6px; }
.analytics-panel p, .analytics-note { font-size: 12px; color: #64748b; line-height: 1.7; }
.analytics-table-wrap { overflow-x: auto; margin-top: 15px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; white-space: nowrap; }
th, td { padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
th { color: #64748b; font-weight: 500; background: #f8fafc; }
td a { color: #2563eb; text-decoration: none; }
.analytics-empty { text-align: center; padding: 24px; }
.analytics-error { padding: 14px; border: 1px solid #fecaca; color: #991b1b; border-radius: 8px; }
summary { cursor: pointer; font-weight: 600; }
@media (max-width: 1000px) { .analytics-plots { grid-template-columns: 1fr; } .analytics-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 540px) { .analytics-metric { padding: 14px; } .analytics-metric strong { font-size: 25px; } .analytics-panel { padding: 12px; } .analytics-dates label { flex: 1; min-width: 130px; } }
</style>
