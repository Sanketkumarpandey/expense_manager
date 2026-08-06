<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <p class="text-sm text-ink-gray-5">
        {{ categories.length }} {{ categories.length === 1 ? 'category' : 'categories' }}
      </p>
      <div class="flex items-center gap-2">
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
        <Button variant="solid" size="sm" @click="openCreate">
          <template #prefix>
            <Plus class="size-4 text-white" />
          </template>
          New category
        </Button>
      </div>
    </div>

    <ResourceState :resource="list" label="your categories">
      <template #skeleton>
        <div class="space-y-2">
          <div v-for="i in 5" :key="i" class="h-14 animate-pulse rounded-lg bg-surface-gray-2" />
        </div>
      </template>

      <div v-if="categories.length === 0" class="rounded-lg border border-dashed border-outline-gray-2 bg-surface-white p-10 text-center">
        <p class="text-sm text-ink-gray-5">
          {{ view === 'active' ? 'No active categories yet. Create your first one.' : 'No archived categories.' }}
        </p>
      </div>

      <div v-else class="divide-y divide-outline-gray-1 rounded-lg border border-outline-gray-1 bg-surface-white">
        <div v-for="category in categories" :key="category.name" class="flex items-center gap-3 px-4 py-3">
          <span class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-xl">
            {{ category.icon || '🏷️' }}
          </span>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="truncate text-sm font-medium text-ink-gray-9">{{ category.category_name }}</p>
              <span v-if="!category.is_active" class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-5">
                Archived
              </span>
            </div>
            <p class="text-xs text-ink-gray-5">Created {{ formatDate(category.creation) }}</p>
          </div>

          <div class="flex shrink-0 items-center gap-1.5">
            <Button variant="ghost" size="sm" title="Edit" @click="openEdit(category)">
              <template #prefix>
                <Pencil class="size-4" />
              </template>
            </Button>
            <Button
              v-if="category.is_active"
              variant="ghost"
              size="sm"
              title="Archive"
              :loading="busy === 'archive-' + category.name"
              @click="archive(category)"
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
              :loading="busy === 'restore-' + category.name"
              @click="restore(category)"
            >
              <template #prefix>
                <RotateCcw class="size-4" />
              </template>
            </Button>
            <Button variant="ghost" size="sm" title="Delete" class="text-ink-gray-5 hover:text-ink-red-5" @click="requestDelete(category)">
              <template #prefix>
                <Trash2 class="size-4" />
              </template>
            </Button>
          </div>
        </div>
      </div>
    </ResourceState>

    <CategoryFormDialog v-model:open="formOpen" :category="editingCategory" @saved="onSaved" />

    <ConfirmDialog
      v-model:open="confirmOpen"
      title="Delete category?"
      :message="deleteMessage"
      confirm-label="Delete"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, createResource, call, toast } from 'frappe-ui'
import Plus from '~icons/lucide/plus'
import Pencil from '~icons/lucide/pencil'
import Archive from '~icons/lucide/archive'
import RotateCcw from '~icons/lucide/rotate-ccw'
import Trash2 from '~icons/lucide/trash-2'
import ResourceState from '@/components/ResourceState.vue'
import CategoryFormDialog from '@/components/CategoryFormDialog.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const viewModes = [
  { value: 'active', label: 'Active' },
  { value: 'all', label: 'All' },
]

const view = ref('active')

const list = createResource({
  url: 'expense_manager.api.categories.list_categories',
  method: 'GET',
  auto: true,
  makeParams: () => ({ active_only: view.value === 'active' ? 1 : 0 }),
})

const categories = computed(() => list.data || [])

function setView(value) {
  view.value = value
  list.fetch()
}

const busy = ref(null)

const formOpen = ref(false)
const editingCategory = ref(null)

function openCreate() {
  editingCategory.value = null
  formOpen.value = true
}

function openEdit(category) {
  editingCategory.value = category
  formOpen.value = true
}

function onSaved(result) {
  list.reload()
  if (editingCategory.value) {
    toast.success('Category updated.')
  } else {
    toast.success(`Category "${result.category_name}" created.`)
  }
}

async function archive(category) {
  busy.value = 'archive-' + category.name
  try {
    const result = await call('expense_manager.api.categories.archive_category', {
      category: category.name,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success(`Category "${category.category_name}" archived.`)
      list.reload()
    }
  } catch (e) {
    toast.error(e.message || 'Could not archive the category.')
  } finally {
    busy.value = null
  }
}

async function restore(category) {
  busy.value = 'restore-' + category.name
  try {
    const result = await call('expense_manager.api.categories.restore_category', {
      category: category.name,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success(`Category "${category.category_name}" restored.`)
      list.reload()
    }
  } catch (e) {
    toast.error(e.message || 'Could not restore the category.')
  } finally {
    busy.value = null
  }
}

const confirmOpen = ref(false)
const deleting = ref(false)
const deleteTarget = ref(null)
const deleteMessage = computed(() =>
  deleteTarget.value
    ? `Delete "${deleteTarget.value.category_name}"? This cannot be undone.`
    : '',
)

function requestDelete(category) {
  deleteTarget.value = category
  confirmOpen.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    const result = await call('expense_manager.api.categories.delete_category', {
      category: deleteTarget.value.name,
    })
    if (result && result.success === false) {
      toast.error(result.message)
    } else {
      toast.success(`Category "${deleteTarget.value.category_name}" deleted.`)
      list.reload()
    }
    confirmOpen.value = false
  } catch (e) {
    toast.error(e.message || 'Could not delete the category.')
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
</script>
