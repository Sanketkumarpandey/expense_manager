<template>
  <div class="rounded-lg border border-dashed border-outline-gray-2 bg-surface-white p-10 text-center">
    <span
      class="mx-auto grid size-10 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-5"
    >
      <component :is="icon" class="size-5" />
    </span>
    <p class="mt-3 text-sm font-medium text-ink-gray-7">{{ title }}</p>
    <p v-if="description" class="mx-auto mt-1 max-w-sm text-sm text-ink-gray-5">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-4 flex justify-center">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: [Object, String, Function], default: null },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
