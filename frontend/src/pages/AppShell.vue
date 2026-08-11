<template>
  <div class="flex h-screen overflow-hidden bg-surface-gray-1">
    <aside
      class="fixed inset-y-0 left-0 z-40 flex flex-shrink-0 flex-col border-r border-outline-gray-1 bg-surface-menu-bar transition-[width,transform] duration-200 md:static"
      :class="{
        'w-14': effectiveCollapsed,
        'w-60': !effectiveCollapsed,
        '-translate-x-full md:translate-x-0': !mobileNavOpen,
        'translate-x-0': mobileNavOpen,
      }"
    >
      <div
        class="flex items-center gap-2.5 px-4 pb-4 pt-5"
        :class="effectiveCollapsed ? 'justify-center px-2' : ''"
      >
        <span class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-gray-3 text-ink-gray-7">
          <span class="lucide-wallet size-4.5" />
        </span>
        <div v-if="!effectiveCollapsed" class="min-w-0 leading-tight">
          <p class="truncate text-sm font-semibold text-ink-gray-9">Expenso</p>
          <p class="truncate text-xs text-ink-gray-5">Family money, in one place</p>
        </div>
      </div>

      <nav class="flex-1 space-y-0.5 px-2">
        <router-link
          v-for="item in navItems"
          :key="item.route"
          :to="{ name: item.route }"
          :title="effectiveCollapsed ? item.label : undefined"
          class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm leading-normal transition-colors"
          :class="effectiveCollapsed ? 'justify-center px-0' : ''"
          :aria-label="item.label"
        >
          <span
            class="size-4 flex-shrink-0"
            :class="[item.icon, isActive(item.route)
              ? 'text-ink-gray-9'
              : 'text-ink-gray-7']"
          />
          <span
            v-if="!effectiveCollapsed"
            class="min-w-0 flex-1 truncate py-0.5 leading-normal"
            :class="isActive(item.route) ? 'font-medium text-ink-gray-9' : 'text-ink-gray-7'"
          >{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="space-y-1 border-t border-outline-gray-1 p-2">
        <button
          class="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm leading-normal text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
          :class="effectiveCollapsed ? 'justify-center px-0' : ''"
          :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggleTheme"
        >
          <Sun v-if="isDark" class="size-4 flex-shrink-0" />
          <Moon v-else class="size-4 flex-shrink-0" />
          <span v-if="!effectiveCollapsed" class="min-w-0 flex-1 truncate py-0.5 text-left leading-normal">{{ isDark ? 'Light mode' : 'Dark mode' }}</span>
        </button>
        <button
          class="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm leading-normal text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
          :class="effectiveCollapsed ? 'justify-center px-0' : ''"
          :title="isMobile ? 'Close menu' : (collapsed ? 'Expand sidebar' : 'Collapse sidebar')"
          @click="toggleSidebar"
        >
          <X v-if="isMobile && mobileNavOpen" class="size-4 flex-shrink-0" />
          <PanelLeftOpen v-else-if="isMobile || collapsed" class="size-4 flex-shrink-0" />
          <PanelLeftClose v-else class="size-4 flex-shrink-0" />
          <span v-if="!effectiveCollapsed" class="min-w-0 flex-1 truncate py-0.5 text-left leading-normal">{{ isMobile ? 'Close' : (collapsed ? 'Expand' : 'Collapse') }}</span>
        </button>
      </div>
    </aside>

    <div
      v-if="mobileNavOpen"
      class="fixed inset-0 z-30 bg-black/40 md:hidden"
      @click="mobileNavOpen = false"
    />

    <div class="app-typography flex min-w-0 flex-1 flex-col">
      <header
        class="flex h-14 flex-shrink-0 items-center justify-between border-b border-outline-gray-1 bg-surface-white px-6"
      >
        <div class="flex items-center gap-3">
          <button
            class="rounded-md p-1.5 text-ink-gray-7 transition-colors hover:bg-surface-gray-2"
            :title="isMobile ? 'Menu' : (collapsed ? 'Expand sidebar' : 'Collapse sidebar')"
            @click="toggleSidebar"
          >
            <X v-if="isMobile && mobileNavOpen" class="size-4" />
            <PanelLeftOpen v-else-if="isMobile || collapsed" class="size-4" />
            <PanelLeftClose v-else class="size-4" />
          </button>
          <h1 class="text-base font-semibold text-ink-gray-9">{{ pageTitle }}</h1>
        </div>
        <div class="flex items-center gap-3">
          <Dropdown :options="userMenuOptions" align="end">
            <template #trigger>
              <div
                class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-surface-gray-2"
                :title="displayName"
              >
                <Avatar :label="displayName" size="xl" />
                <span class="hidden text-sm text-ink-gray-7 sm:block">{{ displayName }}</span>
              </div>
            </template>
          </Dropdown>
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, Button, call, useTheme, Dropdown } from 'frappe-ui'
import PanelLeftClose from '~icons/lucide/panel-left-close'
import PanelLeftOpen from '~icons/lucide/panel-left-open'
import Sun from '~icons/lucide/sun'
import Moon from '~icons/lucide/moon'
import X from '~icons/lucide/x'
import LogOut from '~icons/lucide/log-out'
import User from '~icons/lucide/user'

const route = useRoute()
const loggingOut = ref(false)

const collapsed = ref(localStorage.getItem('appshell.sidebar_collapsed') === '1')
const mobileNavOpen = ref(false)
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth < 768)
const effectiveCollapsed = computed(() => collapsed.value && !mobileNavOpen.value)

function onResize() {
  isMobile.value = window.innerWidth < 768
}
window.addEventListener('resize', onResize)
onBeforeUnmount(() => window.removeEventListener('resize', onResize))

watch(
  () => route.path,
  () => {
    mobileNavOpen.value = false
  },
)

const { currentTheme, toggleTheme, getSystemTheme } = useTheme()
const isDark = computed(
  () =>
    currentTheme.value === 'dark' ||
    (currentTheme.value === 'system' && getSystemTheme() === 'dark'),
)

function toggleSidebar() {
  if (isMobile.value) {
    mobileNavOpen.value = !mobileNavOpen.value
  } else {
    collapsed.value = !collapsed.value
    localStorage.setItem('appshell.sidebar_collapsed', collapsed.value ? '1' : '0')
  }
}

const user = computed(() => window.user || 'Guest')
const displayName = computed(() => {
  if (!user.value || user.value === 'Guest') return 'Guest'
  return user.value
})

const userMenuOptions = [
  {
    label: displayName.value,
    icon: User,
    disabled: true,
  },
  {
    type: 'separator',
  },
  {
    label: 'Log out',
    icon: LogOut,
    onClick: logout,
  },
]

const pageTitle = computed(() => route.meta.title || 'Expenso')

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
