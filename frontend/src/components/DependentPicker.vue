<template>
  <div class="flex items-center gap-2">
    <div class="min-w-0 flex-1">
      <Combobox
        v-model="model"
        :options="options"
        :loading="dependentsResource.loading"
        :placeholder="placeholder"
        trigger="input"
        variant="outline"
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
import { computed, onMounted } from 'vue'
import { Button, Combobox } from 'frappe-ui'
import { dependentsResource } from '@/data/catalog'

const props = defineProps({
  modelValue: { type: String, default: null },
  placeholder: { type: String, default: 'Select dependent (optional)' },
})

const emit = defineEmits(['update:modelValue'])

const model = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const options = computed(() => {
  const deps = dependentsResource.data || []
  return deps.map((dependent) => ({
    label: dependent.dependent_name,
    value: dependent.name,
  }))
})

onMounted(() => {
  dependentsResource.reload()
})
</script>
