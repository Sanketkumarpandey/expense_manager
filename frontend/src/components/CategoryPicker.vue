<template>
  <div class="flex items-center gap-2">
    <div class="min-w-0 flex-1">
      <Combobox
        v-model="model"
        :options="options"
        :loading="categoriesResource.loading"
        :placeholder="placeholder"
        :disabled="disabled"
        trigger="input"
        variant="outline"
      />
    </div>
    <Button
      v-if="model && !disabled"
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
import { categoriesResource } from '@/data/catalog'

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

const options = computed(() => {
  const cats = categoriesResource.data || []
  return cats.map((category) => ({
    label: category.category_name,
    value: category.name,
    icon: category.icon || undefined,
  }))
})

onMounted(() => {
  categoriesResource.reload()
})
</script>
