<template>
	<div
		class="app-typography flex min-h-screen items-center justify-center bg-surface-gray-1 px-4"
	>
		<div
			class="w-full max-w-md rounded-xl border border-outline-gray-1 bg-surface-white p-8 shadow-sm"
		>
			<!-- Expenso Brand Header -->
			<div class="mb-6 flex items-center gap-2.5">
				<span
					class="grid size-9 place-items-center rounded-lg bg-surface-gray-2 text-ink-gray-7"
				>
					<span class="lucide-wallet size-5" />
				</span>
				<div>
					<span class="text-base font-semibold text-ink-gray-9">Expenso</span>
				</div>
			</div>

			<!-- Welcome Header -->
			<h1 class="text-2xl font-bold tracking-tight text-ink-gray-9">Welcome back</h1>
			<p class="mt-1 text-sm text-ink-gray-5">Log in to manage your family's expenses</p>

			<!-- Form -->
			<form class="mt-6 space-y-4" @submit.prevent="onSubmit">
				<div>
					<label class="mb-1.5 block text-xs font-medium text-ink-gray-7"
						>User ID or Email</label
					>
					<Input
						v-model="user"
						type="text"
						placeholder="you@example.com"
						autocomplete="username"
					/>
				</div>

				<div>
					<div class="mb-1.5 flex items-center justify-between">
						<label class="block text-xs font-medium text-ink-gray-7">Password</label>
						<a
							href="/update-password"
							class="text-xs text-ink-gray-5 hover:text-ink-gray-8"
						>
							Forgot password?
						</a>
					</div>
					<Input
						v-model="password"
						type="password"
						placeholder="••••••••"
						autocomplete="current-password"
					/>
				</div>

				<div
					v-if="error"
					class="rounded-lg bg-surface-red-1 p-3 text-xs font-medium text-ink-red-5"
				>
					{{ error }}
				</div>

				<Button
					class="w-full"
					variant="solid"
					type="submit"
					:loading="loading"
					:disabled="loading"
				>
					Log in
				</Button>
			</form>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { Input, Button, call } from "frappe-ui";

const user = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function onSubmit() {
	if (!user.value || !password.value) {
		error.value = "Enter your user ID and password";
		return;
	}
	loading.value = true;
	error.value = "";
	try {
		await call("login", { usr: user.value, pwd: password.value });
		window.location.href = import.meta.env.DEV ? "/" : "/expense_manager";
	} catch (e) {
		error.value = (e.messages && e.messages[0]) || "Login failed";
		loading.value = false;
	}
}
</script>
