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
              class="h-full rounded-full transition-all"
              :class="usagePct > 100 ? 'bg-surface-red-2' : 'bg-surface-blue-2'"
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
    </div>
  </ResourceState>
</template>

<script setup>
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'

const resource = createResource({
  url: 'expense_manager.api.reports.get_dashboard_summary',
  method: 'GET',
  auto: true,
})

const data = computed(() => resource.data || {})
const totalExpense = computed(() => data.value.total_expense ?? 0)
const monthlyExpense = computed(() => data.value.monthly_expense ?? 0)
const remainingBudget = computed(() => data.value.remaining_budget ?? 0)
const monthlySpent = computed(() => monthlyExpense.value)
const usagePct = computed(() => {
  const budget = monthlySpent.value + remainingBudget.value
  if (!budget) return 0
  return Math.min(999, Math.round((monthlySpent.value / budget) * 100))
})

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)

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
      remainingBudget.value < 0 ? 'text-ink-red-4' : 'text-ink-gray-9',
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
        ? 'bg-surface-red-1 text-ink-red-4'
        : 'bg-surface-gray-2 text-ink-gray-7',
    valueClass: (data.value.over_budget ?? 0) > 0 ? 'text-ink-red-4' : 'text-ink-gray-9',
  },
  {
    label: 'Dependents',
    value: data.value.dependents ?? 0,
    icon: 'lucide-users',
    iconBg: 'bg-surface-gray-2 text-ink-gray-7',
  },
])
</script>
