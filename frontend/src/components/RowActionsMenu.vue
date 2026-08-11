<template>
	<Dropdown :options="menuItems" :button="null" align="end" portal-to="body">
		<template #trigger="{ open }">
			<Button
				variant="ghost"
				size="sm"
				title="Row actions"
				:class="open ? 'bg-surface-gray-2 text-ink-gray-9' : 'text-ink-gray-5'"
			>
				<template #prefix>
					<MoreHorizontal class="size-4" />
				</template>
			</Button>
		</template>
	</Dropdown>
</template>

<script setup>
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import MoreHorizontal from "~icons/lucide/more-horizontal";

const props = defineProps({
	items: { type: Array, default: () => [] },
});

const menuItems = computed(() => props.items);
</script>
