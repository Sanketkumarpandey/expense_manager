<template>
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
        </div>
      </div>

      <div class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
        <p class="text-sm text-ink-gray-5">Budget usage this month</p>
        <div class="mt-4">
          <div class="h-2 w-full overflow-hidden rounded-full bg-surface-gray-2">
            <div
              class="h-full rounded-full bg-surface-blue-3 transition-all"
              :style="{ width: usagePct + '%' }"
            />
          </div>
          <div class="mt-2 flex items-center justify-between text-xs text-ink-gray-5">
            <span>
              {{ inr(monthlyExpense) }} spent of
              {{ inr(monthlySpent + remainingBudget) }} budget
            </span>
            <span>{{ usagePct }}%</span>
          </div>
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
        <div v-if="recent.length" class="divide-y divide-outline-gray-1">
          <div
            v-for="expense in recent"
            :key="expense.name"
            class="flex items-center gap-3 px-5 py-3"
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
          No expenses yet. Add one from the Expenses page.
        </p>
      </div>
    </div>
  </ResourceState>
</template>

<script setup>
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import OverspendBanner from '@/components/OverspendBanner.vue'

const resource = createResource({
  url: 'expense_manager.api.reports.get_dashboard_summary',
  method: 'GET',
  auto: true,
})

const dismissed = ref([])

const data = computed(() => resource.data || {})
const totalExpense = computed(() => data.value.total_expense ?? 0)
const monthlyExpense = computed(() => data.value.monthly_expense ?? 0)
const remainingBudget = computed(() => data.value.remaining_budget ?? 0)
const monthlySpent = computed(() => monthlyExpense.value)
const recent = computed(() => data.value.recent_expenses || [])
const overspent = computed(() =>
  (data.value.overspent || []).filter((row) => !dismissed.value.includes(row.category)),
)
const usagePct = computed(() => {
  const budget = monthlySpent.value + remainingBudget.value
  if (!budget) return 0
  return Math.min(999, Math.round((monthlySpent.value / budget) * 100))
})

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

const cards = computed(() => [
  {
    label: 'Total expense',
    value: inr(totalExpense.value),
    icon: 'lucide-wallet',
    iconBg: 'bg-surface-gray-2 text-ink-gray-7',
  },
  {
    label: 'Monthly expense',
    value: inr(monthlyExpense.value),
    icon: 'lucide-calendar-days',
    iconBg: 'bg-surface-gray-2 text-ink-gray-7',
  },
  {
    label: 'Remaining budget',
    value: inr(remainingBudget.value),
    icon: 'lucide-banknote',
    iconBg: 'bg-surface-green-1 text-ink-green-3',
    valueClass:
      remainingBudget.value < 0 ? 'text-ink-red-5' : 'text-ink-gray-9',
  },
  {
    label: 'Active budgets',
    value: data.value.active_budgets ?? 0,
    icon: 'lucide-target',
    iconBg: 'bg-surface-gray-2 text-ink-gray-7',
  },
  {
    label: 'Over budget',
    value: data.value.over_budget ?? 0,
    icon: 'lucide-alert-triangle',
    iconBg:
      (data.value.over_budget ?? 0) > 0
        ? 'bg-surface-red-1 text-ink-red-5'
        : 'bg-surface-gray-2 text-ink-gray-7',
    valueClass: (data.value.over_budget ?? 0) > 0 ? 'text-ink-red-5' : 'text-ink-gray-9',
  },
  {
    label: 'Dependents',
    value: data.value.dependents ?? 0,
    icon: 'lucide-users',
    iconBg: 'bg-surface-gray-2 text-ink-gray-7',
  },
])
</script>
