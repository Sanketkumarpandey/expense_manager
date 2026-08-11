<template>
	<div class="space-y-6">
		<OverspendBanner v-if="overspend" :overspend="overspend" @dismiss="overspend = null" />

		<div class="flex flex-wrap items-center justify-between gap-3">
			<div class="flex items-center gap-2">
				<p class="text-sm text-ink-gray-5">
					{{ expenses.length }} {{ expenses.length === 1 ? "expense" : "expenses" }}
				</p>
				<span
					v-if="hasFilters"
					class="rounded-full bg-surface-blue-1 px-2 py-0.5 text-xs font-medium text-ink-blue-5"
				>
					Filtered
				</span>
			</div>
			<div class="flex items-center gap-2">
				<Button
					variant="subtle"
					size="sm"
					data-testid="filter-toggle"
					:class="
						showFilters || hasFilters
							? 'bg-surface-gray-2 text-ink-gray-9 font-medium'
							: 'text-ink-gray-7'
					"
					@click="showFilters = !showFilters"
				>
					<template #prefix>
						<SlidersHorizontal class="size-4" />
					</template>
					Filters
					<span
						v-if="activeFilterCount"
						class="ml-1.5 rounded-full bg-surface-gray-3 px-1.5 py-0.2 text-xs font-medium text-ink-gray-7"
					>
						{{ activeFilterCount }}
					</span>
				</Button>
				<Button variant="solid" size="sm" @click="openCreate">
					<template #prefix>
						<span class="lucide-plus size-4 text-white" />
					</template>
					New expense
				</Button>
			</div>
		</div>

		<section
			v-if="showFilters || hasFilters"
			class="space-y-3 rounded-lg border border-outline-gray-1 bg-surface-white p-4 shadow-sm"
		>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 sm:gap-4">
				<div class="flex min-w-0 flex-col gap-1.5">
					<FormLabel label="Dependent" />
					<DependentPicker v-model="filters.dependent" placeholder="All dependents" />
				</div>

				<div class="flex min-w-0 flex-col gap-1.5">
					<FormLabel label="Category" />
					<CategoryPicker v-model="filters.category" placeholder="All categories" />
				</div>

				<div class="flex min-w-0 flex-col gap-1.5">
					<FormLabel label="From date" />
					<DatePicker v-model="filters.date_from" placeholder="Start date" />
				</div>

				<div class="flex min-w-0 flex-col gap-1.5">
					<FormLabel label="To date" />
					<DatePicker v-model="filters.date_to" placeholder="End date" />
				</div>
			</div>

			<div
				v-if="hasFilters"
				class="flex flex-wrap items-center justify-between gap-2 border-t border-outline-gray-1 pt-3"
			>
				<div class="flex flex-wrap items-center gap-2">
					<span class="text-xs font-medium text-ink-gray-5">Active filters:</span>

					<span
						v-if="filters.dependent"
						class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-8"
					>
						<span
							>Dependent:
							<strong>{{ getDependentLabel(filters.dependent) }}</strong></span
						>
						<button
							type="button"
							class="ml-0.5 text-ink-gray-5 hover:text-ink-gray-9"
							title="Remove dependent filter"
							@click="filters.dependent = null"
						>
							<X class="size-3" />
						</button>
					</span>

					<span
						v-if="filters.category"
						class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-8"
					>
						<span
							>Category:
							<strong>{{ getCategoryLabel(filters.category) }}</strong></span
						>
						<button
							type="button"
							class="ml-0.5 text-ink-gray-5 hover:text-ink-gray-9"
							title="Remove category filter"
							@click="filters.category = null"
						>
							<X class="size-3" />
						</button>
					</span>

					<span
						v-if="filters.date_from"
						class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-8"
					>
						<span
							>From: <strong>{{ filters.date_from }}</strong></span
						>
						<button
							type="button"
							class="ml-0.5 text-ink-gray-5 hover:text-ink-gray-9"
							title="Remove from date filter"
							@click="filters.date_from = null"
						>
							<X class="size-3" />
						</button>
					</span>

					<span
						v-if="filters.date_to"
						class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2.5 py-1 text-xs text-ink-gray-8"
					>
						<span
							>To: <strong>{{ filters.date_to }}</strong></span
						>
						<button
							type="button"
							class="ml-0.5 text-ink-gray-5 hover:text-ink-gray-9"
							title="Remove to date filter"
							@click="filters.date_to = null"
						>
							<X class="size-3" />
						</button>
					</span>
				</div>

				<Button
					variant="subtle"
					size="sm"
					class="text-xs text-ink-gray-6 hover:text-ink-red-5"
					@click="clearFilters"
				>
					<template #prefix>
						<X class="size-3.5" />
					</template>
					Clear all
				</Button>
			</div>
		</section>

		<ResourceState :resource="list" label="your expenses">
			<template #skeleton>
				<div class="space-y-2">
					<div
						v-for="i in 4"
						:key="i"
						class="h-16 animate-pulse rounded-lg bg-surface-gray-2"
					/>
				</div>
			</template>

			<EmptyState
				v-if="expenses.length === 0"
				:icon="Receipt"
				:title="hasFilters ? 'No matching expenses' : 'No expenses found'"
				:description="
					hasFilters
						? 'Try adjusting your filters or date range.'
						: 'Add a new expense to get started.'
				"
			>
				<template #action>
					<Button v-if="hasFilters" variant="subtle" size="sm" @click="clearFilters">
						Clear filters
					</Button>
					<Button v-else variant="solid" size="sm" @click="openCreate">
						Add expense
					</Button>
				</template>
			</EmptyState>

			<div
				v-else
				class="overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-white shadow-sm"
			>
				<div
					class="hidden items-center gap-4 border-b border-outline-gray-1 bg-surface-gray-1/50 px-4 py-2.5 text-xs font-medium text-ink-gray-5 md:flex"
				>
					<span class="w-24 shrink-0">Date</span>
					<span class="flex-1">Description</span>
					<span class="w-32 shrink-0 text-center">Category</span>
					<span class="w-28 shrink-0 text-right">Amount</span>
					<span class="w-20 shrink-0" />
				</div>

				<div
					class="max-h-[60vh] md:max-h-[65vh] overflow-y-auto divide-y divide-outline-gray-1"
				>
					<div
						v-for="expense in expenses"
						:key="expense.name"
						class="flex items-center gap-4 px-4 py-3 hover:bg-surface-gray-1/50 transition-colors"
					>
						<span class="hidden w-24 shrink-0 text-sm text-ink-gray-5 md:block">
							{{ formatDate(expense.expense_date) }}
						</span>

						<div class="flex min-w-0 flex-1 items-center gap-3">
							<span
								class="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-gray-2 text-lg"
							>
								{{ expense.category_icon || "🏷️" }}
							</span>
							<div class="min-w-0">
								<p class="truncate text-sm font-medium text-ink-gray-9">
									{{ expense.description || expense.category_name || "Expense" }}
								</p>
								<p class="truncate text-xs text-ink-gray-5">
									<span class="md:hidden">{{
										formatDate(expense.expense_date)
									}}</span>
									<span
										v-if="expense.dependent_name"
										class="text-ink-gray-4 md:hidden"
									>
										· {{ expense.dependent_name }}
									</span>
									<span v-if="expense.payment_method" class="text-ink-gray-4">
										· {{ expense.payment_method }}
									</span>
								</p>
							</div>
						</div>

						<div class="hidden w-32 shrink-0 flex-col items-center gap-1 md:flex">
							<span
								class="max-w-full truncate rounded-full bg-surface-gray-2 px-2.5 py-0.5 text-center text-xs text-ink-gray-7"
							>
								{{ expense.category_name || expense.category }}
							</span>
							<span
								v-if="expense.dependent_name"
								class="max-w-full truncate text-xs text-ink-gray-4"
							>
								{{ expense.dependent_name }}
							</span>
						</div>

						<p class="w-28 shrink-0 text-right text-sm font-semibold text-ink-gray-9">
							{{ inr(expense.amount) }}
						</p>

						<div class="flex w-20 shrink-0 items-center justify-end pl-1">
							<RowActionsMenu :items="rowActions(expense)" />
						</div>
					</div>
				</div>
			</div>
		</ResourceState>

		<ExpenseFormDialog v-model:open="formOpen" :expense="editingExpense" @saved="onSaved" />

		<ConfirmDialog
			v-model:open="confirmOpen"
			title="Delete expense?"
			:message="deleteMessage"
			confirm-label="Delete"
			:loading="deleting"
			@confirm="confirmDelete"
		/>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { Button, DatePicker, FormLabel, call, createResource, toast } from "frappe-ui";
import SlidersHorizontal from "~icons/lucide/sliders-horizontal";
import X from "~icons/lucide/x";
import Pencil from "~icons/lucide/pencil";
import Trash2 from "~icons/lucide/trash-2";
import Receipt from "~icons/lucide/receipt";
import ResourceState from "@/components/ResourceState.vue";
import ExpenseFormDialog from "@/components/ExpenseFormDialog.vue";
import ConfirmDialog from "@/components/ConfirmDialog.vue";
import OverspendBanner from "@/components/OverspendBanner.vue";
import RowActionsMenu from "@/components/RowActionsMenu.vue";
import EmptyState from "@/components/EmptyState.vue";
import CategoryPicker from "@/components/CategoryPicker.vue";
import DependentPicker from "@/components/DependentPicker.vue";
import { categoriesResource, dependentsResource } from "@/data/catalog";

const overspend = ref(null);

const filters = reactive({
	dependent: null,
	category: null,
	date_from: null,
	date_to: null,
});

const showFilters = ref(false);

function buildFilters() {
	const params = {};
	if (filters.dependent) params.dependent = filters.dependent;
	if (filters.category) params.category = filters.category;
	if (filters.date_from) params.date_from = filters.date_from;
	if (filters.date_to) params.date_to = filters.date_to;
	return params;
}

const list = createResource({
	url: "expense_manager.api.expenses.list_expenses",
	method: "GET",
	auto: true,
	makeParams: buildFilters,
});

const expenses = computed(() => list.data || []);

const hasFilters = computed(() => {
	return Boolean(filters.dependent || filters.category || filters.date_from || filters.date_to);
});

const activeFilterCount = computed(() => {
	let count = 0;
	if (filters.dependent) count++;
	if (filters.category) count++;
	if (filters.date_from) count++;
	if (filters.date_to) count++;
	return count;
});

watch(
	filters,
	() => {
		list.reload();
	},
	{ deep: true }
);

function clearFilters() {
	filters.dependent = null;
	filters.category = null;
	filters.date_from = null;
	filters.date_to = null;
}

function getDependentLabel(id) {
	const deps = dependentsResource.data || [];
	const found = deps.find((d) => d.name === id);
	return found ? found.dependent_name : id;
}

function getCategoryLabel(id) {
	const cats = categoriesResource.data || [];
	const found = cats.find((c) => c.name === id);
	return found
		? found.icon
			? `${found.icon} ${found.category_name}`
			: found.category_name
		: id;
}

const formOpen = ref(false);
const editingExpense = ref(null);

function openCreate() {
	editingExpense.value = null;
	formOpen.value = true;
}

function openEdit(expense) {
	editingExpense.value = expense;
	formOpen.value = true;
}

function onSaved(result) {
	list.reload();
	if (result && result.overspend) {
		overspend.value = result.overspend;
	} else if (result && result.warning) {
		toast.warning(result.warning);
	}
	if (editingExpense.value) {
		toast.success("Expense updated.");
	} else {
		toast.success(
			`Added ${inr(result.amount)} under ${result.category_name || "a category"}.`
		);
	}
}

const confirmOpen = ref(false);
const deleting = ref(false);
const deleteTarget = ref(null);
const deleteMessage = computed(() => {
	if (!deleteTarget.value) return "";
	const label =
		deleteTarget.value.description || deleteTarget.value.category_name || "this expense";
	return `Are you sure you want to delete "${label}" (${inr(
		deleteTarget.value.amount
	)})? This cannot be undone.`;
});

function requestDelete(expense) {
	deleteTarget.value = expense;
	confirmOpen.value = true;
}

async function confirmDelete() {
	deleting.value = true;
	try {
		const result = await call("expense_manager.api.expenses.delete_expense", {
			expense: deleteTarget.value.name,
		});
		if (result && result.success === false) {
			toast.error(result.message);
		} else {
			toast.success("Expense deleted.");
			list.reload();
		}
		confirmOpen.value = false;
	} catch (e) {
		toast.error(e.message || "Could not delete the expense.");
		confirmOpen.value = false;
	} finally {
		deleting.value = false;
	}
}

const inr = (value) =>
	new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: "INR",
		minimumFractionDigits: 0,
		maximumFractionDigits: 2,
	}).format(value || 0);

function formatDate(value) {
	if (!value) return "";
	return new Date(value).toLocaleDateString("en-IN", {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
}

function rowActions(expense) {
	return [
		{
			label: "Edit",
			icon: Pencil,
			onClick: () => openEdit(expense),
		},
		{
			label: "Delete",
			icon: Trash2,
			theme: "red",
			onClick: () => requestDelete(expense),
		},
	];
}
</script>
