<template>
  <div class="space-y-6">
    <ResourceState :resource="resource" label="your dashboard">
    <template #skeleton>
      <div class="space-y-6">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <div
            v-for="i in 6"
            :key="i"
            class="h-28 animate-pulse rounded-lg bg-surface-gray-2"
          />
        </div>
        <div class="h-40 animate-pulse rounded-lg bg-surface-gray-2" />
      </div>
    </template>

    <div class="space-y-6">
      <div v-if="overspent.length" class="space-y-3">
        <OverspendBanner
          v-for="row in overspent"
          :key="row.category"
          :overspend="row"
          class="max-w-3xl"
          @dismiss="dismissed.push(row.category)"
        />
      </div>

      <div class="flex justify-end">
        <QuickExpenseHoverCard @added="onExpenseAdded" />
      </div>

      <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <div
          v-for="card in cards"
          :key="card.label"
          class="rounded-lg border border-outline-gray-1 bg-surface-white p-5"
        >
          <div class="flex items-center justify-between">
            <p class="text-sm text-ink-gray-5">{{ card.label }}</p>
            <span
              class="grid size-8 place-items-center rounded-lg"
              :class="card.iconBg"
            >
              <span class="size-4" :class="card.icon" />
            </span>
          </div>
          <p
            class="mt-3 text-2xl font-semibold tracking-tight"
            :class="card.valueClass || 'text-ink-gray-9'"
          >
            {{ card.value }}
          </p>
          <div class="mt-4">
            <div class="h-1.5 w-full overflow-hidden rounded-full bg-surface-gray-2">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="card.barClass"
                :style="{ width: card.barPct + '%' }"
              />
            </div>
            <div class="mt-1.5 flex items-center justify-between gap-2 text-xs text-ink-gray-5">
              <span class="truncate">{{ card.footer }}</span>
              <span class="shrink-0 font-medium" :class="card.footerClass">
                {{ card.barLabel }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <h2 class="text-sm font-medium text-ink-gray-9">Spending trend</h2>
          <p class="text-xs text-ink-gray-5">Monthly spend vs. monthly budget</p>
          <div v-if="trendHasData" class="mt-4">
            <ChartBox type="bar" :data="trendData" :options="trendOptions" height="260px" />
          </div>
          <p v-else class="py-10 text-center text-sm text-ink-gray-5">
            No spending in the last 6 months.
          </p>
        </div>
        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <h2 class="text-sm font-medium text-ink-gray-9">Spending by category</h2>
          <p class="text-xs text-ink-gray-5">This month's category share</p>
          <div v-if="breakdownHasData" class="mt-4">
            <ChartBox type="doughnut" :data="breakdownData" :options="breakdownOptions" height="260px" />
          </div>
          <p v-else class="py-10 text-center text-sm text-ink-gray-5">
            No expenses this month.
          </p>
        </div>
      </div>

      <div class="rounded-lg border border-outline-gray-1 bg-surface-white">
        <div class="flex items-center justify-between border-b border-outline-gray-1 px-5 py-4">
          <div>
            <h2 class="text-sm font-medium text-ink-gray-9">Recent expenses</h2>
            <p class="text-xs text-ink-gray-5">Latest activity across all categories</p>
          </div>
          <router-link
            :to="{ name: 'expenses' }"
            class="text-sm font-medium text-ink-blue-3 hover:text-ink-blue-4"
          >
            View all
          </router-link>
        </div>
        <div v-if="recent.length" class="max-h-72 overflow-y-auto divide-y divide-outline-gray-1">
          <div
            v-for="expense in recent"
            :key="expense.name"
            class="flex items-center gap-3 px-5 py-3 hover:bg-surface-gray-1/50 transition-colors"
          >
            <span
              class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-7"
            >
              <span class="size-4">{{ expense.category_icon }}</span>
            </span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink-gray-9">
                {{ expense.description || expense.category_name || 'Expense' }}
              </p>
              <p class="text-xs text-ink-gray-5">
                {{ expense.category_name || expense.category }}
                <span v-if="expense.dependent_name"> · {{ expense.dependent_name }}</span>
                · {{ formatDate(expense.expense_date) }}
              </p>
            </div>
            <p class="text-sm font-medium text-ink-gray-9">{{ inr(expense.amount) }}</p>
          </div>
        </div>
        <p v-else class="px-5 py-8 text-center text-sm text-ink-gray-5">
          No expenses yet. Use Quick Add Expense to log your first expense.
        </p>
      </div>
    </div>
  </ResourceState>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import OverspendBanner from '@/components/OverspendBanner.vue'
import ChartBox from '@/components/ChartBox.vue'
import QuickExpenseHoverCard from '@/components/QuickExpenseHoverCard.vue'

const resource = createResource({
  url: 'expense_manager.api.reports.get_dashboard_summary',
  method: 'GET',
  auto: true,
})

const now = new Date()
const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
const todayIso = now.toISOString().slice(0, 10)
const firstOfMonthIso = firstOfMonth.toISOString().slice(0, 10)

const trendResource = createResource({
  url: 'expense_manager.api.reports.get_spending_trend',
  method: 'GET',
  auto: true,
  makeParams: () => ({ months: 6 }),
})

const breakdownResource = createResource({
  url: 'expense_manager.api.reports.get_category_breakdown',
  method: 'GET',
  auto: true,
  makeParams: () => ({
    date_from: firstOfMonthIso,
    date_to: todayIso,
  }),
})

const dismissed = ref([])

function onExpenseAdded() {
  resource.reload()
  trendResource.reload()
  breakdownResource.reload()
}

const data = computed(() => resource.data || {})
const totalExpense = computed(() => data.value.total_expense ?? 0)
const monthlyExpense = computed(() => data.value.monthly_expense ?? 0)
const remainingBudget = computed(() => data.value.remaining_budget ?? 0)
const totalBudget = computed(() => monthlyExpense.value + remainingBudget.value)
const recent = computed(() => data.value.recent_expenses || [])
const overspent = computed(() =>
  (data.value.overspent || []).filter((row) => !dismissed.value.includes(row.category)),
)

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value || 0)

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
  })
}

const cards = computed(() => {
  const budget = monthlyExpense.value + remainingBudget.value
  const monthlyPct = budget ? Math.round((monthlyExpense.value / budget) * 100) : 0
  const remaining = Math.max(0, remainingBudget.value)
  const remainingPct = budget ? Math.round((remaining / budget) * 100) : 0
  const totalPct = budget ? Math.round((totalExpense.value / budget) * 100) : 0
  const active = data.value.active_budgets ?? 0
  const over = data.value.over_budget ?? 0
  const within = Math.max(0, active - over)
  const activePct = active ? Math.round((within / active) * 100) : 0
  const overPct = active ? Math.round((over / active) * 100) : 0
  const dependents = data.value.dependents ?? 0

  const monthlyBar = usageBar(monthlyPct)
  const totalBar = usageBar(totalPct)

  return [
    {
      label: 'Monthly expense',
      value: inr(monthlyExpense.value),
      icon: 'lucide-calendar-days',
      iconBg: 'bg-surface-blue-1 text-ink-blue-3',
      barPct: Math.min(100, monthlyPct),
      barClass: monthlyBar.color,
      footer: `spent of ${inr(budget)}`,
      barLabel: `${monthlyPct}%`,
      footerClass: monthlyBar.label,
    },
    {
      label: 'Remaining budget',
      value: inr(remainingBudget.value),
      icon: 'lucide-banknote',
      iconBg: 'bg-surface-green-1 text-ink-green-3',
      valueClass: remainingBudget.value < 0 ? 'text-ink-red-5' : 'text-ink-gray-9',
      barPct: Math.min(100, remainingPct),
      barClass: remainingBudget.value < 0 ? 'bg-surface-red-6' : 'bg-surface-green-3',
      footer: `remaining of ${inr(budget)}`,
      barLabel: `${remainingPct}%`,
      footerClass: remainingBudget.value < 0 ? 'text-ink-red-5' : 'text-ink-gray-5',
    },
    {
      label: 'Total expense',
      value: inr(totalExpense.value),
      icon: 'lucide-wallet',
      iconBg: 'bg-surface-gray-2 text-ink-gray-7',
      barPct: Math.min(100, totalPct),
      barClass: totalBar.color,
      footer: `spent vs ${inr(budget)} budget`,
      barLabel: `${totalPct}%`,
      footerClass: totalBar.label,
    },
    {
      label: 'Active budgets',
      value: active,
      icon: 'lucide-target',
      iconBg: 'bg-surface-gray-2 text-ink-gray-7',
      barPct: Math.min(100, activePct),
      barClass: 'bg-surface-green-3',
      footer: `${within} of ${active} within budget`,
      barLabel: `${activePct}%`,
      footerClass: 'text-ink-gray-5',
    },
    {
      label: 'Over budget',
      value: over,
      icon: 'lucide-alert-triangle',
      iconBg: over > 0 ? 'bg-surface-red-1 text-ink-red-5' : 'bg-surface-gray-2 text-ink-gray-7',
      valueClass: over > 0 ? 'text-ink-red-5' : 'text-ink-gray-9',
      barPct: Math.min(100, overPct),
      barClass: over > 0 ? 'bg-surface-red-6' : 'bg-surface-gray-2',
      footer: `${over} of ${active} budgets over`,
      barLabel: `${overPct}%`,
      footerClass: over > 0 ? 'text-ink-red-5' : 'text-ink-gray-5',
    },
    {
      label: 'Dependents',
      value: dependents,
      icon: 'lucide-users',
      iconBg: 'bg-surface-gray-2 text-ink-gray-7',
      barPct: dependents ? 100 : 0,
      barClass: 'bg-surface-blue-3',
      footer: 'active on the household plan',
      barLabel: dependents ? 'Active' : 'None',
      footerClass: 'text-ink-gray-5',
    },
  ]
})

function usageBar(pct) {
  if (pct >= 100) return { color: 'bg-surface-red-6', label: 'text-ink-red-5' }
  if (pct >= 90) return { color: 'bg-surface-amber-3', label: 'text-ink-amber-3' }
  return { color: 'bg-surface-blue-3', label: 'text-ink-gray-5' }
}

const CHART_COLORS = ['#007BE0', '#46B37E', '#E79913', '#CC2929', '#7C7C7C', '#0289F7']

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

const trendOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: { color: tickColor.value, boxWidth: 10, boxHeight: 10, padding: 16 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${compactInr(ctx.parsed.y ?? ctx.parsed)}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: tickColor.value, maxRotation: 0 } },
    y: {
      grid: { color: gridColor.value },
      ticks: { color: tickColor.value, callback: (value) => compactInr(value) },
    },
  },
}))

const breakdownOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  cutout: '58%',
  plugins: {
    legend: {
      position: 'bottom',
      labels: { color: tickColor.value, boxWidth: 10, boxHeight: 10, padding: 16 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const total = ctx.dataset.data.reduce((sum, value) => sum + value, 0)
          const pct = total ? Math.round((ctx.parsed / total) * 100) : 0
          return `${ctx.label}: ${compactInr(ctx.parsed)} (${pct}%)`
        },
      },
    },
  },
}))
const compactInr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value || 0)

const trendHasData = computed(() =>
  (trendResource.data || []).some((row) => row.total_amount > 0),
)
const breakdownHasData = computed(() =>
  (breakdownResource.data || []).some((row) => row.total_amount > 0),
)

const trendData = computed(() => {
  const rows = trendResource.data || []
  const budget = totalBudget.value
  return {
    labels: rows.map((row) => row.month),
    datasets: [
      {
        label: 'Spend',
        type: 'bar',
        data: rows.map((row) => row.total_amount),
        backgroundColor: '#0289F7',
        borderRadius: 6,
        maxBarThickness: 28,
      },
      {
        label: 'Monthly budget',
        type: 'line',
        data: rows.map(() => budget),
        borderColor: '#46B37E',
        borderDash: [6, 6],
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 2,
        fill: false,
      },
    ],
  }
})

const breakdownData = computed(() => {
  const rows = breakdownResource.data || []
  return {
    labels: rows.map((row) => row.category_name),
    datasets: [
      {
        data: rows.map((row) => row.total_amount),
        backgroundColor: rows.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
        borderWidth: 0,
        hoverOffset: 4,
      },
    ],
  }
})

</script>
