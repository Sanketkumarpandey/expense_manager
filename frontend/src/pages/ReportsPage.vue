<template>
  <div class="space-y-6">
    <div>
      <p class="text-sm text-ink-gray-5">Report period: {{ periodLabel }}</p>
      <p class="text-xs text-ink-gray-4">
        The spending trend covers the last 6 months; budget reports show the current state.
      </p>
    </div>

    <ResourceState :resource="combined" label="your reports">
      <template #skeleton>
        <div class="space-y-6">
          <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-lg bg-surface-gray-2" />
          </div>
          <div v-for="i in 2" :key="`c${i}`" class="h-48 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <div class="space-y-6">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <div
            v-for="card in summaryCards"
            :key="card.label"
            class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
          >
            <p class="text-sm text-ink-gray-5">{{ card.label }}</p>
            <p class="mt-3 text-2xl font-semibold tracking-tight text-ink-gray-9">
              {{ card.value }}
            </p>
            <p class="mt-1 text-xs text-ink-gray-5">{{ card.sub }}</p>
          </div>
        </div>

        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <div class="flex items-center gap-2">
            <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
              <LineChart class="size-4" />
            </span>
            <div>
              <p class="text-sm font-medium text-ink-gray-9">Monthly spending trend</p>
              <p class="text-xs text-ink-gray-5">Last 6 months breakdown</p>
            </div>
          </div>

          <p v-if="!trendHasData" class="mt-6 text-center text-sm text-ink-gray-5">
            No expenses in the last 6 months.
          </p>
          <div v-else class="mt-4">
            <ChartBox type="line" :data="trendChartData" :options="trendChartOptions" height="280px" />
          </div>
        </div>

        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <div class="flex items-center gap-2">
            <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
              <BarChart3 class="size-4" />
            </span>
            <div>
              <p class="text-sm font-medium text-ink-gray-9">Category breakdown</p>
              <p class="text-xs text-ink-gray-5">{{ periodLabel }}</p>
            </div>
          </div>

          <p v-if="breakdown.length === 0" class="mt-6 text-center text-sm text-ink-gray-5">
            No expenses in this period.
          </p>
          <div v-else class="mt-4">
            <ChartBox type="bar" :data="breakdownChartData" :options="breakdownChartOptions" height="280px" />
          </div>
        </div>

        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <div class="flex items-center gap-2">
            <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
              <Wallet class="size-4" />
            </span>
            <div>
              <p class="text-sm font-medium text-ink-gray-9">Budget utilization</p>
              <p class="text-xs text-ink-gray-5">Active budgets, current state</p>
            </div>
          </div>

          <p v-if="budgetSummary.length === 0" class="mt-6 text-center text-sm text-ink-gray-5">
            No active budgets.
          </p>
          <div v-else class="mt-4 space-y-3">
            <div
              v-for="row in budgetSummary"
              :key="row.category"
              class="flex items-center gap-3"
            >
              <span class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-lg">
                {{ row.category_icon || '🏷️' }}
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <p class="truncate text-sm font-medium text-ink-gray-9">{{ row.category_name }}</p>
                  <span
                    v-if="row.is_overspent"
                    class="rounded bg-surface-red-1 px-1.5 py-0.5 text-xs font-medium text-ink-red-5"
                  >
                    Over budget
                  </span>
                </div>
                <div class="mt-1 flex items-center gap-2">
                  <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="row.is_overspent ? 'bg-surface-red-6' : 'bg-surface-blue-3'"
                      :style="{ width: Math.min(row.percentage, 100) + '%' }"
                    />
                  </div>
                  <p class="shrink-0 text-xs" :class="row.is_overspent ? 'text-ink-red-5' : 'text-ink-gray-5'">
                    {{ inr(row.spent_amount) }} of {{ inr(row.allocated_amount) }}
                    · {{ inr(row.remaining_amount) }} left
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ResourceState>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watchEffect } from 'vue'
import { request } from 'frappe-ui'
import BarChart3 from '~icons/lucide/bar-chart-3'
import LineChart from '~icons/lucide/line-chart'
import Wallet from '~icons/lucide/wallet'
import ResourceState from '@/components/ResourceState.vue'
import ChartBox from '@/components/ChartBox.vue'

const now = new Date()
const pad = (n) => String(n).padStart(2, '0')
const toLocalDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

const defaultFrom = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`
const defaultTo = toLocalDate(now)

const periodLabel = computed(() => `${defaultFrom} – ${defaultTo}`)

const loading = ref(true)
const error = ref(null)
const loadedOnce = ref(false)

const summary = ref(null)
const trend = ref([])
const breakdown = ref([])
const budgetSummary = ref([])

async function getReport(method, params) {
  const res = await request({ url: `/api/method/${method}`, params })
  if (res.message && res.message.success === false) return null
  return res.message
}

async function reload() {
  loading.value = true
  error.value = null

  const [s, t, b, bs] = await Promise.allSettled([
    getReport('expense_manager.api.reports.get_expense_summary', {
      date_from: defaultFrom,
      date_to: defaultTo,
    }),
    getReport('expense_manager.api.reports.get_spending_trend', { months: 6 }),
    getReport('expense_manager.api.reports.get_category_breakdown', {
      date_from: defaultFrom,
      date_to: defaultTo,
    }),
    getReport('expense_manager.api.reports.get_budget_summary'),
  ])

  summary.value = s.status === 'fulfilled' ? s.value : null
  trend.value = t.status === 'fulfilled' && Array.isArray(t.value) ? t.value : []
  breakdown.value = b.status === 'fulfilled' && Array.isArray(b.value) ? b.value : []
  budgetSummary.value = bs.status === 'fulfilled' && Array.isArray(bs.value) ? bs.value : []

  const failures = [s, t, b, bs].filter((r) => r.status === 'rejected')
  if (failures.length) {
    error.value = 'Some reports could not be loaded.'
  } else {
    loadedOnce.value = true
  }
  loading.value = false
}

reload()

function reloadIfVisible() {
  if (document.visibilityState === 'visible') reload()
}
document.addEventListener('visibilitychange', reloadIfVisible)
window.addEventListener('focus', reloadIfVisible)
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', reloadIfVisible)
  window.removeEventListener('focus', reloadIfVisible)
})

const combined = reactive({ data: null, error: null, loading: true, reload })

watchEffect(() => {
  combined.data = loadedOnce.value ? {} : null
  combined.error = error.value
  combined.loading = loading.value
})

const summaryCards = computed(() => {
  const s = summary.value || {}
  return [
    { label: 'Total spent', value: inr(s.total_amount), sub: periodLabel.value },
    { label: 'Expenses', value: s.expense_count ?? 0, sub: periodLabel.value },
    { label: 'Average expense', value: inr(s.average_expense), sub: periodLabel.value },
  ]
})

const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function monthLabel(monthKey) {
  const month = Number(String(monthKey).split('-')[1])
  return monthNames[month - 1] || monthKey
}

const CHART_COLORS = ['#007BE0', '#46B37E', '#E79913', '#CC2929', '#7C7C7C', '#0289F7', '#8B5CF6', '#14B8A6']

const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')
if (typeof MutationObserver !== 'undefined') {
  const themeObserver = new MutationObserver(() => {
    isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
  })
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
}

const tickColor = computed(() => (isDark.value ? '#9CA3AF' : '#6B7280'))
const gridColor = computed(() =>
  isDark.value ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
)

const compactInr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value || 0)

const trendHasData = computed(() => {
  return trend.value.some((row) => Number(row.total_amount) > 0)
})

const trendChartLabels = computed(() => trend.value.map((row) => monthLabel(row.month)))

const trendChartData = computed(() => ({
  labels: trendChartLabels.value,
  datasets: [
    {
      label: 'Total spend',
      data: trend.value.map((row) => Number(row.total_amount) || 0),
      borderColor: '#007BE0',
      backgroundColor: '#007BE0',
      tension: 0.3,
      fill: true,
      borderWidth: 2,
      pointRadius: 3,
    },
  ],
}))

const trendChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${compactInr(ctx.parsed.y ?? ctx.parsed)}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: tickColor.value, maxRotation: 0 } },
    y: {
      beginAtZero: true,
      grid: { color: gridColor.value },
      ticks: { color: tickColor.value, callback: (value) => compactInr(value) },
    },
  },
}))

const breakdownChartData = computed(() => ({
  labels: breakdown.value.map((row) => row.category_name),
  datasets: [
    {
      label: 'Spent',
      data: breakdown.value.map((row) => Number(row.total_amount) || 0),
      backgroundColor: breakdown.value.map(
        (_, i) => CHART_COLORS[i % CHART_COLORS.length],
      ),
      borderRadius: 6,
      maxBarThickness: 44,
    },
  ],
}))

const breakdownChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${compactInr(ctx.parsed.y ?? ctx.parsed)}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: tickColor.value, maxRotation: 30 } },
    y: {
      beginAtZero: true,
      grid: { color: gridColor.value },
      ticks: { color: tickColor.value, callback: (value) => compactInr(value) },
    },
  },
}))

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value || 0)
</script>

