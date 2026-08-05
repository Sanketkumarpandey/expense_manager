<template>
  <div class="flex h-full flex-col items-center justify-center py-24 text-center">
    <span class="grid size-14 place-items-center rounded-xl bg-surface-gray-2 text-ink-gray-5">
      <span class="size-6" :class="icon" />
    </span>
    <h2 class="mt-4 text-lg font-semibold text-ink-gray-9">{{ pageTitle }}</h2>
    <p class="mt-1 max-w-sm text-sm text-ink-gray-6">
      This section is coming in a later phase.
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const pageTitle = computed(() => route.meta.title || 'Coming soon')

const icon = computed(() => {
  const icons = {
    expenses: 'lucide-receipt',
    categories: 'lucide-tag',
    budgets: 'lucide-target',
    dependents: 'lucide-users',
    reports: 'lucide-chart-pie',
    telegram: 'lucide-send',
  }
  return icons[route.name] || 'lucide-hourglass'
})
</script>
