<template>
	<Dialog :open="open" :options="{ title }" @close="$emit('update:open', false)">
		<template #body-content>
			<p class="text-p-base text-ink-gray-7">{{ message }}</p>
		</template>
		<template #actions="{ close }">
			<div class="flex justify-end gap-2">
				<Button variant="subtle" :disabled="loading" @click="close">Cancel</Button>
				<Button variant="solid" theme="red" :loading="loading" @click="confirm">
					{{ confirmLabel }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Button, Dialog } from "frappe-ui";

defineProps({
	open: { type: Boolean, default: false },
	title: { type: String, default: "Are you sure?" },
	message: { type: String, default: "" },
	confirmLabel: { type: String, default: "Delete" },
	loading: { type: Boolean, default: false },
});

const emit = defineEmits(["update:open", "confirm"]);

function confirm() {
	emit("confirm");
}
</script>
