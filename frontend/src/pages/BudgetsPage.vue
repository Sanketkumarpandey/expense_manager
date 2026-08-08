<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-outline-gray-1 bg-surface-white p-4">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1 rounded-lg bg-surface-tea p-1">
            <button
              v-for="mode in viewModes"
              :key="String(mode.value)"
              type="button"
              class="rounded-md px-3 py-1.5 text-sm transition-colors"
              :class="activeOnly === mode.value
                ? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm'
                : 'text-ink-gray-6 hover:text-ink-gray-8'"
              @click="setView(mode.value)"
            >
              {{ mode.label }}
            </button>
          </div>
          <p class="text-sm text-ink-gray-5">
            {{ mergedBudgets.length }} {{ mergedBudgets.length === 1 ? 'budget' : 'budgets' }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="solid" size="sm" @click="openCreate">
            <template #prefix>
              <Plus class="size-4 text-white" />
            </template>
            New budget
          </Button>
        </div>
      </div>
    </section>

    <ResourceState :resource="combined" label="your budgets">
      <template #skeleton>
        <div class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-20 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <EmptyState
        v-if="mergedBudgets.length === 0"
        :icon="Target"
        :title="activeOnly ? 'No active budgets' : 'No budgets found'"
        :description="activeOnly ? 'Create a budget to start tracking spending by category.' : 'Archived budgets will show up here.'"
      >
        <template v-if="activeOnly" #action>
          <Button variant="solid" size="sm" @click="openCreate">New budget</Button>
        </template>
      </EmptyState>

      <div v-else class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-white">
        <div v-for="budget in mergedBudgets" :key="budget.name" class="flex items-start gap-3 px-4 py-3">
          <span class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-xl">
            {{ categoryIcon(budget.category) }}
          </span>

          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <p class="truncate text-sm font-medium text-ink-gray-9">{{ categoryName(budget.category) }}</p>
              <span
                class="rounded px-1.5 py-0.5 text-xs font-medium"
                :class="budget.dependent ? 'bg-surface-gray-2 text-ink-gray-6' : 'bg-surface-blue-1 text-ink-blue-5'"
              >
                {{ budget.dependent ? dependentName(budget.dependent) : 'Household' }}
              </span>
              <span v-if="!budget.is_active" class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-5">
                Archived
              </span>
              <span
                v-if="isFlagged(budget)"
                class="rounded px-1.5 py-0.5 text-xs font-medium text-ink-red-5"
                :class="isOverBudget(budget) ? 'bg-surface-red-1' : 'bg-surface-red-2'"
              >
                {{ isOverBudget(budget) ? 'Over budget' : `${usagePct(budget)}% used` }}
              </span>
            </div>

            <p class="mt-0.5 text-xs text-ink-gray-5">
              {{ budget.period }} budget · {{ budget.start_date }} – {{ budget.end_date }}
            </p>

            <div v-if="usageOf(budget)" class="mt-2 max-w-md">
              <div class="flex items-center gap-2">
                <div class="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-gray-2">
                  <div
                    class="h-full rounded-full transition-all"
                    :class="isOverBudget(budget) ? 'bg-surface-red-6' : 'bg-surface-blue-3'"
                    :style="{ width: `${Math.min(usagePct(budget), 100)}%` }"
                  />
                </div>
                <span class="text-xs font-medium text-ink-gray-6">{{ usagePct(budget) }}%</span>
              </div>
              <p class="mt-1 text-xs" :class="isFlagged(budget) ? 'text-ink-red-5' : 'text-ink-gray-5'">
                {{ inr(usageOf(budget).spent_amount) }} of {{ inr(usageOf(budget).allocated_amount) }} spent
                · {{ inr(usageOf(budget).remaining_amount) }} left
                <span v-if="isOverBudget(budget)">· over by {{ inr(Math.abs(usageOf(budget).remaining_amount)) }}</span>
              </p>
            </div>
          </div>

          <RowActionsMenu :items="rowActions(budget)" />
        </div>
      </div>
    </ResourceState>

    <BudgetFormDialog v-model:open="formOpen" :budget="editingBudget" @saved="onSaved" />

    <ConfirmDialog
      v-model:open="confirmOpen"
      title="Delete budget?"
      :message="deleteMessage"
      confirm-label="Delete"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch, watchEffect } from 'vue'
import { Button, call, createResource, request, toast } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import Pencil from '~icons/lucide/pencil'
import Archive from '~icons/lucide/archive'
import RotateCcw from '~icons/lucide/rotate-ccw'
import Trash2 from '~icons/lucide/trash-2'
import ResourceState from '@/components/ResourceState.vue'
import BudgetFormDialog from '@/components/BudgetFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import RowActionsMenu from '@/components/RowActionsMenu.vue'
import EmptyState from '@/components/EmptyState.vue'
import Target from '~icons/lucide/target'

const viewModes = [
  { value: true, label: 'Active' },
  { value: false, label: 'All' },
]

const activeOnly = ref(true)

function setView(value) {
  activeOnly.value = value
  reloadAll()
}

function budgetParams() {
  return { active_only: activeOnly.value ? 1 : 0 }
}

const guardianBudgets = createResource({
  url: 'expense_manager.api.budgets.list_budgets',
  method: 'GET',
  auto: true,
  makeParams: budgetParams,
})

const dependentsResource = createResource({
  url: 'expense_manager.api.dependents.list_dependents',
  method: 'GET',
  auto: true,
  params: { active_only: 0 },
})

const categoriesResource = createResource({
  url: 'expense_manager.api.categories.list_categories',
  method: 'GET',
  auto: true,
  params: { active_only: 0 },
})

const depBudgets = reactive({})
const depLoading = ref(false)

async function fetchDependentBudgets() {
  const deps = dependentsResource.data || []
  depLoading.value = true
  try {
    const entries = await Promise.all(
      deps.map(async (dependent) => {
        const res = await request({
          url: '/api/method/expense_manager.api.budgets.list_budgets',
          params: { ...budgetParams(), dependent: dependent.name },
        })
        return [dependent.name, res.message]
      }),
    )
    for (const [name, rows] of entries) {
      depBudgets[name] = rows
    }
  } catch (e) {
    console.error('Failed to load dependent budgets', e)
  } finally {
    depLoading.value = false
  }
}

watch(
  () => dependentsResource.data,
  () => {
    if (dependentsResource.data) fetchDependentBudgets()
  },
)

const mergedBudgets = computed(() => {
  const rows = [...(guardianBudgets.data || [])]
  for (const depRows of Object.values(depBudgets)) {
    rows.push(...(depRows || []))
  }
  return rows.sort((a, b) => categoryName(a.category).localeCompare(categoryName(b.category)))
})

const combined = reactive({ data: [], error: null, loading: true, reload: reloadAll })

watchEffect(() => {
  combined.data = mergedBudgets.value
  combined.loading =
    guardianBudgets.loading ||
    dependentsResource.loading ||
    categoriesResource.loading ||
    depLoading.value
  combined.error = guardianBudgets.error || dependentsResource.error
})

function reloadAll() {
  guardianBudgets.fetch()
  if (dependentsResource.data) fetchDependentBudgets()
}

const categoryLabelMap = computed(() => {
  const map = {}
  for (const category of categoriesResource.data || []) {
    map[category.name] = category
  }
  return map
})

function categoryName(name) {
  const category = categoryLabelMap.value[name]
  return category ? category.category_name : name
}

function categoryIcon(name) {
  const category = categoryLabelMap.value[name]
  return category ? category.icon || '🏷️' : '🏷️'
}

const dependentLabelMap = computed(() => {
  const map = {}
  for (const dependent of dependentsResource.data || []) {
    map[dependent.name] = dependent.dependent_name
  }
  return map
})

function dependentName(name) {
  return dependentLabelMap.value[name] || name
}

const usageMap = reactive({})

function usageOf(budget) {
  return usageMap[budget.name] || null
}

function usagePct(budget) {
  const usage = usageOf(budget)
  if (!usage) return 0
  return Math.round(usage.pct_used)
}

function isFlagged(budget) {
  const usage = usageOf(budget)
  if (!usage) return false
  return usage.is_overspent || usage.pct_used >= usage.alert_threshold_pct
}

function isOverBudget(budget) {
  const usage = usageOf(budget)
  return Boolean(usage && usage.is_overspent)
}

watch(
  mergedBudgets,
  async () => {
    for (const name of Object.keys(usageMap)) delete usageMap[name]
    for (const budget of mergedBudgets.value) {
      if (!budget.is_active) continue
      const params = { category: budget.category }
      if (budget.dependent) params.dependent = budget.dependent
      try {
        const res = await request({
          url: '/api/method/expense_manager.api.budgets.get_budget_usage',
          params,
        })
        const usage = res.message
        usageMap[budget.name] = usage && usage.success !== false ? usage : null
      } catch (e) {
        console.error('Failed to load budget usage', budget.name, e)
        usageMap[budget.name] = null
      }
    }
  },
  { immediate: true },
)

const busy = ref(null)

const formOpen = ref(false)
const editingBudget = ref(null)

function openCreate() {
  editingBudget.value = null
  formOpen.value = true
}

function openEdit(budget) {
  editingBudget.value = budget
  formOpen.value = true
}

function onSaved(result) {
  reloadAll()
  const label = categoryName(result.category || editingBudget.value?.category)
  toast.success(
    editingBudget.value
      ? `Budget for "${label}" updated.`
      : `Budget for "${label}" created.`,
  )
}

async function archive(budget) {
  busy.value = 'archive-' + budget.name
  try {
    const result = await call('expense_manager.api.budgets.archive_budget', {
      budget: budget.name,
      dependent: budget.dependent || null,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success(`Budget for "${categoryName(budget.category)}" archived.`)
      reloadAll()
    }
  } catch (e) {
    toast.error(e.message || 'Could not archive the budget.')
  } finally {
    busy.value = null
  }
}

async function restore(budget) {
  busy.value = 'restore-' + budget.name
  try {
    const result = await call('expense_manager.api.budgets.restore_budget', {
      budget: budget.name,
      dependent: budget.dependent || null,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success(`Budget for "${categoryName(budget.category)}" restored.`)
      reloadAll()
    }
  } catch (e) {
    toast.error(e.message || 'Could not restore the budget.')
  } finally {
    busy.value = null
  }
}

const confirmOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)
const deleteMessage = computed(() =>
  deleteTarget.value
    ? `Delete the ${budgetScopeLabel(deleteTarget.value)} budget for "${categoryName(deleteTarget.value.category)}"? This cannot be undone.`
    : '',
)

function budgetScopeLabel(budget) {
  if (budget.dependent) return `"${dependentName(budget.dependent)}"`
  return 'household'
}

function requestDelete(budget) {
  deleteTarget.value = budget
  confirmOpen.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    const result = await call('expense_manager.api.budgets.delete_budget', {
      budget: deleteTarget.value.name,
      dependent: deleteTarget.value.dependent || null,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success('Budget deleted.')
      reloadAll()
    }
    confirmOpen.value = false
  } catch (e) {
    toast.error(e.message || 'Could not delete the budget.')
    confirmOpen.value = false
  } finally {
    deleting.value = false
  }
}

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value || 0)

function rowActions(budget) {
  const actions = [
    {
      label: 'Edit',
      icon: Pencil,
      onClick: () => openEdit(budget),
    },
  ]
  if (budget.is_active) {
    actions.push({
      label: 'Archive',
      icon: Archive,
      disabled: busy.value === 'archive-' + budget.name,
      onClick: () => archive(budget),
    })
  } else {
    actions.push({
      label: 'Restore',
      icon: RotateCcw,
      disabled: busy.value === 'restore-' + budget.name,
      onClick: () => restore(budget),
    })
  }
  actions.push({
    label: 'Delete',
    icon: Trash2,
    theme: 'red',
    onClick: () => requestDelete(budget),
  })
  return actions
}
</script>
