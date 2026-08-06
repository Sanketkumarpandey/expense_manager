<template>
  <div
    class="flex items-start gap-2.5 rounded-lg border border-outline-red-2 bg-surface-red-1 p-4"
    role="status"
  >
    <span class="mt-0.5 shrink-0 text-ink-red-5">
      <AlertTriangle class="size-5" />
    </span>
    <div class="min-w-0 flex-1">
      <p class="text-sm font-medium text-ink-red-5">
        Over budget in {{ overspend.category_name }}
      </p>
      <p class="mt-0.5 text-sm text-ink-red-4">
        {{ inr(overspend.spent_amount) }} spent of {{ inr(overspend.allocated_amount) }} allocated
        <span v-if="Number(overspend.remaining_amount) < 0">
          ({{ inr(Math.abs(Number(overspend.remaining_amount))) }} over)
        </span>
      </p>
    </div>
    <button
      class="shrink-0 rounded p-1 text-ink-red-4 transition hover:bg-surface-red-2 hover:text-ink-red-5"
      aria-label="Dismiss"
      @click="$emit('dismiss')"
    >
      <X class="size-4" />
    </button>
  </div>
</template>

<script setup>
import AlertTriangle from '~icons/lucide/alert-triangle'
import X from '~icons/lucide/x'

defineProps({
  overspend: { type: Object, required: true },
})

defineEmits(['dismiss'])

const inr = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)
</script>
