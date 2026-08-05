<template>
  <Dialog :open="open" :options="{ title }" size="md" @close="closeDialog">
    <template #body-content>
      <div class="space-y-4">
        <div>
          <FormLabel label="Category" required />
          <CategoryPicker v-model="form.category" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Amount" required />
            <Input
              v-model="form.amount"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              @keydown.enter="save"
            />
          </div>
          <div>
            <FormLabel label="Date" required />
            <DatePicker v-model="form.expense_date" />
          </div>
        </div>

        <div>
          <FormLabel label="Dependent (optional)" />
          <DependentPicker v-model="form.dependent" />
        </div>

        <div>
          <FormLabel label="Description" />
          <Textarea v-model="form.description" placeholder="What was this for?" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Payment method" />
            <Select
              v-model="form.payment_method"
              :options="PAYMENT_METHODS"
              placeholder="Select method"
            />
          </div>
          <div v-if="!isEditing">
            <FormLabel label="Source" />
            <Select
              v-model="form.source"
              :options="SOURCES"
              placeholder="Select source"
            />
          </div>
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
import {
  Button,
  DatePicker,
  Dialog,
  FormLabel,
  Input,
  Select,
  Textarea,
  call,
} from 'frappe-ui'
import CategoryPicker from '@/components/CategoryPicker.vue'
import DependentPicker from '@/components/DependentPicker.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  expense: { type: Object, default: null },
})

const emit = defineEmits(['update:open', 'saved'])

const PAYMENT_METHODS = [
  'Cash',
  'UPI',
  'Credit Card',
  'Debit Card',
  'Net Banking',
  'Wallet',
  'Other',
]
const SOURCES = ['Manual', 'Web', 'API', 'Telegram']

const today = new Date().toISOString().slice(0, 10)

const form = reactive({
  category: null,
  amount: '',
  expense_date: today,
  dependent: null,
  description: '',
  payment_method: '',
  source: 'Manual',
})

const saving = ref(false)
const errorMessage = ref('')

const isEditing = computed(() => Boolean(props.expense))
const title = computed(() => (isEditing.value ? 'Edit expense' : 'New expense'))

watch(
  () => [props.open, props.expense],
  () => {
    if (!props.open) return
    errorMessage.value = ''
    if (isEditing.value) {
      const expense = props.expense
      form.category = expense.category
      form.amount = expense.amount
      form.expense_date = expense.expense_date
      form.dependent = expense.dependent || null
      form.description = expense.description || ''
      form.payment_method = expense.payment_method || ''
    } else {
      form.category = null
      form.amount = ''
      form.expense_date = today
      form.dependent = null
      form.description = ''
      form.payment_method = ''
      form.source = 'Manual'
    }
  },
)

function closeDialog() {
  if (saving.value) return
  emit('update:open', false)
}

function validate() {
  if (!form.category) return 'Please select a category.'
  if (form.amount === '' || Number(form.amount) <= 0) {
    return 'Please enter a valid amount.'
  }
  if (!form.expense_date) return 'Please select a date.'
  return null
}

async function save() {
  errorMessage.value = validate()
  if (errorMessage.value) return

  saving.value = true
  try {
    const payload = {
      category: form.category,
      amount: Number(form.amount),
      expense_date: form.expense_date,
      dependent: form.dependent || null,
      description: form.description || null,
      payment_method: form.payment_method || null,
    }
    const result = isEditing.value
      ? await call('expense_manager.api.expenses.update_expense', {
          expense: props.expense.name,
          ...payload,
        })
      : await call('expense_manager.api.expenses.create_expense', {
          ...payload,
          source: form.source || 'Manual',
        })

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
