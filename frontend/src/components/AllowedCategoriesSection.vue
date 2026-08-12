<template>
	<div class="mt-3 rounded-md border border-outline-gray-1 bg-surface-white">
		<button
			type="button"
			class="flex w-full items-center justify-between gap-2 p-3 text-left"
			@click="toggleExpand"
		>
			<span class="flex items-center gap-2 text-xs font-medium text-ink-gray-7">
				<ShieldCheck class="size-3.5" />
				Allowed categories
				<span
					v-if="loaded && pool.length > 0"
					class="rounded bg-surface-blue-1 px-1.5 py-0.5 text-xs font-medium text-ink-blue-5"
				>
					{{ effective.length }} of {{ pool.length }}
				</span>
			</span>
			<ChevronDown
				class="size-4 text-ink-gray-5 transition-transform"
				:class="expanded ? 'rotate-180' : ''"
			/>
		</button>

		<div v-if="expanded" class="space-y-3 border-t border-outline-gray-1 p-3">
			<p class="text-xs text-ink-gray-5">
				By default your dependent can use every category. Turn a category off to restrict
				them.
			</p>

			<p
				v-if="errorMessage"
				class="rounded-md bg-surface-red-1 px-3 py-2 text-sm text-ink-red-5"
			>
				{{ errorMessage }}
			</p>

			<div v-if="loading" class="space-y-2">
				<div
					v-for="i in 3"
					:key="i"
					class="h-8 animate-pulse rounded-md bg-surface-gray-2"
				/>
			</div>

			<p v-else-if="pool.length === 0" class="text-xs text-ink-gray-5">
				No active categories yet. Add categories first.
			</p>

			<div v-else class="grid grid-cols-2 gap-x-3 gap-y-2">
				<div
					v-for="cat in pool"
					:key="cat.name"
					class="flex items-center justify-between gap-2 rounded-md bg-surface-gray-1 px-2.5 py-2"
				>
					<span class="flex min-w-0 items-center gap-2 text-sm text-ink-gray-8">
						<span class="text-base">{{ cat.icon }}</span>
						<span class="truncate">{{ cat.category_name }}</span>
					</span>
					<Switch
						:model-value="Boolean(checked[cat.name])"
						:disabled="!dependent.is_active || busy[cat.name]"
						@change="onToggle(cat, $event)"
					/>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { Switch, call, request, toast } from "frappe-ui";
import ShieldCheck from "~icons/lucide/shield-check";
import ChevronDown from "~icons/lucide/chevron-down";

const props = defineProps({
	dependent: { type: Object, required: true },
});

const expanded = ref(false);
const loading = ref(false);
const loaded = ref(false);
const errorMessage = ref("");
const pool = ref([]);
const effective = ref([]);
const rawSet = ref(new Set());
const checked = reactive({});
const busy = reactive({});

async function load() {
	loading.value = true;
	errorMessage.value = "";
	try {
		await loadState();
		loaded.value = true;
	} catch (e) {
		errorMessage.value = e.message || "Could not load allowed categories.";
	} finally {
		loading.value = false;
	}
}

async function loadState() {
	if (pool.value.length === 0) {
		const res = await request({
			url: "/api/method/expense_manager.api.categories.list_categories",
			params: { active_only: 1 },
		});
		pool.value = res.message && res.message.success !== false ? res.message : [];
	}

	const allowedRes = await request({
		url: "/api/method/expense_manager.api.dependents.list_allowed_categories",
		params: { dependent: props.dependent.name, active_only: 1 },
	});
	effective.value =
		allowedRes.message && allowedRes.message.success !== false ? allowedRes.message : [];

	const depRes = await request({
		url: "/api/method/expense_manager.api.dependents.get_dependent",
		params: { dependent: props.dependent.name },
	});
	const dep = depRes.message || {};
	rawSet.value = new Set((dep.allowed_categories || []).map((row) => row.category));

	syncChecked();
}

function syncChecked() {
	const allowedNames = new Set(effective.value.map((cat) => cat.name));
	for (const cat of pool.value) {
		checked[cat.name] = allowedNames.has(cat.name);
	}
}

function toggleExpand() {
	expanded.value = !expanded.value;
	if (expanded.value && !loaded.value) {
		load();
	}
}

async function onToggle(cat, value) {
	if (busy[cat.name]) return;
	if (value === checked[cat.name]) return;
	busy[cat.name] = true;
	checked[cat.name] = value;
	errorMessage.value = "";
	try {
		if (value) {
			await call("expense_manager.api.dependents.add_allowed_category", {
				dependent: props.dependent.name,
				category: cat.name,
			});
			toast.success(
				`"${cat.category_name}" is allowed for ${props.dependent.dependent_name}.`
			);
		} else if (rawSet.value.has(cat.name)) {
			await call("expense_manager.api.dependents.remove_allowed_category", {
				dependent: props.dependent.name,
				category: cat.name,
			});
			toast.success(
				`"${cat.category_name}" restricted for ${props.dependent.dependent_name}.`
			);
		} else {
			for (const other of effective.value) {
				if (other.name !== cat.name) {
					await call("expense_manager.api.dependents.add_allowed_category", {
						dependent: props.dependent.name,
						category: other.name,
					});
				}
			}
			toast.success(
				`"${cat.category_name}" restricted for ${props.dependent.dependent_name}.`
			);
		}
	} catch (e) {
		toast.error(e.message || "Could not update allowed categories.");
		errorMessage.value = e.message || "Could not update allowed categories.";
	} finally {
		try {
			await loadState();
		} catch (e) {
			errorMessage.value = e.message || "Could not refresh allowed categories.";
		} finally {
			busy[cat.name] = false;
		}
	}
}
</script>
