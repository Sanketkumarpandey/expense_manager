<template>
  <div class="space-y-6">
    <section class="rounded-lg border border-outline-gray-1 bg-surface-white p-5">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div class="min-w-0 flex-1">
          <Input
            v-model="quickText"
            placeholder="Quick add — e.g. &quot;Lunch 250&quot;"
            :disabled="quickAdding"
            @keydown.enter="quickAdd"
          />
        </div>
        <Button variant="solid" :loading="quickAdding" @click="quickAdd">
          <template #prefix>
            <span class="lucide-wand-2 size-4 text-white" />
          </template>
          <span class="hidden sm:inline">Add</span>
        </Button>
      </div>
      <p
        v-if="quickMessage"
        class="mt-3 text-sm font-medium"
        :class="{
          'text-ink-red-4': quickMessage.type === 'error',
          'text-ink-green-3': quickMessage.type === 'success',
          'text-ink-gray-8': quickMessage.type === 'warning',
        }"
      >
        {{ quickMessage.text }}
      </p>
    </section>

    <section class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 bg-surface-white p-4">
      <div class="flex flex-wrap items-end gap-4 sm:gap-6">
        <div class="w-48">
          <FormLabel label="Dependent" />
          <DependentPicker v-model="filters.dependent" placeholder="All dependents" />
        </div>
        <div class="w-48">
          <FormLabel label="Category" />
          <CategoryPicker v-model="filters.category" placeholder="All categories" />
        </div>
        <div class="w-40">
          <FormLabel label="From" />
          <DatePicker v-model="filters.date_from" placeholder="Start date" />
        </div>
        <div class="w-40">
          <FormLabel label="To" />
          <DatePicker v-model="filters.date_to" placeholder="End date" />
        </div>
        <Button
          v-if="hasFilters"
          variant="subtle"
          size="sm"
          class="mb-0.5"
          @click="clearFilters"
        >
          <template #prefix>
            <span class="lucide-x size-4" />
          </template>
          Clear filters
        </Button>
      </div>

      <div class="flex items-center justify-between">
        <p class="text-sm text-ink-gray-5">
          {{ expenses.length }} {{ expenses.length === 1 ? 'expense' : 'expenses' }}
        </p>
        <Button variant="solid" size="sm" @click="openCreate">
          <template #prefix>
            <span class="lucide-plus size-4 text-white" />
          </template>
          New expense
        </Button>
      </div>
    </section>

    <ResourceState :resource="list" label="your expenses">
      <template #skeleton>
        <div class="space-y-2">
          <div v-for="i in 4" :key="i" class="h-16 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <div v-if="expenses.length === 0" class="rounded-lg border border-dashed border-outline-gray-2 bg-surface-white p-10 text-center">
        <p class="text-sm text-ink-gray-5">
          No expenses found. Try clearing the filters or add a new expense.
        </p>
      </div>

      <div v-else class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-white">
        <div
          v-for="expense in expenses"
          :key="expense.name"
          class="flex items-center gap-3 px-4 py-3"
        >
          <span
            class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-lg"
          >
            {{ expense.category_icon || '🏷️' }}
          </span>

          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-ink-gray-9">
              {{ expense.description || expense.category_name || 'Expense' }}
            </p>
            <p class="truncate text-xs text-ink-gray-5">
              {{ formatDate(expense.expense_date) }}
              <span v-if="expense.dependent_name" class="text-ink-gray-4">
                · {{ expense.dependent_name }}
              </span>
              <span v-if="expense.payment_method" class="text-ink-gray-4">
                · {{ expense.payment_method }}
              </span>
            </p>
          </div>

          <div class="flex shrink-0 items-center gap-1.5">
            <p class="mr-2 text-sm font-semibold text-ink-gray-9">
              {{ inr(expense.amount) }}
            </p>
            <Button variant="ghost" size="sm" title="Edit" @click="openEdit(expense)">
              <template #prefix>
                <span class="lucide-pencil size-4" />
              </template>
            </Button>
            <Button variant="ghost" size="sm" title="Delete" @click="requestDelete(expense)">
              <template #prefix>
                <span class="lucide-trash-2 size-4" />
              </template>
            </Button>
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
import { computed, reactive, ref } from 'vue'
import {
  Button,
  DatePicker,
  FormLabel,
  Input,
  createResource,
  call,
} from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import CategoryPicker from '@/components/CategoryPicker.vue'
import DependentPicker from '@/components/DependentPicker.vue'
import ExpenseFormDialog from '@/components/ExpenseFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const quickText = ref('')
const quickAdding = ref(false)
const quickMessage = ref(null)

const filters = reactive({
  dependent: null,
  category: null,
  date_from: null,
  date_to: null,
})

function buildFilters() {
  const params = {}
  if (filters.dependent) params.dependent = filters.dependent
  if (filters.category) params.category = filters.category
  if (filters.date_from) params.date_from = filters.date_from
  if (filters.date_to) params.date_to = filters.date_to
  return params
}

const list = createResource({
  url: 'expense_manager.api.expenses.list_expenses',
  method: 'GET',
  auto: true,
  makeParams: buildFilters,
})

const hasFilters = computed(() => Object.keys(buildFilters()).length > 0)
const expenses = computed(() => list.data || [])

function clearFilters() {
  filters.dependent = null
  filters.category = null
  filters.date_from = null
  filters.date_to = null
  list.fetch()
}

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
  if (result && result.warning) {
    showQuickMessage(result.warning, 'warning')
  } else if (editingExpense.value) {
    showQuickMessage('Expense updated.', 'success')
  } else {
    showQuickMessage(
      `Added ${inr(result.amount)} under ${result.category_name || 'a category'}.`,
      'success',
    )
  }
}

async function quickAdd() {
  const text = quickText.value.trim()
  if (!text || quickAdding.value) return

  quickAdding.value = true
  quickMessage.value = null
  try {
    const result = await call('expense_manager.api.expenses.create_expense_from_text', {
      text,
    })
    if (result && result.success === false) {
      showQuickMessage(result.message, 'error')
      return
    }
    quickText.value = ''
    list.reload()
    let message = `Added ${inr(result.amount)} under ${result.category_name || 'a category'}.`
    if (result.warning) message += ' ' + result.warning
    showQuickMessage(message, 'success')
  } catch (e) {
    showQuickMessage(e.message || 'Could not add the expense.', 'error')
  } finally {
    quickAdding.value = false
  }
}

function showQuickMessage(text, type) {
  quickMessage.value = { text, type }
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
      showQuickMessage(result.message, 'error')
    } else {
      showQuickMessage('Expense deleted.', 'success')
      list.reload()
    }
    confirmOpen.value = false
  } catch (e) {
    showQuickMessage(e.message || 'Could not delete the expense.', 'error')
    confirmOpen.value = false
  } finally {
    deleting.value = false
  }
}

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
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
</script>
