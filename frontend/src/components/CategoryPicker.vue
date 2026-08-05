<template>
  <Combobox
    v-model="model"
    :options="options"
    :loading="resource.loading"
    :placeholder="placeholder"
    :disabled="disabled"
    trigger="input"
  />
</template>

<script setup>
import { computed } from 'vue'
import { Combobox, createResource } from 'frappe-ui'

const props = defineProps({
  modelValue: { type: String, default: null },
  placeholder: { type: String, default: 'Select category' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const model = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const resource = createResource({
  url: 'expense_manager.api.categories.list_categories',
  method: 'GET',
  auto: true,
  params: { active_only: 1 },
})

const options = computed(() => {
  const cats = resource.data || []
  return cats.map((category) => ({
    label: category.category_name,
    value: category.name,
    icon: category.icon || undefined,
  }))
})
</script>
