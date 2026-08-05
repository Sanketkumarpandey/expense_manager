<template>
  <div class="flex h-screen items-center justify-center bg-gray-50">
    <div class="w-80 rounded-lg border border-gray-200 bg-white p-6">
      <h1 class="text-xl font-semibold text-gray-800">Expense Manager</h1>
      <p class="mb-6 mt-1 text-sm text-gray-500">Sign in to continue</p>
      <form @submit.prevent="onSubmit">
        <Input
          v-model="user"
          class="mb-3"
          type="text"
          label="User ID"
          placeholder="you@example.com"
          autocomplete="username"
        />
        <Input
          v-model="password"
          class="mb-4"
          type="password"
          label="Password"
          placeholder="Your password"
          autocomplete="current-password"
        />
        <p v-if="error" class="mb-3 text-sm text-red-600">{{ error }}</p>
        <Button variant="solid" type="submit" :loading="loading" :disabled="loading">
          Log in
        </Button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Input, Button, call } from 'frappe-ui'

const user = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  if (!user.value || !password.value) {
    error.value = 'Enter your user ID and password'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await call('login', { usr: user.value, pwd: password.value })
    window.location.href = import.meta.env.DEV ? '/' : '/expense_manager'
  } catch (e) {
    error.value = (e.messages && e.messages[0]) || 'Login failed'
    loading.value = false
  }
}
</script>
