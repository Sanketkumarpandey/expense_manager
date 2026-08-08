<template>
  <div class="space-y-6">
    <OverspendBanner
      v-if="overspend"
      :overspend="overspend"
      @dismiss="overspend = null"
    />

    <div class="flex items-center justify-between">
      <p class="text-sm text-ink-gray-5">
        {{ expenses.length }} {{ expenses.length === 1 ? 'expense' : 'expenses' }}
      </p>
      <div class="flex items-center gap-2">
        <Button variant="solid" size="sm" @click="openCreate">
          <template #prefix>
            <span class="lucide-plus size-4 text-white" />
          </template>
          New expense
        </Button>
      </div>
    </div>

    <ResourceState :resource="list" label="your expenses">
      <template #skeleton>
        <div class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-16 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <EmptyState
        v-if="expenses.length === 0"
        :icon="Receipt"
        title="No expenses found"
        description="Add a new expense to get started."
      >
        <template #action>
          <Button variant="solid" size="sm" @click="openCreate">Add expense</Button>
        </template>
      </EmptyState>

      <div v-else class="overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white">
        <div class="hidden items-center gap-4 border-b border-outline-gray-1 px-4 py-2 text-xs font-medium text-ink-gray-5 md:flex">
          <span class="w-24 shrink-0">Date</span>
          <span class="flex-1">Description</span>
          <span class="w-32 shrink-0 text-center">Category</span>
          <span class="w-28 shrink-0 text-right">Amount</span>
          <span class="w-20 shrink-0" />
        </div>

        <div class="divide-y divide-outline-gray-1">
          <div
            v-for="expense in expenses"
            :key="expense.name"
            class="flex items-center gap-4 px-4 py-3"
          >
            <span class="hidden w-24 shrink-0 text-sm text-ink-gray-5 md:block">
              {{ formatDate(expense.expense_date) }}
            </span>

            <div class="flex min-w-0 flex-1 items-center gap-3">
              <span
                class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-lg"
              >
                {{ expense.category_icon || '🏷️' }}
              </span>
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-ink-gray-9">
                  {{ expense.description || expense.category_name || 'Expense' }}
                </p>
                <p class="truncate text-xs text-ink-gray-5">
                  <span class="md:hidden">{{ formatDate(expense.expense_date) }}</span>
                  <span v-if="expense.dependent_name" class="text-ink-gray-4 md:hidden">
                    · {{ expense.dependent_name }}
                  </span>
                  <span v-if="expense.payment_method" class="text-ink-gray-4">
                    · {{ expense.payment_method }}
                  </span>
                </p>
              </div>
            </div>

            <div class="hidden w-32 shrink-0 flex-col items-center gap-1 md:flex">
              <span
                class="max-w-full truncate rounded-full bg-surface-gray-2 px-2.5 py-0.5 text-center text-xs text-ink-gray-7"
              >
                {{ expense.category_name || expense.category }}
              </span>
              <span
                v-if="expense.dependent_name"
                class="max-w-full truncate text-xs text-ink-gray-4"
              >
                {{ expense.dependent_name }}
              </span>
            </div>

            <p class="w-28 shrink-0 text-right text-sm font-semibold text-ink-gray-9">
              {{ inr(expense.amount) }}
            </p>

            <div class="flex w-20 shrink-0 items-center justify-end pl-1">
              <RowActionsMenu :items="rowActions(expense)" />
            </div>
          </div>
        </div>
      </div>
    </ResourceState>

    <ExpenseFormDialog v-model:open="formOpen" :expense="editingExpense" @saved="onSaved" />

    <ConfirmDialog
      v-model:open="confirmOpen"
      title="Delete expense?"
      :message="deleteMessage"
      confirm-label="Delete"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Button,
  call,
  createResource,
  toast,
} from 'frappe-ui'
import Pencil from '~icons/lucide/pencil'
import Trash2 from '~icons/lucide/trash-2'
import ResourceState from '@/components/ResourceState.vue'
import ExpenseFormDialog from '@/components/ExpenseFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import OverspendBanner from '@/components/OverspendBanner.vue'
import RowActionsMenu from '@/components/RowActionsMenu.vue'
import EmptyState from '@/components/EmptyState.vue'
import Receipt from '~icons/lucide/receipt'

const overspend = ref(null)

const list = createResource({
  url: 'expense_manager.api.expenses.list_expenses',
  method: 'GET',
  auto: true,
})

const expenses = computed(() => list.data || [])

const formOpen = ref(false)
const editingExpense = ref(null)

function openCreate() {
  editingExpense.value = null
  formOpen.value = true
}

function openEdit(expense) {
  editingExpense.value = expense
  formOpen.value = true
}

function onSaved(result) {
  list.reload()
  if (result && result.overspend) {
    overspend.value = result.overspend
  } else if (result && result.warning) {
    toast.warning(result.warning)
  }
  if (editingExpense.value) {
    toast.success('Expense updated.')
  } else {
    toast.success(
      `Added ${inr(result.amount)} under ${result.category_name || 'a category'}.`,
    )
  }
}

const confirmOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)
const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  const label =
    deleteTarget.value.description ||
    deleteTarget.value.category_name ||
    'this expense'
  return `Are you sure you want to delete "${label}" (${inr(deleteTarget.value.amount)})? This cannot be undone.`
})

function requestDelete(expense) {
  deleteTarget.value = expense
  confirmOpen.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    const result = await call('expense_manager.api.expenses.delete_expense', {
      expense: deleteTarget.value.name,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success('Expense deleted.')
      list.reload()
    }
    confirmOpen.value = false
  } catch (e) {
    toast.error(e.message || 'Could not delete the expense.')
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

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function rowActions(expense) {
  return [
    {
      label: 'Edit',
      icon: Pencil,
      onClick: () => openEdit(expense),
    },
    {
      label: 'Delete',
      icon: Trash2,
      theme: 'red',
      onClick: () => requestDelete(expense),
    },
  ]
}
</script>
