<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-outline-gray-1 bg-surface-white p-4">
      <div class="flex flex-wrap items-end gap-4 sm:gap-6">
        <div class="w-48">
          <FormLabel label="Dependent" />
          <DependentPicker v-model="filters.dependent" placeholder="All dependents" />
        </div>
        <div class="w-44">
          <FormLabel label="From" />
          <DatePicker v-model="filters.date_from" />
        </div>
        <div class="w-44">
          <FormLabel label="To" />
          <DatePicker v-model="filters.date_to" />
        </div>
        <Button
          v-if="hasCustomFilters"
          variant="subtle"
          size="sm"
          class="mb-0.5"
          @click="clearFilters"
        >
          <template #prefix>
            <X class="size-4" />
          </template>
          Reset
        </Button>
      </div>
      <p class="mt-3 text-xs text-ink-gray-5">
        The spending trend covers the last 6 months; budget and pocket-money
        reports show the current state.
      </p>
    </section>

    <ResourceState :resource="combined" label="your reports">
      <template #skeleton>
        <div class="space-y-6">
          <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-lg bg-surface-gray-2" />
          </div>
          <div v-for="i in 3" :key="`c${i}`" class="h-48 animate-pulse rounded-lg bg-surface-gray-2" />
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
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
                <BarChart3 class="size-4" />
              </span>
              <div>
                <p class="text-sm font-medium text-ink-gray-9">Monthly spending trend</p>
                <p class="text-xs text-ink-gray-5">Last 6 months breakdown</p>
              </div>
            </div>
          </div>

          <p v-if="trend.length === 0" class="mt-6 text-center text-sm text-ink-gray-5">
            No expenses in the last 6 months.
          </p>
          <div v-else class="mt-6 flex items-end gap-3 sm:gap-6 border-b border-gray-200 pb-2">
            <div
              v-for="row in trend"
              :key="row.month"
              class="flex min-w-0 flex-1 flex-col items-center gap-1.5"
            >
              <p class="text-[11px] font-medium text-ink-gray-7">{{ inr(row.total_amount) }}</p>
              <div class="flex h-36 w-full items-end justify-center rounded-md bg-gray-50/50 p-1">
                <div
                  class="w-full max-w-14 rounded-t-md transition-all shadow-sm"
                  :class="row.total_amount > 0 ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-200'"
                  :style="{ height: trendHeight(row) + '%' }"
                  :title="`${monthLabel(row.month)}: ${inr(row.total_amount)}`"
                />
              </div>
              <p class="text-xs font-medium text-ink-gray-7">{{ monthLabel(row.month) }}</p>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <div class="flex items-center gap-2">
            <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
              <PieChart class="size-4" />
            </span>
            <div>
              <p class="text-sm font-medium text-ink-gray-9">Category breakdown</p>
              <p class="text-xs text-ink-gray-5">{{ periodLabel }}</p>
            </div>
          </div>

          <p v-if="breakdown.length === 0" class="mt-6 text-center text-sm text-ink-gray-5">
            No expenses in this period.
          </p>
          <div v-else class="mt-4 space-y-3">
            <div
              v-for="row in breakdown"
              :key="row.category"
              class="flex items-center gap-3"
            >
              <span class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-lg">
                {{ row.category_icon || '🏷️' }}
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline justify-between gap-2">
                  <p class="truncate text-sm font-medium text-ink-gray-9">{{ row.category_name }}</p>
                  <p class="shrink-0 text-sm font-medium text-ink-gray-9">{{ inr(row.total_amount) }}</p>
                </div>
                <div class="mt-1 flex items-center gap-2">
                  <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-200 border border-gray-300">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="row.percentage_of_total > 0 ? 'bg-blue-600' : 'bg-gray-300'"
                      :style="{ width: Math.min(row.percentage_of_total, 100) + '%' }"
                    />
                  </div>
                  <p class="shrink-0 text-xs text-ink-gray-6 font-medium">
                    {{ row.expense_count }} {{ row.expense_count === 1 ? 'expense' : 'expenses' }}
                    · {{ row.percentage_of_total }}%
                  </p>
                </div>
              </div>
            </div>
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
                    class="rounded bg-surface-red-1 px-1.5 py-0.5 text-xs font-medium text-ink-red-4"
                  >
                    Over budget
                  </span>
                </div>
                <div class="mt-1 flex items-center gap-2">
                  <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-200 border border-gray-300">
                    <div
                      class="h-full rounded-full transition-all"
                      :class="row.is_overspent ? 'bg-red-600' : 'bg-blue-600'"
                      :style="{ width: Math.min(row.percentage, 100) + '%' }"
                    />
                  </div>
                  <p class="shrink-0 text-xs" :class="row.is_overspent ? 'text-ink-red-4' : 'text-ink-gray-5'">
                    {{ inr(row.spent_amount) }} of {{ inr(row.allocated_amount) }}
                    · {{ inr(row.remaining_amount) }} left
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
          <div class="flex items-center gap-2">
            <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-6">
              <Coins class="size-4" />
            </span>
            <div>
              <p class="text-sm font-medium text-ink-gray-9">Pocket money summary</p>
              <p class="text-xs text-ink-gray-5">Active allocations, current state</p>
            </div>
          </div>

          <p v-if="pocketMoney.length === 0" class="mt-6 text-center text-sm text-ink-gray-5">
            No active pocket money allocations.
          </p>
          <div v-else class="mt-4">
            <div class="grid grid-cols-[minmax(0,1.5fr)_repeat(5,minmax(0,1fr))] gap-3 border-b border-outline-gray-1 pb-2 text-xs text-ink-gray-5">
              <p>Dependent</p>
              <p class="text-right">Allocated</p>
              <p class="text-right">Spent</p>
              <p class="text-right">Carry fwd</p>
              <p class="text-right">Remaining</p>
              <p class="text-right">Savings</p>
            </div>
            <div
              v-for="row in pocketMoney"
              :key="row.dependent"
              class="grid grid-cols-[minmax(0,1.5fr)_repeat(5,minmax(0,1fr))] items-center gap-3 border-b border-outline-gray-1 py-2.5 text-sm last:border-0"
            >
              <p class="truncate font-medium text-ink-gray-9">{{ row.dependent_name }}</p>
              <p class="text-right text-ink-gray-9">{{ inr(row.allocated_amount) }}</p>
              <p class="text-right text-ink-gray-6">{{ inr(row.spent_amount) }}</p>
              <p class="text-right text-ink-gray-6">{{ inr(row.carry_forward) }}</p>
              <p class="text-right font-medium" :class="row.remaining_amount < 0 ? 'text-ink-red-4' : 'text-ink-gray-9'">
                {{ inr(row.remaining_amount) }}
              </p>
              <p class="text-right text-ink-green-3">{{ inr(row.total_savings) }}</p>
            </div>
          </div>
        </div>
      </div>
    </ResourceState>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch, watchEffect } from 'vue'
import { Button, DatePicker, FormLabel, request } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import DependentPicker from '@/components/DependentPicker.vue'

const now = new Date()
const pad = (n) => String(n).padStart(2, '0')
const toLocalDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

const defaultFrom = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`
const defaultTo = toLocalDate(now)

const filters = reactive({
  dependent: null,
  date_from: defaultFrom,
  date_to: defaultTo,
})

const hasCustomFilters = computed(
  () =>
    Boolean(filters.dependent) ||
    filters.date_from !== defaultFrom ||
    filters.date_to !== defaultTo,
)

function clearFilters() {
  filters.dependent = null
  filters.date_from = defaultFrom
  filters.date_to = defaultTo
}

const periodLabel = computed(() => `${filters.date_from || '…'} – ${filters.date_to || '…'}`)

const loading = ref(true)
const error = ref(null)
const loadedOnce = ref(false)

const summary = ref(null)
const trend = ref([])
const breakdown = ref([])
const budgetSummary = ref([])
const pocketMoney = ref([])

async function getReport(method, params) {
  const res = await request({ url: `/api/method/${method}`, params })
  if (res.message && res.message.success === false) return null
  return res.message
}

async function reload() {
  loading.value = true
  error.value = null

  const dependentParams = {}
  if (filters.dependent) dependentParams.dependent = filters.dependent

  const periodParams = {}
  if (filters.date_from) periodParams.date_from = filters.date_from
  if (filters.date_to) periodParams.date_to = filters.date_to

  const [s, t, b, bs, pm] = await Promise.allSettled([
    getReport('expense_manager.api.reports.get_expense_summary', {
      ...dependentParams,
      ...periodParams,
    }),
    getReport('expense_manager.api.reports.get_spending_trend', {
      ...dependentParams,
      months: 6,
    }),
    getReport('expense_manager.api.reports.get_category_breakdown', {
      ...dependentParams,
      ...periodParams,
    }),
    getReport('expense_manager.api.reports.get_budget_summary', {}),
    getReport('expense_manager.api.reports.get_pocket_money_summary', {}),
  ])

  summary.value = s.status === 'fulfilled' ? s.value : null
  trend.value = t.status === 'fulfilled' && Array.isArray(t.value) ? t.value : []
  breakdown.value = b.status === 'fulfilled' && Array.isArray(b.value) ? b.value : []
  budgetSummary.value = bs.status === 'fulfilled' && Array.isArray(bs.value) ? bs.value : []
  pocketMoney.value = pm.status === 'fulfilled' && Array.isArray(pm.value) ? pm.value : []

  const failures = [s, t, b, bs, pm].filter((r) => r.status === 'rejected')
  if (failures.length) {
    error.value = 'Some reports could not be loaded.'
  } else {
    loadedOnce.value = true
  }
  loading.value = false
}

watch(
  () => [filters.dependent, filters.date_from, filters.date_to],
  reload,
  { immediate: true },
)

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

const trendMax = computed(() =>
  Math.max(0, ...trend.value.map((row) => Number(row.total_amount) || 0)),
)

function trendHeight(row) {
  const value = Number(row.total_amount) || 0
  if (!trendMax.value || !value) return 0
  return Math.max(6, Math.round((value / trendMax.value) * 100))
}

const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function monthLabel(monthKey) {
  const month = Number(String(monthKey).split('-')[1])
  return monthNames[month - 1] || monthKey
}

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)

const compactInr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number(value) || 0)
</script>
