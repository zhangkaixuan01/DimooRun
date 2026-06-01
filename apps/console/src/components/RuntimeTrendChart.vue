<template>
  <div ref="chartRef" class="runtime-chart" role="img" :aria-label="t('runtimeTrendChart')" />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
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
      data: ["00", "02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22"],
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
        name: "runs",
        type: "bar",
        data: [42, 64, 58, 77, 63, 82, 71, 89, 66, 74, 86, 92],
        barMaxWidth: 18,
        itemStyle: { borderRadius: [4, 4, 0, 0] },
      },
      {
        name: "success",
        type: "line",
        data: [97, 98, 99, 98, 97, 99, 98, 99, 97, 98, 99, 99],
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
onUnmounted(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
});
</script>

<style scoped>
.runtime-chart {
  width: 100%;
  height: 230px;
}
</style>
