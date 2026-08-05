<template>
  <div class="space-y-6 max-w-3xl">
    <ResourceState :resource="statusResource" label="Telegram link status">
      <template #skeleton>
        <div class="h-48 animate-pulse rounded-lg bg-surface-gray-2" />
      </template>

      <div v-if="isLinked" class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 space-y-6">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-3">
            <span class="grid size-12 place-items-center rounded-xl bg-surface-green-1 text-ink-green-3">
              <CheckCircle class="size-6" />
            </span>
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-lg font-semibold text-ink-gray-9">Telegram Connected</h2>
                <span class="rounded bg-surface-green-1 px-2 py-0.5 text-xs font-medium text-ink-green-3">
                  Active Link
                </span>
              </div>
              <p class="text-sm text-ink-gray-5 mt-0.5">
                Your Frappe account is linked to your Telegram profile.
              </p>
            </div>
          </div>

          <Button
            variant="outline"
            theme="red"
            size="sm"
            @click="confirmUnlinkOpen = true"
          >
            <template #prefix>
              <Unlink class="size-4" />
            </template>
            Unlink account
          </Button>
        </div>

        <div class="border-t border-outline-gray-1 pt-4 space-y-3">
          <h3 class="text-sm font-medium text-ink-gray-9">Features available on Telegram:</h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-ink-gray-7">
            <div class="flex items-center gap-2">
              <Mic class="size-4 text-ink-blue-5" />
              <span>Voice expense tracking (Sarvam AI)</span>
            </div>
            <div class="flex items-center gap-2">
              <MessageSquare class="size-4 text-ink-blue-5" />
              <span>Free-text expense parsing (Groq LLM)</span>
            </div>
            <div class="flex items-center gap-2">
              <Bell class="size-4 text-ink-blue-5" />
              <span>Instant budget overspend alerts</span>
            </div>
            <div class="flex items-center gap-2">
              <BarChart3 class="size-4 text-ink-blue-5" />
              <span>Daily & monthly summary nudges</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 space-y-6">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-center gap-3">
            <span class="grid size-12 place-items-center rounded-xl bg-surface-gray-2 text-ink-gray-6">
              <Send class="size-6" />
            </span>
            <div>
              <h2 class="text-lg font-semibold text-ink-gray-9">Link Telegram Account</h2>
              <p class="text-sm text-ink-gray-5 mt-0.5">
                Connect your Telegram account to log expenses via voice notes & chat.
              </p>
            </div>
          </div>
        </div>

        <div v-if="!linkCode" class="border-t border-outline-gray-1 pt-6 text-center space-y-4">
          <p class="text-sm text-ink-gray-6 max-w-md mx-auto">
            Click the button below to generate a unique code. You will send this code to our Telegram bot to verify your account.
          </p>
          <Button
            variant="solid"
            size="md"
            :loading="generating"
            @click="generateCode"
          >
            <template #prefix>
              <Key class="size-4" />
            </template>
            Generate Link Code
          </Button>
        </div>

        <div v-else class="border-t border-outline-gray-1 pt-6 space-y-6">
          <div class="rounded-lg bg-surface-gray-1 p-6 text-center space-y-2 border border-outline-gray-1">
            <p class="text-xs uppercase tracking-wider font-semibold text-ink-gray-5">Your One-Time Link Code</p>
            <div class="flex items-center justify-center gap-3">
              <span class="text-3xl font-mono font-bold tracking-widest text-ink-gray-9">
                {{ linkCode }}
              </span>
              <Button variant="ghost" size="sm" title="Copy code" @click="copyCode">
                <template #prefix>
                  <Copy class="size-4" />
                </template>
              </Button>
            </div>
            <p v-if="expiresInText" class="text-xs text-ink-amber-3 font-medium">
              Code expires in {{ expiresInText }}
            </p>
          </div>

          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-ink-gray-9">How to complete linking:</h3>
            <ol class="list-decimal list-inside text-sm text-ink-gray-7 space-y-2 pl-1">
              <li>Open your Telegram app.</li>
              <li>Search for your Expense Manager Bot.</li>
              <li>
                Send the command:
                <code class="rounded bg-surface-gray-2 px-2 py-0.5 text-xs font-mono font-semibold text-ink-gray-9">
                  /link {{ linkCode }}
                </code>
              </li>
              <li>You will receive a confirmation message once linked.</li>
            </ol>
          </div>

          <div class="flex justify-center pt-2">
            <Button variant="subtle" size="sm" :loading="statusResource.loading" @click="checkStatus">
              <template #prefix>
                <RefreshCw class="size-4" />
              </template>
              Check link status
            </Button>
          </div>
        </div>
      </div>
    </ResourceState>

    <ConfirmDialog
      v-model:open="confirmUnlinkOpen"
      title="Unlink Telegram account?"
      message="Are you sure you want to unlink your Telegram account? You will no longer receive alerts or be able to log expenses via Telegram."
      confirm-label="Unlink"
      :loading="unlinking"
      @confirm="confirmUnlink"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, call, createResource } from 'frappe-ui'
import ResourceState from '@/components/ResourceState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const statusResource = createResource({
  url: 'expense_manager.api.telegram.get_link_status',
  method: 'GET',
  auto: true,
})

const isLinked = computed(() => Boolean(statusResource.data?.linked))

const generating = ref(false)
const linkCode = ref('')
const expiresInText = ref('')

async function generateCode() {
  generating.value = true
  try {
    const res = await call('expense_manager.api.telegram.generate_link_code')
    if (res && res.token) {
      linkCode.value = res.token
      expiresInText.value = res.expires_in_minutes ? `${res.expires_in_minutes} minutes` : '10 minutes'
    } else if (res && res.message) {
      alert(res.message)
    }
  } catch (e) {
    alert(e.message || 'Failed to generate code')
  } finally {
    generating.value = false
  }
}

function copyCode() {
  if (!linkCode.value) return
  navigator.clipboard.writeText(linkCode.value)
  alert('Code copied to clipboard!')
}

function checkStatus() {
  statusResource.reload()
}

const confirmUnlinkOpen = ref(false)
const unlinking = ref(false)

async function confirmUnlink() {
  unlinking.value = true
  try {
    const res = await call('expense_manager.api.telegram.unlink')
    if (res && res.success) {
      linkCode.value = ''
      statusResource.reload()
    }
  } catch (e) {
    alert(e.message || 'Failed to unlink account')
  } finally {
    unlinking.value = false
    confirmUnlinkOpen.value = false
  }
}
</script>
