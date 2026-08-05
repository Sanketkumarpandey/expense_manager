<template>
  <div class="flex items-center gap-2">
    <div class="min-w-0 flex-1">
      <Combobox
        v-model="model"
        :options="options"
        :loading="resource.loading"
        :placeholder="placeholder"
        trigger="input"
      />
    </div>
    <Button
      v-if="model"
      variant="subtle"
      size="sm"
      title="Clear selection"
      @click="model = null"
    >
      <template #prefix>
        <span class="lucide-x size-4" />
      </template>
    </Button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Combobox, createResource } from 'frappe-ui'

const props = defineProps({
  modelValue: { type: String, default: null },
  placeholder: { type: String, default: 'Select dependent (optional)' },
})

const emit = defineEmits(['update:modelValue'])

const model = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const resource = createResource({
  url: 'expense_manager.api.dependents.list_dependents',
  method: 'GET',
  auto: true,
  params: { active_only: 1 },
})

const options = computed(() => {
  const deps = resource.data || []
  return deps.map((dependent) => ({
    label: dependent.dependent_name,
    value: dependent.name,
  }))
})
</script>
