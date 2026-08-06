<template>
  <Dialog :open="open" :options="{ title }" size="md" @close="closeDialog">
    <template #body-content>
      <div class="space-y-4">
        <div>
          <FormLabel label="Dependent" required />
          <p class="text-sm font-medium text-ink-gray-9">
            {{ dependentName }}
          </p>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Allocated amount (₹)" required />
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
            <Select v-model="form.allocation_period" :options="PERIODS" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <FormLabel label="Allocation date" />
            <DatePicker v-model="form.allocation_date" />
          </div>
          <div>
            <FormLabel label="Carry forward amount (₹)" />
            <Input
              v-model="form.carry_forward_amount"
              type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              @keydown.enter="save"
            />
          </div>
        </div>

        <div>
          <FormLabel label="Remarks" />
          <Textarea v-model="form.remarks" placeholder="Optional notes or remarks" />
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
import { Button, DatePicker, Dialog, FormLabel, Input, Select, Textarea, call } from 'frappe-ui'

const props = defineProps({
  open: { type: Boolean, default: false },
  dependent: { type: Object, default: null },
  allocation: { type: Object, default: null },
})

const emit = defineEmits(['update:open', 'saved'])

const PERIODS = ['Weekly', 'Monthly', 'Quarterly', 'Yearly']

const today = new Date().toISOString().slice(0, 10)

const form = reactive({
  allocated_amount: '',
  allocation_period: 'Monthly',
  allocation_date: today,
  carry_forward_amount: '0',
  remarks: '',
})

const saving = ref(false)
const errorMessage = ref('')

const isEditing = computed(() => Boolean(props.allocation))
const title = computed(() => (isEditing.value ? 'Edit pocket money allocation' : 'Set pocket money allocation'))
const dependentName = computed(() => props.dependent?.dependent_name || 'Dependent')

watch(
  () => [props.open, props.allocation, props.dependent],
  () => {
    if (!props.open) return
    errorMessage.value = ''
    if (isEditing.value) {
      const alloc = props.allocation
      form.allocated_amount = String(alloc.allocated_amount ?? '')
      form.allocation_period = alloc.allocation_period || 'Monthly'
      form.allocation_date = alloc.allocation_date || today
      form.carry_forward_amount = String(alloc.carry_forward_amount ?? '0')
      form.remarks = alloc.remarks || ''
    } else {
      const defaultAllowance = props.dependent?.default_monthly_allowance
      form.allocated_amount = defaultAllowance !== undefined ? String(defaultAllowance) : ''
      form.allocation_period = 'Monthly'
      form.allocation_date = today
      form.carry_forward_amount = '0'
      form.remarks = ''
    }
  },
)

function closeDialog() {
  if (saving.value) return
  emit('update:open', false)
}

async function save() {
  if (form.allocated_amount === '' || Number(form.allocated_amount) < 0) {
    errorMessage.value = 'Please enter a valid allocated amount.'
    return
  }

  saving.value = true
  errorMessage.value = null
  try {
    const payload = {
      allocated_amount: Number(form.allocated_amount),
      allocation_period: form.allocation_period,
      allocation_date: form.allocation_date || today,
      carry_forward_amount: Number(form.carry_forward_amount || 0),
      remarks: form.remarks.trim() || null,
    }

    const result = isEditing.value
      ? await call('expense_manager.api.pocket_money.update_allocation', {
          allocation: props.allocation.name,
          ...payload,
        })
      : await call('expense_manager.api.pocket_money.create_allocation', {
          dependent: props.dependent.name,
          ...payload,
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
