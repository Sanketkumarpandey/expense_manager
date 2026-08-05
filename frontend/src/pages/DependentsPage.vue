<template>
  <div class="space-y-6">
    <section class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 bg-surface-white p-4 sm:flex-row sm:items-center sm:justify-between">
      <div class="flex items-center gap-1 rounded-lg bg-surface-gray-2 p-1">
        <button
          v-for="mode in viewModes"
          :key="mode.value"
          type="button"
          class="rounded-md px-3 py-1.5 text-sm transition-colors"
          :class="view === mode.value
            ? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm'
            : 'text-ink-gray-6 hover:text-ink-gray-8'"
          @click="setView(mode.value)"
        >
          {{ mode.label }}
        </button>
      </div>
      <div class="flex items-center gap-3">
        <p v-if="message" class="text-sm font-medium" :class="message.type === 'error' ? 'text-ink-red-4' : 'text-ink-green-3'">
          {{ message.text }}
        </p>
        <Button variant="solid" size="sm" @click="openCreate">
          <template #prefix>
            <Plus class="size-4 text-white" />
          </template>
          New dependent
        </Button>
      </div>
    </section>

    <ResourceState :resource="list" label="your dependents">
      <template #skeleton>
        <div class="space-y-4">
          <div v-for="i in 3" :key="i" class="h-40 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <div v-if="dependents.length === 0" class="rounded-lg border border-dashed border-outline-gray-2 bg-surface-white p-10 text-center">
        <p class="text-sm text-ink-gray-5">
          {{ view === 'active' ? 'No active dependents found. Add your first dependent.' : 'No dependents found.' }}
        </p>
      </div>

      <div v-else class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div
          v-for="dep in dependents"
          :key="dep.name"
          class="flex flex-col justify-between rounded-lg border border-outline-gray-1 bg-surface-white p-5 space-y-4"
        >
          <div>
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-3">
                <span class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-xl">
                  👤
                </span>
                <div>
                  <div class="flex items-center gap-2">
                    <p class="text-base font-semibold text-ink-gray-9">{{ dep.dependent_name }}</p>
                    <span class="rounded bg-surface-blue-1 px-2 py-0.5 text-xs font-medium text-ink-blue-5">
                      {{ dep.relationship }}
                    </span>
                    <span v-if="!dep.is_active" class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-5">
                      Archived
                    </span>
                  </div>
                  <p class="text-xs text-ink-gray-5">
                    Added {{ formatDate(dep.creation) }}
                    <span v-if="dep.telegram_username"> · @{{ dep.telegram_username }}</span>
                  </p>
                </div>
              </div>

              <div class="flex items-center gap-1">
                <Button variant="ghost" size="sm" title="Edit" @click="openEdit(dep)">
                  <template #prefix>
                    <Pencil class="size-4" />
                  </template>
                </Button>
                <Button
                  v-if="dep.is_active"
                  variant="ghost"
                  size="sm"
                  title="Archive"
                  :loading="archiving === dep.name"
                  @click="triggerArchive(dep)"
                >
                  <template #prefix>
                    <Archive class="size-4" />
                  </template>
                </Button>
                <Button
                  v-else
                  variant="ghost"
                  size="sm"
                  title="Restore"
                  :loading="restoring === dep.name"
                  @click="triggerRestore(dep)"
                >
                  <template #prefix>
                    <RotateCcw class="size-4" />
                  </template>
                </Button>
                <Button variant="ghost" size="sm" title="Delete" @click="requestDelete(dep)">
                  <template #prefix>
                    <Trash2 class="size-4" />
                  </template>
                </Button>
              </div>
            </div>

            <!-- Stats & Allowance section -->
            <div class="mt-4 grid grid-cols-2 gap-3 rounded-md bg-surface-gray-1 p-3">
              <div>
                <p class="text-xs text-ink-gray-5">Monthly Allowance</p>
                <p class="mt-0.5 text-sm font-semibold text-ink-gray-9">
                  {{ inr(dep.default_monthly_allowance) }}
                </p>
              </div>
              <div>
                <p class="text-xs text-ink-gray-5">Total Savings</p>
                <p class="mt-0.5 text-sm font-semibold text-ink-green-3">
                  {{ inr(dep.total_savings) }}
                </p>
              </div>
            </div>

            <!-- Pocket Money Balance Card -->
            <div class="mt-3 rounded-md border border-outline-gray-1 bg-surface-white p-3">
              <div class="flex items-center justify-between">
                <p class="text-xs font-medium text-ink-gray-7">Pocket Money Allocation</p>
                <div class="flex items-center gap-2">
                  <Button
                    v-if="dep.is_active"
                    variant="subtle"
                    size="sm"
                    title="Manual Rollover"
                    :loading="rollingOver === dep.name"
                    @click="triggerRollover(dep)"
                  >
                    <template #prefix>
                      <RefreshCw class="size-3.5" />
                    </template>
                    Rollover
                  </Button>
                  <Button
                    v-if="dep.is_active"
                    variant="outline"
                    size="sm"
                    @click="openPocketMoney(dep)"
                  >
                    <template #prefix>
                      <Coins class="size-3.5" />
                    </template>
                    {{ balanceOf(dep.name) ? 'Update' : 'Allocate' }}
                  </Button>
                </div>
              </div>

              <div v-if="balanceOf(dep.name)" class="mt-2 text-xs space-y-1">
                <div class="flex justify-between text-ink-gray-7">
                  <span>Period: {{ balanceOf(dep.name).allocation_period || 'Monthly' }}</span>
                  <span class="font-medium" :class="balanceOf(dep.name).remaining_amount < 0 ? 'text-ink-red-4' : 'text-ink-gray-9'">
                    Remaining: {{ inr(balanceOf(dep.name).remaining_amount) }}
                  </span>
                </div>
                <div class="h-2.5 overflow-hidden rounded-full bg-gray-200 border border-gray-300">
                  <div
                    class="h-full rounded-full transition-all"
                    :class="balanceOf(dep.name).remaining_amount < 0 ? 'bg-red-600' : 'bg-blue-600'"
                    :style="{ width: `${Math.min(balancePct(dep.name), 100)}%` }"
                  />
                </div>
                <p class="text-[11px] text-ink-gray-5">
                  Allocated: {{ inr(balanceOf(dep.name).allocated_amount) }} · Spent: {{ inr(balanceOf(dep.name).spent_amount) }}
                </p>
              </div>
              <div v-else class="mt-2 text-xs text-ink-gray-5">
                No active pocket money allocation set.
              </div>
            </div>

            <AllowedCategoriesSection :dependent="dep" />
          </div>

          <div class="text-xs text-ink-gray-5 pt-2 border-t border-outline-gray-1 flex items-center justify-between">
            <span>Carry forward: {{ dep.allow_carry_forward ? 'Enabled' : 'Disabled' }}</span>
            <span>Created {{ formatDate(dep.creation) }}</span>
          </div>
        </div>
      </div>
    </ResourceState>

    <DependentFormDialog v-model:open="formOpen" :dependent="editingDep" @saved="onSaved" />

    <PocketMoneyFormDialog
      v-model:open="pocketOpen"
      :dependent="targetDep"
      :allocation="targetAllocation"
      @saved="onPocketMoneySaved"
    />

    <ConfirmDialog
      v-model:open="confirmOpen"
      title="Delete dependent?"
      :message="deleteMessage"
      confirm-label="Delete"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, call, createResource, request } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import DependentFormDialog from '@/components/DependentFormDialog.vue'
import PocketMoneyFormDialog from '@/components/PocketMoneyFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AllowedCategoriesSection from '@/components/AllowedCategoriesSection.vue'

const viewModes = [
  { value: 'active', label: 'Active' },
  { value: 'all', label: 'All' },
]

const view = ref('active')

const list = createResource({
  url: 'expense_manager.api.dependents.list_dependents',
  method: 'GET',
  auto: true,
  makeParams: () => ({ active_only: view.value === 'active' ? 1 : 0 }),
})

const dependents = computed(() => list.data || [])

function setView(value) {
  view.value = value
  list.fetch()
}

const balances = reactive({})

async function fetchBalances() {
  const deps = list.data || []
  for (const dep of deps) {
    try {
      const res = await request({
        url: '/api/method/expense_manager.api.pocket_money.get_balance',
        params: { dependent: dep.name },
      })
      if (res.message && res.message.success !== false) {
        balances[dep.name] = res.message
      } else {
        balances[dep.name] = null
      }
    } catch (e) {
      balances[dep.name] = null
    }
  }
}

watch(
  () => list.data,
  () => {
    if (list.data) fetchBalances()
  },
  { immediate: true },
)

function balanceOf(depName) {
  return balances[depName] || null
}

function balancePct(depName) {
  const b = balanceOf(depName)
  if (!b || !b.total_available_amount) return 0
  const pct = (b.spent_amount / b.total_available_amount) * 100
  return Math.round(pct)
}

const message = ref(null)

function showMessage(text, type = 'success') {
  message.value = { text, type }
}

const formOpen = ref(false)
const editingDep = ref(null)

function openCreate() {
  editingDep.value = null
  formOpen.value = true
}

function openEdit(dep) {
  editingDep.value = dep
  formOpen.value = true
}

function onSaved() {
  list.reload()
  showMessage(editingDep.value ? 'Dependent updated.' : 'Dependent created.')
}

const pocketOpen = ref(false)
const targetDep = ref(null)
const targetAllocation = ref(null)

async function openPocketMoney(dep) {
  targetDep.value = dep
  const bal = balanceOf(dep.name)
  targetAllocation.value = bal ? { name: bal.allocation } : null
  pocketOpen.value = true
}

function onPocketMoneySaved() {
  fetchBalances()
  showMessage('Pocket money allocation updated.')
}

const rollingOver = ref(null)

async function triggerRollover(dep) {
  rollingOver.value = dep.name
  try {
    const result = await call('expense_manager.api.pocket_money.rollover_allocation', {
      dependent: dep.name,
    })
    if (result && result.success === false) {
      showMessage(result.message, 'error')
    } else {
      showMessage(`Pocket money rolled over for ${dep.dependent_name}.`)
      list.reload()
      fetchBalances()
    }
  } catch (e) {
    showMessage(e.message || 'Could not perform rollover.', 'error')
  } finally {
    rollingOver.value = null
  }
}

async function archiveDep(dep) {
  await call('expense_manager.api.dependents.archive_dependent', { dependent: dep.name })
  showMessage(`Dependent "${dep.dependent_name}" archived.`)
  list.reload()
}

async function restoreDep(dep) {
  await call('expense_manager.api.dependents.restore_dependent', { dependent: dep.name })
  showMessage(`Dependent "${dep.dependent_name}" restored.`)
  list.reload()
}

const confirmOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)
const deleteMessage = computed(() =>
  deleteTarget.value
    ? `Delete "${deleteTarget.value.dependent_name}"? This cannot be undone.`
    : '',
)

function requestDelete(dep) {
  deleteTarget.value = dep
  confirmOpen.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    const result = await call('expense_manager.api.dependents.delete_dependent', {
      dependent: deleteTarget.value.name,
    })
    if (result && result.success === false) {
      showMessage(result.message, 'error')
    } else {
      showMessage(`Dependent "${deleteTarget.value.dependent_name}" deleted.`)
      list.reload()
    }
    confirmOpen.value = false
  } catch (e) {
    showMessage(e.message || 'Could not delete dependent.', 'error')
    confirmOpen.value = false
  } finally {
    deleting.value = false
  }
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value || 0)
</script>
