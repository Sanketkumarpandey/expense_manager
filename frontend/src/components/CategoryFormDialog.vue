<template>
	<Dialog :open="open" :options="{ title }" size="md" @close="closeDialog">
		<template #body-content>
			<div class="space-y-4">
				<div>
					<FormLabel label="Category name" required />
					<Input
						v-model="form.category_name"
						placeholder="e.g. Groceries"
						@keydown.enter="save"
					/>
				</div>

				<div>
					<FormLabel label="Icon" />
					<div class="flex items-center gap-2">
						<span
							class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-xl"
							:class="form.icon ? '' : 'text-ink-gray-4'"
						>
							{{ form.icon || "🙂" }}
						</span>
						<Input
							v-model="form.icon"
							maxlength="8"
							placeholder="Pick an emoji, e.g. 🛒"
							class="flex-1"
							@keydown.enter="save"
						/>
					</div>
					<p class="mt-1 text-xs text-ink-gray-5">
						Optional. Shown next to the category across the app.
					</p>
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
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, FormLabel, Input, call } from "frappe-ui";

const props = defineProps({
	open: { type: Boolean, default: false },
	category: { type: Object, default: null },
});

const emit = defineEmits(["update:open", "saved"]);

const form = reactive({
	category_name: "",
	icon: "",
});

const saving = ref(false);
const errorMessage = ref("");

const isEditing = computed(() => Boolean(props.category));
const title = computed(() => (isEditing.value ? "Edit category" : "New category"));

watch(
	() => [props.open, props.category],
	() => {
		if (!props.open) return;
		errorMessage.value = "";
		form.category_name = props.category ? props.category.category_name : "";
		form.icon = props.category ? props.category.icon || "" : "";
	}
);

function closeDialog() {
	if (saving.value) return;
	emit("update:open", false);
}

async function save() {
	if (!form.category_name.trim()) {
		errorMessage.value = "Please enter a category name.";
		return;
	}

	saving.value = true;
	errorMessage.value = null;
	try {
		const payload = {
			category_name: form.category_name.trim(),
			icon: form.icon.trim() || null,
		};
		const result = isEditing.value
			? await call("expense_manager.api.categories.update_category", {
					category: props.category.name,
					...payload,
			  })
			: await call("expense_manager.api.categories.create_category", payload);

		if (result && result.success === false) {
			errorMessage.value = result.message;
			return;
		}
		emit("saved", result);
		emit("update:open", false);
	} catch (e) {
		errorMessage.value = e.message || "Something went wrong. Please try again.";
	} finally {
		saving.value = false;
	}
}
</script>
