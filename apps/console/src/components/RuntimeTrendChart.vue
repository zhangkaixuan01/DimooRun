<template>
  <figure class="runtime-chart-figure">
    <figcaption class="sr-only" :id="summaryId">{{ summary }}</figcaption>
    <div
      ref="chartRef"
      class="runtime-chart"
      role="img"
      :aria-label="t('runtimeTrendChart')"
      :aria-describedby="summaryId"
    />
  </figure>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

import { usePreferencesStore } from "../stores/preferences";
import { useI18n } from "../i18n/useI18n";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

const preferences = usePreferencesStore();
const { t } = useI18n();
const chartRef = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | undefined;

const props = withDefaults(defineProps<{
  trendPoints?: Array<{
    label: string;
    runs: number;
    successRate: number;
  }>;
}>(), {
  trendPoints: () => [
    { label: "00", runs: 42, successRate: 97 },
    { label: "02", runs: 64, successRate: 98 },
    { label: "04", runs: 58, successRate: 99 },
    { label: "06", runs: 77, successRate: 98 },
    { label: "08", runs: 63, successRate: 97 },
    { label: "10", runs: 82, successRate: 99 },
    { label: "12", runs: 71, successRate: 98 },
    { label: "14", runs: 89, successRate: 99 },
    { label: "16", runs: 66, successRate: 97 },
    { label: "18", runs: 74, successRate: 98 },
    { label: "20", runs: 86, successRate: 99 },
    { label: "22", runs: 92, successRate: 99 },
  ],
});

const labels = computed(() => props.trendPoints.map((point) => point.label));
const runCounts = computed(() => props.trendPoints.map((point) => point.runs));
const successRates = computed(() => props.trendPoints.map((point) => point.successRate));
const summaryId = `runtime-trend-summary-${Math.random().toString(36).slice(2, 10)}`;
const summary = computed(() => props.trendPoints.length === 0
  ? t("noTrendData")
  : props.trendPoints
    .map((point) => `${point.label}: ${point.runs} ${t("runs")}, ${point.successRate}% ${t("successRate")}`)
    .join("; "));

function renderChart() {
  if (!chartRef.value) return;
  chart ??= echarts.init(chartRef.value);
  const dark = preferences.theme === "dark";
  chart.setOption({
    backgroundColor: "transparent",
    color: dark ? ["#77d9a7", "#9aa7ff"] : ["#149465", "#5362d8"],
    grid: { left: 38, right: 18, top: 20, bottom: 28 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: labels.value,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: dark ? "#566274" : "#c6d0dc" } },
      axisLabel: { color: dark ? "#b2bdcb" : "#596a7f" },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: dark ? "#b2bdcb" : "#596a7f" },
      splitLine: { lineStyle: { color: dark ? "#364153" : "#dce4ee" } },
    },
    series: [
      {
        name: t("runs"),
        type: "bar",
        data: runCounts.value,
        barMaxWidth: 18,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
      {
        name: t("successRate"),
        type: "line",
        data: successRates.value,
        smooth: true,
        symbolSize: 6,
      },
    ],
  });
}

function resizeChart() {
  chart?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener("resize", resizeChart);
});
watch(() => preferences.theme, renderChart);
watch(() => props.trendPoints, renderChart, { deep: true });
onUnmounted(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>

<style scoped>
.runtime-chart-figure {
  margin: 0;
}

.runtime-chart {
  width: 100%;
  height: 230px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
