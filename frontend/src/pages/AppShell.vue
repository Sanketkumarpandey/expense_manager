<template>
  <div class="flex h-screen overflow-hidden bg-surface-gray-1">
    <aside
      class="flex w-60 flex-shrink-0 flex-col border-r border-outline-gray-1 bg-surface-menu-bar"
    >
      <div class="flex items-center gap-2.5 px-4 pb-4 pt-5">
        <span class="grid size-8 place-items-center rounded-lg bg-surface-gray-3 text-ink-gray-7">
          <span class="lucide-wallet size-4.5" />
        </span>
        <div class="leading-tight">
          <p class="text-sm font-semibold text-ink-gray-9">Expense Manager</p>
          <p class="text-xs text-ink-gray-5">Family money, in one place</p>
        </div>
      </div>

      <nav class="flex-1 space-y-0.5 px-2">
        <router-link
          v-for="item in navItems"
          :key="item.route"
          :to="{ name: item.route }"
          class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors"
          :class="isActive(item.route)
            ? 'bg-surface-selected font-medium text-ink-gray-9'
            : 'text-ink-gray-7 hover:bg-surface-gray-2'"
        >
          <span class="size-4 flex-shrink-0" :class="item.icon" />
          <span class="truncate">{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="flex h-14 flex-shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-6"
      >
        <div>
          <h1 class="text-base font-semibold text-ink-gray-9">{{ pageTitle }}</h1>
        </div>
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-2">
            <Avatar :label="displayName" size="xl" />
            <span class="hidden text-sm text-ink-gray-7 sm:block">{{ displayName }}</span>
          </div>
          <Button variant="subtle" size="sm" :loading="loggingOut" @click="logout">
            <template #prefix>
              <span class="lucide-log-out size-4" />
            </template>
            <span class="hidden sm:inline">Log out</span>
          </Button>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Avatar, Button, call } from 'frappe-ui'

const route = useRoute()
const router = useRouter()
const loggingOut = ref(false)

const user = computed(() => window.user || 'Guest')
const displayName = computed(() => {
  if (!user.value || user.value === 'Guest') return 'Guest'
  return user.value
})

const pageTitle = computed(() => route.meta.title || 'Expense Manager')

const navItems = [
  { route: 'dashboard', label: 'Dashboard', icon: 'lucide-layout-dashboard' },
  { route: 'expenses', label: 'Expenses', icon: 'lucide-receipt' },
  { route: 'categories', label: 'Categories', icon: 'lucide-tag' },
  { route: 'budgets', label: 'Budgets', icon: 'lucide-target' },
  { route: 'dependents', label: 'Dependents', icon: 'lucide-users' },
  { route: 'reports', label: 'Reports', icon: 'lucide-chart-pie' },
  { route: 'telegram', label: 'Telegram', icon: 'lucide-send' },
]

function isActive(name) {
  return route.name === name
}

async function logout() {
  loggingOut.value = true
  try {
    await call('logout')
  } finally {
    window.location.href = import.meta.env.DEV ? '/login' : '/expense_manager/login'
  }
}
</script>
