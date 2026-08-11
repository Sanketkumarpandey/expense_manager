<template>
	<Popover placement="bottom-end" trigger="click" @open="focusInput">
		<template #target="{ togglePopover }">
			<Button variant="solid" data-testid="quick-add-trigger" @click="togglePopover">
				<template #prefix>
					<Plus class="size-4" />
				</template>
				Quick Add Expense
			</Button>
		</template>

		<template #body="{ close }">
			<div
				class="w-80 rounded-lg border border-outline-gray-1 bg-surface-white p-3 shadow-lg"
			>
				<p class="mb-2 text-sm font-medium text-ink-gray-9">Quick add expense</p>
				<Input
					ref="inputRef"
					v-model="text"
					data-testid="quick-add-input"
					placeholder="e.g. 500 on groceries"
					:disabled="loading"
					@keydown.enter="submit(close)"
				/>
				<p
					v-if="errorMessage"
					data-testid="quick-add-error"
					class="mt-1 text-sm text-ink-red-5"
				>
					{{ errorMessage }}
				</p>
				<div class="mt-3 flex justify-end gap-2">
					<Button variant="subtle" :disabled="loading" @click="close">Cancel</Button>
					<Button variant="solid" :loading="loading" @click="submit(close)">
						Add
					</Button>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup>
import { nextTick, ref } from "vue";
import { Button, Input, Popover, call, toast } from "frappe-ui";
import Plus from "~icons/lucide/plus";

const text = ref("");
const loading = ref(false);
const errorMessage = ref("");
const inputRef = ref(null);

const emit = defineEmits(["added"]);

const inr = (value) =>
	new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: "INR",
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	}).format(value || 0);

function focusInput() {
	nextTick(() => {
		if (inputRef.value) inputRef.value.focus();
	});
}

async function submit(close) {
	const value = text.value.trim();
	if (!value || loading.value) return;

	loading.value = true;
	errorMessage.value = "";
	try {
		const result = await call("expense_manager.api.expenses.create_expense_from_text", {
			text: value,
		});
		if (result && result.success === false) {
			errorMessage.value = result.message;
			return;
		}
		toast.success(
			`Added ${inr(result.amount)} under ${result.category_name || "a category"}.`
		);
		if (result.warning) {
			toast.warning(result.warning);
		}
		emit("added", result);
		text.value = "";
		close();
	} catch (e) {
		errorMessage.value = e.message || "Could not add the expense.";
	} finally {
		loading.value = false;
	}
}
</script>
