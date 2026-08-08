<template>
  <div :style="{ height }">
    <canvas ref="canvas" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Chart as ChartJS,
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js'

ChartJS.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
)

const props = defineProps({
  type: { type: String, required: true },
  data: { type: Object, required: true },
  options: { type: Object, default: () => ({}) },
  height: { type: String, default: '260px' },
})

const canvas = ref(null)
let chart = null

function render() {
  if (!canvas.value) return
  if (!chart) {
    chart = new ChartJS(canvas.value, {
      type: props.type,
      data: props.data,
      options: props.options,
    })
    return
  }
  chart.data = props.data
  chart.options = props.options
  chart.update()
}

onMounted(render)

watch(
  () => [props.data, props.type, props.options],
  render,
  { deep: true },
)

onBeforeUnmount(() => {
  if (chart) {
    chart.destroy()
    chart = null
  }
})
</script>
