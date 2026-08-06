<template>
  <div>
    <div v-if="error" class="rounded-lg border border-outline-red-2 bg-surface-red-1 p-6">
      <div class="flex items-center gap-2 text-ink-red-5">
        <span class="lucide-alert-circle size-4" />
        <p class="text-sm font-medium">Couldn't load {{ label }}</p>
      </div>
      <p v-if="errorMessage" class="mt-1 pl-6 text-sm text-ink-red-4">{{ errorMessage }}</p>
      <Button
        class="mt-4"
        variant="subtle"
        size="sm"
        :loading="retrying"
        @click="retry"
      >
        Retry
      </Button>
    </div>

    <div v-else-if="showSkeleton">
      <slot name="skeleton">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <div
            v-for="i in 6"
            :key="i"
            class="h-28 animate-pulse rounded-lg bg-surface-gray-2"
          />
        </div>
      </slot>
    </div>

    <slot
      v-else
      :data="data"
      :resource="resource"
      :error="error"
      :loading="loading"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button } from 'frappe-ui'

const props = defineProps({
  resource: { type: Object, required: true },
  label: { type: String, default: 'this page' },
})

const retrying = ref(false)

const data = computed(() => props.resource.data)
const error = computed(() => props.resource.error)
const loading = computed(() => props.resource.loading)

const showSkeleton = computed(
  () => loading.value && !data.value,
)

async function retry() {
  retrying.value = true
  try {
    await props.resource.reload()
  } finally {
    retrying.value = false
  }
}
</script>
