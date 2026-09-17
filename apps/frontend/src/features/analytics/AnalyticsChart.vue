<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { init, use, type EChartsType } from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { AnalyticsBucket } from "./types";

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer]);
const props = defineProps<{ rows: AnalyticsBucket[]; kind: "creation" | "visits"; monthly: boolean }>();
const emit = defineEmits<{ month: [value: string] }>();
const host = ref<HTMLElement | null>(null);
let chart: EChartsType | undefined;
let observer: ResizeObserver | undefined;

/** 同步聚合序列，null 保留为未采集的折线空段。 */
function render(): void {
  const styles = host.value ? getComputedStyle(host.value) : undefined;
  const color = (name: string, fallback: string) => styles?.getPropertyValue(name).trim() || fallback;
  chart?.setOption({
    color: [color("--blue", "#2563eb"), color("--green", "#12805c")],
    textStyle: { color: color("--muted", "#64748b"), fontFamily: styles?.fontFamily || "sans-serif" },
    tooltip: { trigger: "axis", confine: true },
    legend: { show: props.kind === "visits", top: 0 },
    grid: { top: 42, left: 52, right: 24, bottom: 44 },
    xAxis: { type: "category", data: props.rows.map((row) => props.monthly ? row.date.slice(0, 7) : row.date.slice(5)), axisLabel: { hideOverlap: true } },
    yAxis: { type: "value", minInterval: 1 },
    series: props.kind === "creation"
      ? [{ name: "新增 Skill", type: "bar", barMaxWidth: 36, itemStyle: { borderRadius: [5, 5, 0, 0] }, data: props.rows.map((row) => row.new_skills) }]
      : [{ name: "访问次数 PV", type: "line", showSymbol: false, connectNulls: false, data: props.rows.map((row) => row.pv) },
        { name: "访问人数 UV", type: "line", showSymbol: false, connectNulls: false, data: props.rows.map((row) => row.uv) }],
  }, true);
}
onMounted(() => {
  chart = init(host.value!, undefined, { renderer: "svg" });
  chart.on("click", (event) => { if (props.monthly && typeof event.dataIndex === "number") emit("month", props.rows[event.dataIndex]!.date); });
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value!);
  render();
});
watch(() => [props.rows, props.monthly, props.kind], render);
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose(); });
</script>

<template><div ref="host" class="analytics-chart" role="img" :aria-label="kind === 'creation' ? '新增 Skill 趋势，精确数值见趋势数据表' : '访问次数和访问人数趋势，精确数值见趋势数据表'" /></template>
<style scoped>.analytics-chart { width: 100%; height: 300px; overflow: hidden; }</style>
