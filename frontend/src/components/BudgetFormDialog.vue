<template>
  <Dialog :open="open" :options="{ title }" size="md" @close="closeDialog">
    <template #body-content>
      <div class="space-y-4">
        <div>
          <FormLabel label="Category" required />
          <CategoryPicker v-model="form.category" :disabled="isEditing" />
        </div>

        <div>
          <FormLabel label="Scope" />
          <DependentPicker v-model="form.dependent" />
          <p class="mt-1 text-xs text-ink-gray-5">
            Leave empty for a household budget covering all dependents.
          </p>
        </div>

        <div>
          <FormLabel label="Allocated amount" required />
          <Input
            v-model="form.allocated_amount"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            @keydown.enter="save"
          />
        </div>

        <div>
          <FormLabel label="Period" required />
          <Select v-model="form.period" :options="PERIODS" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Start date" required />
            <DatePicker v-model="form.start_date" />
          </div>
          <div>
            <FormLabel label="End date" required />
            <DatePicker v-model="form.end_date" />
          </div>
        </div>

        <div>
          <FormLabel label="Alert threshold" />
          <Input
            v-model="form.alert_threshold_pct"
            type="number"
            min="1"
            max="100"
            step="1"
            placeholder="90"
            @keydown.enter="save"
          />
          <p class="mt-1 text-xs text-ink-gray-5">
            Percentage of the budget that flags as overspent. 1–100, default 90.
          </p>
        </div>

        <div>
          <FormLabel label="Notes" />
          <Textarea v-model="form.notes" placeholder="Optional notes" />
        </div>

        <p
          v-if="errorMessage"
          class="rounded-md bg-surface-red-1 px-3 py-2 text-sm text-ink-red-5"
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
  budget: { type: Object, default: null },
})

const emit = defineEmits(['update:open', 'saved'])

const PERIODS = ['Weekly', 'Monthly', 'Quarterly', 'Yearly']

const now = new Date()
const pad = (n) => String(n).padStart(2, '0')
const firstOfMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-01`
const lastOfMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate())}`

const form = reactive({
  category: null,
  dependent: null,
  allocated_amount: '',
  period: 'Monthly',
  start_date: firstOfMonth,
  end_date: lastOfMonth,
  alert_threshold_pct: 90,
  notes: '',
})

const saving = ref(false)
const errorMessage = ref('')

const isEditing = computed(() => Boolean(props.budget))
const title = computed(() => (isEditing.value ? 'Edit budget' : 'New budget'))

watch(
  () => [props.open, props.budget],
  () => {
    if (!props.open) return
    errorMessage.value = ''
    if (isEditing.value) {
      form.category = props.budget.category
      form.dependent = props.budget.dependent || null
      form.allocated_amount = String(props.budget.allocated_amount ?? '')
      form.period = props.budget.period
      form.start_date = props.budget.start_date
      form.end_date = props.budget.end_date
      form.alert_threshold_pct = props.budget.alert_threshold_pct ?? 90
      form.notes = props.budget.notes || ''
    } else {
      form.category = null
      form.dependent = null
      form.allocated_amount = ''
      form.period = 'Monthly'
      form.start_date = firstOfMonth
      form.end_date = lastOfMonth
      form.alert_threshold_pct = 90
      form.notes = ''
    }
  },
)

function closeDialog() {
  if (saving.value) return
  emit('update:open', false)
}

async function save() {
  if (!form.category) {
    errorMessage.value = 'Please select a category.'
    return
  }
  if (!form.allocated_amount || Number(form.allocated_amount) <= 0) {
    errorMessage.value = 'Please enter a valid allocated amount.'
    return
  }

  saving.value = true
  errorMessage.value = null
  try {
    const result = isEditing.value
      ? await call('expense_manager.api.budgets.update_budget', {
          budget: props.budget.name,
          allocated_amount: Number(form.allocated_amount),
          period: form.period,
          start_date: form.start_date,
          end_date: form.end_date,
          alert_threshold_pct: Number(form.alert_threshold_pct),
          notes: form.notes,
        })
      : await call('expense_manager.api.budgets.create_budget', {
          category: form.category,
          dependent: form.dependent,
          allocated_amount: Number(form.allocated_amount),
          period: form.period,
          start_date: form.start_date,
          end_date: form.end_date,
          alert_threshold_pct: Number(form.alert_threshold_pct),
          notes: form.notes,
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
