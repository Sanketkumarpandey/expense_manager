import { createResource } from "frappe-ui";

export const dependentsResource = createResource({
	url: "expense_manager.api.dependents.list_dependents",
	method: "GET",
	auto: true,
	params: { active_only: 1 },
});

export const categoriesResource = createResource({
	url: "expense_manager.api.categories.list_categories",
	method: "GET",
	auto: true,
	params: { active_only: 1 },
});
