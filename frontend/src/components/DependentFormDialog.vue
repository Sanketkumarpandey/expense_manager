<template>
  <Dialog :open="open" :options="{ title }" size="md" @close="closeDialog">
    <template #body-content>
      <div class="space-y-4">
        <div>
          <FormLabel label="Dependent name" required />
          <Input
            v-model="form.dependent_name"
            placeholder="e.g. Alex Junior"
            @keydown.enter="save"
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Relationship" required />
            <Select v-model="form.relationship" :options="RELATIONSHIPS" />
          </div>
          <div>
            <FormLabel label="Monthly allowance (₹)" required />
            <Input
              v-model="form.default_monthly_allowance"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              @keydown.enter="save"
            />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Telegram username" />
            <Input
              v-model="form.telegram_username"
              placeholder="e.g. alex_jr"
              @keydown.enter="save"
            />
          </div>
          <div>
            <FormLabel label="Telegram User ID" />
            <Input
              v-model="form.telegram_user_id"
              placeholder="e.g. 12345678"
              @keydown.enter="save"
            />
          </div>
        </div>

        <div class="flex items-center gap-2 pt-1">
          <Checkbox v-model="form.allow_carry_forward" id="allow_carry_forward" />
          <label for="allow_carry_forward" class="cursor-pointer text-sm text-ink-gray-7">
            Allow carry forward of unused pocket money to savings
          </label>
        </div>

        <p
          v-if="errorMessage"
          class="rounded-md bg-surface-red-1 px-3 py-2 text-sm text-ink-red-4"
        >
          {{ errorMessage }}
        </p>
      </div>
    </template>
    <template #actions="{ close }">
      <div class="flex justify-end gap-2">
        <Button variant="subtle" :disabled="saving" @click="close">Cancel</Button>
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Checkbox, Dialog, FormLabel, Input, Select, call } from 'frappe-ui'

const props = defineProps({
  open: { type: Boolean, default: false },
  dependent: { type: Object, default: null },
})

const emit = defineEmits(['update:open', 'saved'])

const RELATIONSHIPS = [
  'Son',
  'Daughter',
  'Brother',
  'Sister',
  'Spouse',
  'Parent',
  'Friend',
  'Other',
]

const form = reactive({
  dependent_name: '',
  relationship: 'Son',
  default_monthly_allowance: '',
  telegram_username: '',
  telegram_user_id: '',
  allow_carry_forward: true,
})

const saving = ref(false)
const errorMessage = ref('')

const isEditing = computed(() => Boolean(props.dependent))
const title = computed(() => (isEditing.value ? 'Edit dependent' : 'New dependent'))

watch(
  () => [props.open, props.dependent],
  () => {
    if (!props.open) return
    errorMessage.value = ''
    if (isEditing.value) {
      const dep = props.dependent
      form.dependent_name = dep.dependent_name || ''
      form.relationship = dep.relationship || 'Son'
      form.default_monthly_allowance = String(dep.default_monthly_allowance ?? '')
      form.telegram_username = dep.telegram_username || ''
      form.telegram_user_id = dep.telegram_user_id || ''
      form.allow_carry_forward = Boolean(dep.allow_carry_forward ?? true)
    } else {
      form.dependent_name = ''
      form.relationship = 'Son'
      form.default_monthly_allowance = ''
      form.telegram_username = ''
      form.telegram_user_id = ''
      form.allow_carry_forward = true
    }
  },
)

function closeDialog() {
  if (saving.value) return
  emit('update:open', false)
}

async function save() {
  if (!form.dependent_name.trim()) {
    errorMessage.value = 'Please enter dependent name.'
    return
  }
  if (form.default_monthly_allowance === '' || Number(form.default_monthly_allowance) < 0) {
    errorMessage.value = 'Please enter a valid monthly allowance.'
    return
  }

  saving.value = true
  errorMessage.value = null
  try {
    const payload = {
      dependent_name: form.dependent_name.trim(),
      relationship: form.relationship,
      default_monthly_allowance: Number(form.default_monthly_allowance),
      telegram_username: form.telegram_username.trim() || null,
      telegram_user_id: form.telegram_user_id.trim() || null,
      allow_carry_forward: form.allow_carry_forward ? 1 : 0,
    }
    const result = isEditing.value
      ? await call('expense_manager.api.dependents.update_dependent', {
          dependent: props.dependent.name,
          ...payload,
        })
      : await call('expense_manager.api.dependents.create_dependent', payload)

    if (result && result.success === false) {
      errorMessage.value = result.message
      return
    }
    emit('saved', result)
    emit('update:open', false)
  } catch (e) {
    errorMessage.value = e.message || 'Something went wrong. Please try again.'
  } finally {
    saving.value = false
  }
}
</script>
