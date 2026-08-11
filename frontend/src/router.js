import { createRouter, createWebHistory } from "vue-router";
import LoginPage from "@/pages/LoginPage.vue";
import AppShell from "@/pages/AppShell.vue";

function isAuthenticated() {
	return window.user && window.user !== "Guest";
}

let routes = [
	{
		path: "/",
		name: "index",
		redirect: () => (isAuthenticated() ? "/dashboard" : "/login"),
	},
	{
		path: "/login",
		name: "login",
		component: LoginPage,
		meta: { title: "Log in" },
	},
	{
		path: "/",
		component: AppShell,
		meta: { requiresAuth: true },
		children: [
			{
				path: "dashboard",
				name: "dashboard",
				component: () => import("@/pages/DashboardPage.vue"),
				meta: { title: "Dashboard" },
			},
			{
				path: "expenses",
				name: "expenses",
				component: () => import("@/pages/ExpensesPage.vue"),
				meta: { title: "Expenses" },
			},
			{
				path: "categories",
				name: "categories",
				component: () => import("@/pages/CategoriesPage.vue"),
				meta: { title: "Categories" },
			},
			{
				path: "budgets",
				name: "budgets",
				component: () => import("@/pages/BudgetsPage.vue"),
				meta: { title: "Budgets" },
			},
			{
				path: "dependents",
				name: "dependents",
				component: () => import("@/pages/DependentsPage.vue"),
				meta: { title: "Dependents" },
			},
			{
				path: "reports",
				name: "reports",
				component: () => import("@/pages/ReportsPage.vue"),
				meta: { title: "Reports" },
			},
			{
				path: "telegram",
				name: "telegram",
				component: () => import("@/pages/TelegramPage.vue"),
				meta: { title: "Telegram" },
			},
		],
	},
];

let router = createRouter({
	history: createWebHistory(import.meta.env.DEV ? "/" : "/expense_manager/"),
	routes,
});

router.beforeEach((to) => {
	if (to.name === "login" && isAuthenticated()) {
		return { name: "dashboard" };
	}
	if (to.meta.requiresAuth && !isAuthenticated()) {
		return { name: "login" };
	}
});

router.afterEach((to) => {
	document.title = to.meta.title
		? `${to.meta.title} — Expenso`
		: "Expenso — Family Expense Manager";
});

export default router;
