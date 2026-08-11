import { spawn } from 'child_process'

// The test-site dev stack (bench :8001 pinned to expense-test.localhost via
// `bench --site expense-test.localhost serve --port 8001`, vite :8081 via
// FRAPPE_WEB_SERVER_PORT=8001) — see bench-root scripts/run-e2e.sh.
// default_site stays expense.local permanently (Part 0 / Phase 33).
const APP_URL = 'http://expense-test.localhost:8081/'
const ADMIN_USER = 'Administrator'
const ADMIN_PWD = 'admin'
const DEPENDENT_NAME = 'Alex Junior'

let passed = 0
let failed = 0

function report(label, ok, detail = '') {
  if (ok) {
    passed++
    console.log(`  ✓ ${label}${detail ? ` — ${detail}` : ''}`)
  } else {
    failed++
    console.error(`  ✗ ${label}${detail ? ` — ${detail}` : ''}`)
  }
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// Local-timezone ISO date. Pocket-money allocations are dated `today`, and
// _calculate_spent_amount filters to the allocation window, so expenses
// created for that scenario must be dated on/after today, not a hardcoded past
// date (which silently leaves spent_amount at 0).
const todayIso = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

async function run() {
  console.log('Starting Headless Chrome on port 9222...')
  const chrome = spawn('google-chrome', [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    APP_URL,
  ])

  await sleep(2500)

  let ws = null
  let chromeOk = false
  try {
    const listRes = await fetch('http://127.0.0.1:9222/json/list')
    const targets = await listRes.json()
    const target = targets.find((t) => t.type === 'page') || targets[0]
    if (!target) throw new Error('No Chrome target page found')

    ws = new WebSocket(target.webSocketDebuggerUrl)

    let idCounter = 1
    const pending = new Map()
    const consoleLogs = []

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id)
        pending.delete(msg.id)
        if (msg.error) reject(msg.error)
        else resolve(msg.result)
      } else if (msg.method === 'Runtime.consoleAPICalled') {
        const type = msg.params.type
        const args = msg.params.args.map((a) => a.value || a.description).join(' ')
        if (type === 'error') {
          consoleLogs.push(args)
          console.error('[Browser Error]', args)
        }
      } else if (msg.method === 'Runtime.exceptionThrown') {
        consoleLogs.push('EXC: ' + (msg.params.exceptionDetails?.text || 'unknown'))
      }
    }

    await new Promise((resolve, reject) => {
      ws.onopen = resolve
      ws.onerror = reject
    })

    function send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = idCounter++
        pending.set(id, { resolve, reject })
        ws.send(JSON.stringify({ id, method, params }))
      })
    }

    await send('Page.enable')
    await send('DOM.enable')
    await send('Runtime.enable')
    await send('Network.enable')

    async function evalCode(expression) {
      const res = await send('Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true,
      })
      if (res.exceptionDetails) {
        throw new Error(
          (res.exceptionDetails.exception?.description ||
            res.exceptionDetails.text ||
            'JS Evaluation Exception'),
        )
      }
      return res.result ? res.result.value : null
    }

    async function waitFor(expression, timeout = 10000, step = 350) {
      const deadline = Date.now() + timeout
      while (Date.now() < deadline) {
        const ok = await evalCode(`Boolean(${expression})`)
        if (ok) return true
        await sleep(step)
      }
      return false
    }

    async function waitForText(text, timeout = 10000) {
      return waitFor(
        `document.body.innerText.includes(${JSON.stringify(text)})`,
        timeout,
      )
    }

    // Native-setter input dispatch that Vue 3 v-model reacts to.
    async function setInputValue(selectorOrPlaceholder, value) {
      return evalCode(`
        (() => {
          const input = ${typeof selectorOrPlaceholder === 'string' && selectorOrPlaceholder.startsWith('[')
            ? `document.querySelector(${JSON.stringify(selectorOrPlaceholder)})`
            : `[...document.querySelectorAll('input')].find(i => (i.placeholder || '') === ${JSON.stringify(selectorOrPlaceholder)})`
          };
          if (!input) return false;
          const proto = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
          setter.call(input, ${JSON.stringify(value)});
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        })()
      `)
    }

    // Type into a combobox input (by placeholder) and click the matching option.
    async function pickComboboxOption(placeholder, search, optionLabel) {
      const typed = await setInputValue(placeholder, search)
      if (!typed) return false
      await sleep(600)
      return evalCode(`
        (() => {
          const items = [...document.querySelectorAll('[data-slot="item"]')];
          const match = items.find(el => (el.innerText || '').includes(${JSON.stringify(optionLabel)}));
          if (!match) return false;
          match.click();
          return true;
        })()
      `)
    }

    async function clickVisibleButton(text) {
      return evalCode(`
        (() => {
          const btn = [...document.querySelectorAll('button')].find(b =>
            !b.disabled &&
            b.getBoundingClientRect().height > 0 &&
            getComputedStyle(b).display !== 'none' &&
            (b.innerText || '').trim() === ${JSON.stringify(text)}
          );
          if (!btn) return false;
          btn.click();
          return true;
        })()
      `)
    }

    // List rows (Categories/Budgets pages) are the outer <div class="...py-3">.
    // Find the row containing `rowText`, open its 3-dot menu (title="Row actions")
    // and click the menu item whose label matches `title`.
    async function clickRowButton(rowText, title) {
      const opened = await evalCode(`
        (() => {
          const rows = [...document.querySelectorAll('div[class*="py-3"]')];
          const row = rows.find(r => (r.innerText || '').includes(${JSON.stringify(rowText)}));
          if (!row) return false;
          const btn = row.querySelector('button[title="Row actions"]');
          if (!btn) return false;
          // reka-ui dropdowns open on pointerdown, so dispatch the full
          // pointer -> click sequence a real user would produce.
          const opts = { bubbles: true, cancelable: true, button: 0, ctrlKey: false };
          btn.dispatchEvent(new PointerEvent('pointerdown', opts));
          btn.dispatchEvent(new PointerEvent('pointerup', opts));
          btn.dispatchEvent(new MouseEvent('click', opts));
          return true;
        })()
      `)
      if (!opened) return false
      await sleep(450)
      return evalCode(`
        (() => {
          const items = [...document.querySelectorAll('[role="menuitem"]')];
          const item = items.find(b => (b.innerText || '').trim() === ${JSON.stringify(title)});
          if (!item) return false;
          item.click();
          return true;
        })()
      `)
    }

    async function rowExists(rowText) {
      return evalCode(`
        (() => {
          const rows = [...document.querySelectorAll('div[class*="py-3"]')];
          return rows.some(r => (r.innerText || '').includes(${JSON.stringify(rowText)}));
        })()
      `)
    }

    async function bodyText() {
      return evalCode(`document.body.innerText`)
    }

    async function apiCall(method, params = {}, isPost = true) {
      return evalCode(`
        (async () => {
          const qs = new URLSearchParams(${JSON.stringify(params)});
          const url = '/api/method/' + ${JSON.stringify(method)} + (${isPost} ? '' : '?' + qs.toString());
          const res = await fetch(url, {
            method: ${isPost ? "'POST'" : "'GET'"},
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: ${isPost} ? qs.toString() : undefined,
          });
          return await res.json();
        })()
      `)
    }

    async function navigate(path) {
      await evalCode(
        `window.history.pushState({}, '', ${JSON.stringify(path)}); window.dispatchEvent(new PopStateEvent('popstate'));`,
      )
      await sleep(1200)
    }

    // Find a dependent's card (by dependent name) and click its
    // "Allowed categories" header to expand the toggle section.
    async function expandAllowedCategories(depName) {
      return evalCode(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            el.getBoundingClientRect().height > 0 &&
            (el.innerText || '').includes(${JSON.stringify(depName)}) &&
            (el.innerText || '').includes('Allowed categories'));
          if (!card) return false;
          const header = [...card.querySelectorAll('button')].find(b =>
            (b.innerText || '').includes('Allowed categories'));
          if (!header) return false;
          header.click();
          return true;
        })()
      `)
    }

    // Click the frappe-ui Switch (role=switch) for a category inside a
    // dependent's card. The switch row is the nearest rounded-md div.
    async function clickCategorySwitch(depName, categoryName) {
      return evalCode(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            el.getBoundingClientRect().height > 0 &&
            (el.innerText || '').includes(${JSON.stringify(depName)}));
          if (!card) return false;
          const sw = [...card.querySelectorAll('button[role="switch"]')].find(b => {
            const row = b.closest('div[class*="rounded-md"]');
            return row && (row.innerText || '').includes(${JSON.stringify(categoryName)});
          });
          if (!sw) return false;
          sw.click();
          return true;
        })()
      `)
    }

    // Wait until a category switch in the card reaches the given state.
    async function waitForSwitchState(depName, categoryName, state, timeout = 12000) {
      return waitFor(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            (el.innerText || '').includes(${JSON.stringify(depName)}));
          if (!card) return false;
          const sw = [...card.querySelectorAll('button[role="switch"]')].find(b => {
            const row = b.closest('div[class*="rounded-md"]');
            return row && (row.innerText || '').includes(${JSON.stringify(categoryName)});
          });
          return Boolean(sw && sw.getAttribute('data-state') === ${JSON.stringify(state)});
        })()
      `, timeout)
    }

    // Count how many switches exist in a dependent's card (0 if collapsed).
    async function switchCountInCard(depName) {
      return evalCode(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            (el.innerText || '').includes(${JSON.stringify(depName)}));
          if (!card) return 0;
          return card.querySelectorAll('button[role="switch"]').length;
        })()
      `)
    }

    // Poll a predicate until it returns true — used to wait for the SERVER
    // to reflect a toggle (the switch flips optimistically, so UI state alone
    // is not proof the allow-list update finished).
    async function waitForApi(fn, timeout = 20000, step = 400) {
      const deadline = Date.now() + timeout
      while (Date.now() < deadline) {
        try {
          if (await fn()) return true
        } catch (e) {
          /* keep polling */
        }
        await sleep(step)
      }
      return false
    }

    // ---------------------------------------------------------------
    console.log('\n--- DEV SERVER BOOT + LOGIN ---')

    const bootOk = await waitFor(`document.querySelector('#app') && document.querySelector('#app').childElementCount > 0`, 8000)
    report('Dev server SPA mounted (#app has children)', bootOk)

    const loginRes = await apiCall('login', { usr: ADMIN_USER, pwd: ADMIN_PWD }, true)
    report(
      'Login via /api/method/login (dev proxy)',
      loginRes && loginRes.message !== 'Invalid login credentials',
      JSON.stringify(loginRes?.message || loginRes?.full_name || ''),
    )
    if (!loginRes || loginRes.message === 'Invalid login credentials') {
      throw new Error('Login failed — aborting')
    }

    // Dev server does not serve frappe's boot script (window.user comes from
    // expense_manager/www/expense_manager.py in prod), so mirror what boot
    // provides before driving the SPA.
    await evalCode(`window.user = ${JSON.stringify(ADMIN_USER)}`)

    const catListRes = await apiCall('expense_manager.api.categories.list_categories', { active_only: 0 }, false)
    const allCats = (catListRes && catListRes.message) || []
    const BILLS_ID = (allCats.find(c => c.category_name === 'Bills') || {}).name
    const FOOD_ID = (allCats.find(c => c.category_name === 'Food') || {}).name
    const SHOPPING_ID = (allCats.find(c => c.category_name === 'Shopping') || {}).name

    const depListRes = await apiCall('expense_manager.api.dependents.list_dependents', { active_only: 0 }, false)
    const allDeps = (depListRes && depListRes.message) || []
    let ALEX_ID = (allDeps.find(d => d.dependent_name === DEPENDENT_NAME) || {}).name
    if (!ALEX_ID) {
      const alexCreate = await apiCall('expense_manager.api.dependents.create_dependent', {
        dependent_name: DEPENDENT_NAME, relationship: 'Son', default_monthly_allowance: 2000, telegram_user_id: '99881122'
      })
      ALEX_ID = alexCreate && alexCreate.message && alexCreate.message.name
    }

    // Clean up any stale test records from prior runs to ensure a clean baseline
    const initStaleBudgets = (await apiCall('expense_manager.api.budgets.list_budgets', { active_only: 0 }, false))?.message || []
    for (const b of initStaleBudgets) {
      if (['Bills', 'Shopping'].includes(b.category_name) || (b.category_name === 'Food' && b.dependent)) {
        await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: b.dependent || '' })
      }
    }
    const initStaleAllocs = (await apiCall('expense_manager.api.pocket_money.list_allocations', { dependent: ALEX_ID, active_only: 0 }, false))?.message || []
    for (const a of initStaleAllocs) {
      await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: a.name })
    }

    // Clean up stale test dependents from prior interrupted runs
    const existingInitDeps = (await apiCall('expense_manager.api.dependents.list_dependents', { active_only: 0 }, false))?.message || []
    for (const d of existingInitDeps) {
      if (['E2E Pocket Jr', 'E2E Savings Jr', 'E2E Portal Dependent'].includes(d.dependent_name)) {
        await apiCall('expense_manager.api.dependents.delete_dependent', { dependent: d.name })
      }
    }

    // Ensure fixture Food household budget (₹5,000) exists
    const foodHouseholdBudgets = (await apiCall('expense_manager.api.budgets.list_budgets', { category: FOOD_ID, dependent: '' }, false))?.message || []
    if (!foodHouseholdBudgets.length && FOOD_ID) {
      await apiCall('expense_manager.api.budgets.create_budget', {
        category: FOOD_ID, allocated_amount: 5000, period: 'Monthly'
      })
    }

    // Seed Bills expense to guarantee "in-use" delete blocking in Scenario 1
    if (BILLS_ID) {
      await apiCall('expense_manager.api.expenses.create_expense', {
        category: BILLS_ID, amount: 250, expense_date: todayIso()
      })
    }

    await navigate('/categories')
    await waitForText('New category')
    report('Categories page rendered', await waitForText('New category'))

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 1: Category create → edit → archive → restore → delete rules ---')

    await clickVisibleButton('New category')
    await sleep(600)
    await setInputValue('e.g. Groceries', 'E2E Cats')
    await setInputValue('Pick an emoji, e.g. 🛒', '🐱')
    await clickVisibleButton('Save')
    report('Category created via dialog', await waitForText('Category "E2E Cats" created.'))
    report('New category row visible with icon', await rowExists('E2E Cats') && (await bodyText()).includes('🐱'))

    await clickRowButton('E2E Cats', 'Edit')
    await sleep(600)
    await setInputValue('e.g. Groceries', 'E2E Cats X')
    await setInputValue('Pick an emoji, e.g. 🛒', '🐯')
    await clickVisibleButton('Save')
    report('Category renamed via edit dialog', await waitForText('Category updated.'))
    report('Edited row reflects new name + icon', await rowExists('E2E Cats X') && (await bodyText()).includes('🐯'))

    await clickRowButton('E2E Cats X', 'Archive')
    report('Category archived', await waitForText('Category "E2E Cats X" archived.'))
    await clickVisibleButton('All')
    await waitForText('Archived')
    report('Archived category visible in "All" view with badge', await (async () => {
      const hasRow = await rowExists('E2E Cats X')
      const hasBadge = (await bodyText()).includes('Archived')
      return hasRow && hasBadge
    })())

    await clickRowButton('E2E Cats X', 'Restore')
    report('Category restored', await waitForText('Category "E2E Cats X" restored.'))
    await clickVisibleButton('Active')
    await sleep(1000)
    report('Restored category visible again in "Active" view', await rowExists('E2E Cats X'))

    // Delete is blocked while the category is in use (Bills has expenses).
    await clickRowButton('Bills', 'Delete')
    await sleep(600)
    await clickVisibleButton('Delete')
    report(
      'Delete blocked for category in use by expenses',
      await waitForText('Cannot delete category because it is used by one or more expenses.'),
    )
    report('Bills category still present after blocked delete', await rowExists('Bills'))

    // The test category is unused, so it can be deleted.
    await clickRowButton('E2E Cats X', 'Delete')
    await sleep(600)
    await clickVisibleButton('Delete')
    report('Unused category deleted successfully', await waitForText('Category "E2E Cats X" deleted.'))
    report('Deleted category gone from list', !(await rowExists('E2E Cats X')))

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 2: Household budget shows pre-existing spend on creation ---')

    await navigate('/budgets')
    await waitForText('New budget')

    await clickVisibleButton('New budget')
    await sleep(700)
    report('Budget dialog: picked category Bills', await pickComboboxOption('Select category', 'Bills', 'Bills'))
    await setInputValue('0.00', '1000')
    await clickVisibleButton('Save')
    report('Household Bills budget created', await waitForText('Budget for "Bills" created.'))

    const billsUsage = await waitForText('₹250 of ₹1,000 spent')
    report('Budget card shows pre-existing ₹250 spend of ₹1,000', billsUsage)
    report('Budget card shows 25% used', await waitForText('25%'))
    const billsText = await bodyText()
    report('Budget not flagged at 25% (< 90% threshold)', !billsText.includes('Over budget'))

    const billsApi = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: BILLS_ID }, false)
    const billsUsageData = billsApi && billsApi.message
    report(
      'API get_budget_usage(Bills) → spent 250 / allocated 1000',
      Boolean(
        billsUsageData &&
          billsUsageData.success !== false &&
          billsUsageData.spent_amount === 250 &&
          billsUsageData.allocated_amount === 1000,
      ),
      JSON.stringify(billsApi?.message || billsApi),
    )

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 3: Dependent-scoped budget on same category, independently tracked ---')

    await clickVisibleButton('New budget')
    await sleep(700)
    report('Budget dialog: picked category Food', await pickComboboxOption('Select category', 'Food', 'Food'))
    report('Budget dialog: picked dependent Alex Junior', await pickComboboxOption('Select dependent (optional)', 'Alex', DEPENDENT_NAME))
    await setInputValue('0.00', '2000')
    await clickVisibleButton('Save')
    report('Dependent-scoped Food budget created (allowed alongside household budget)', await waitForText('Budget for "Food" created.'))
    report('Dependent scope badge shown on card', await waitForText(DEPENDENT_NAME))

    // Seed expenses: household first, then dependent — the dependent expense
    // must update only the dependent budget, not the household one.
    const depFood = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 200, expense_date: todayIso(),
    })
    const depFoodName = depFood && depFood.message && depFood.message.name
    report('Seeded household Food expense (₹200)', Boolean(depFoodName), depFoodName || JSON.stringify(depFood && depFood.message))

    const depAlex = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 300, expense_date: todayIso(), dependent: ALEX_ID,
    })
    const depAlexName = depAlex && depAlex.message && depAlex.message.name
    report('Seeded dependent Food expense (₹300, Alex)', Boolean(depAlexName), depAlexName || JSON.stringify(depAlex && depAlex.message))

    // Remount the budgets page so usage is recomputed from the DB.
    await navigate('/dashboard')
    await navigate('/budgets')
    await waitForText('New budget')
    await sleep(800)

    const depUsage = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: FOOD_ID, dependent: ALEX_ID }, false)
    const depUsageData = depUsage && depUsage.message
    report(
      'API get_budget_usage(Food, Alex) → spent 300 / allocated 2000',
      Boolean(
        depUsageData &&
          depUsageData.success !== false &&
          depUsageData.spent_amount === 300 &&
          depUsageData.allocated_amount === 2000,
      ),
      JSON.stringify(depUsage?.message || depUsage),
    )
    report('Dependent Food budget card shows ₹300 of ₹2,000', await waitForText('₹300 of ₹2,000 spent'))

    const householdUsage = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: FOOD_ID }, false)
    const householdUsageData = householdUsage && householdUsage.message
    report(
      'API get_budget_usage(Food, household) → spent 200 / allocated 5000 (dependent expense did NOT leak in)',
      Boolean(
        householdUsageData &&
          householdUsageData.success !== false &&
          householdUsageData.spent_amount === 200 &&
          householdUsageData.allocated_amount === 5000,
      ),
      JSON.stringify(householdUsage?.message || householdUsage),
    )
    report('Household Food budget card shows ₹200 of ₹5,000', await waitForText('₹200 of ₹5,000 spent'))

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 4: Overspent budget renders red styling ---')

    await clickVisibleButton('New budget')
    await sleep(700)
    report('Budget dialog: picked category Shopping', await pickComboboxOption('Select category', 'Shopping', 'Shopping'))
    await setInputValue('0.00', '200')
    await clickVisibleButton('Save')
    report('Household Shopping budget created (₹200)', await waitForText('Budget for "Shopping" created.'))

    const shoppingExp = await apiCall('expense_manager.api.expenses.create_expense', {
      category: SHOPPING_ID, amount: 300, expense_date: todayIso(),
    })
    const shoppingExpName = shoppingExp && shoppingExp.message && shoppingExp.message.name
    report('Seeded Shopping expense (₹300 → over budget)', Boolean(shoppingExpName), shoppingExpName || JSON.stringify(shoppingExp && shoppingExp.message))
    report('Expense API returned overspend warning', Boolean(shoppingExp && shoppingExp.message && shoppingExp.message.warning), shoppingExp?.message?.warning || '')

    await navigate('/dashboard')
    await navigate('/budgets')
    await waitForText('New budget')
    await sleep(800)

    report('Shopping card shows "Over budget" badge', await waitForText('Over budget'))
    report('Shopping card shows overspend detail', await waitForText('over by ₹100'))
    const progressBarCount = await evalCode(`
      (() => {
        const bars = [...document.querySelectorAll('div[class*="bg-surface-blue-3"], div[class*="bg-surface-red-6"]')];
        return bars.filter(el => el.offsetParent !== null && el.getBoundingClientRect().height > 0).length;
      })()
    `)
    report('Overspent budget renders dark progress bar', progressBarCount >= 1, `progress bars: ${progressBarCount}`)

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 5: Per-dependent allowed-categories toggles + server-side block ---')

    // Force a deterministic starting state: empty allowed_categories child
    // table (= "all active categories allowed"). The fixture dependent may
    // carry an explicit allow-list from earlier runs.
    const alexPre = await apiCall('expense_manager.api.dependents.get_dependent', { dependent: ALEX_ID }, false)
    for (const row of (alexPre && alexPre.message && alexPre.message.allowed_categories) || []) {
      await apiCall('expense_manager.api.dependents.remove_allowed_category', { dependent: ALEX_ID, category: row.category })
    }
    const alexPreIds = ((await apiCall('expense_manager.api.dependents.list_allowed_categories', { dependent: ALEX_ID, active_only: 1 }, false)) || {}).message
    report(
      'Alex reset to all-allowed default (empty child table)',
      Array.isArray(alexPreIds) && alexPreIds.length >= 2 && alexPreIds.map((c) => c.name).includes(FOOD_ID),
      `allowed: ${Array.isArray(alexPreIds) ? alexPreIds.map((c) => c.name).join(', ') : '(none)'}`,
    )

    await navigate('/dependents')
    await waitForText('New dependent')
    report('Dependents page rendered', await waitForText(DEPENDENT_NAME))

    report('Allowed-categories section collapsed initially', (await switchCountInCard(DEPENDENT_NAME)) === 0)
    report('Expanded "Allowed categories" for Alex', await expandAllowedCategories(DEPENDENT_NAME))

    const switchesVisible = await waitFor(
      `(() => {
        const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
          (el.innerText || '').includes(${JSON.stringify(DEPENDENT_NAME)}));
        if (!card) return false;
        return card.querySelectorAll('button[role="switch"]').length > 0;
      })()`,
      12000,
    )
    report('Allowed-categories toggles rendered (one per active category)', switchesVisible)
    report('Food toggle defaults to checked (all allowed)', await waitForSwitchState(DEPENDENT_NAME, 'Food', 'checked'))

    // Turn Food OFF — first restriction, so the section seeds the allow-list
    // with every other active category (empty list means "all allowed").
    report('Clicked Food toggle OFF', await clickCategorySwitch(DEPENDENT_NAME, 'Food'))

    const serverFoodOff = await waitForApi(async () => {
      const res = await apiCall('expense_manager.api.dependents.list_allowed_categories', { dependent: ALEX_ID, active_only: 1 }, false)
      const ids = ((res && res.message) || []).map((c) => c.name)
      // The seed adds every category EXCEPT Food; wait for the full list so
      // the toggle isn't caught mid-seed (the switch flips optimistically).
      return ids.length === alexPreIds.length - 1 && !ids.includes(FOOD_ID)
    })
    report('Server: Food removed from Alex allowed list after seed', serverFoodOff)

    report('Food toggle now unchecked', await waitForSwitchState(DEPENDENT_NAME, 'Food', 'unchecked'))

    // The money shot: a direct REST call must NOT bypass the toggle.
    const blockedExpense = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 50, expense_date: '2026-08-05', dependent: ALEX_ID,
    })
    const blockedOk =
      blockedExpense &&
      blockedExpense.message &&
      blockedExpense.message.success === false &&
      String(blockedExpense.message.message || '').toLowerCase().includes('not allowed')
    report('Direct API expense in a toggled-off category is BLOCKED', Boolean(blockedOk), JSON.stringify(blockedExpense?.message || blockedExpense))

    // Wait for the toggle to be re-enabled (busy guard clears once the reload
    // after the seed finishes) before clicking it again.
    const foodEnabled = await waitFor(`
      (() => {
        const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
          (el.innerText || '').includes(${JSON.stringify(DEPENDENT_NAME)}));
        if (!card) return false;
        const sw = [...card.querySelectorAll('button[role="switch"]')].find(b => {
          const row = b.closest('div[class*="rounded-md"]');
          return row && (row.innerText || '').includes('Food');
        });
        return Boolean(sw && !sw.disabled);
      })()
    `, 15000)

    // Re-enable Food through the UI.
    report('Clicked Food toggle back ON', await clickCategorySwitch(DEPENDENT_NAME, 'Food'))

    const serverFoodOn = await waitForApi(async () => {
      const res = await apiCall('expense_manager.api.dependents.list_allowed_categories', { dependent: ALEX_ID, active_only: 1 }, false)
      const ids = ((res && res.message) || []).map((c) => c.name)
      return ids.includes(FOOD_ID)
    })
    report('Server: Food restored to Alex allowed list', serverFoodOn)

    report('Food toggle checked again', await waitForSwitchState(DEPENDENT_NAME, 'Food', 'checked'))

    const reAllowedExpense = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 120, expense_date: '2026-08-05', dependent: ALEX_ID,
    })
    const reAllowedName = reAllowedExpense && reAllowedExpense.message && reAllowedExpense.message.name
    report('Direct API expense allowed again after re-enable', Boolean(reAllowedName), reAllowedName || JSON.stringify(reAllowedExpense?.message))

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 6: Pocket money allocation lifecycle + rollover ---')

    const pmDep = await apiCall('expense_manager.api.dependents.create_dependent', {
      dependent_name: 'E2E Pocket Jr', relationship: 'Son', default_monthly_allowance: 0, allow_carry_forward: 1,
    })
    let pmDepId = pmDep && pmDep.message && pmDep.message.name
    if (!pmDepId) {
      const deps = await apiCall('expense_manager.api.dependents.list_dependents', { active_only: 0 }, false)
      const existing = ((deps && deps.message) || []).find((d) => d.dependent_name === 'E2E Pocket Jr')
      pmDepId = existing && existing.name
    }
    report('Created dedicated dependent for pocket money lifecycle', Boolean(pmDepId), pmDepId || JSON.stringify(pmDep?.message))

    // Clear leftovers from any failed prior run so assertions are deterministic.
    const staleExpenses = await apiCall('expense_manager.api.expenses.list_expenses', { dependent: pmDepId }, false)
    for (const e of (staleExpenses && staleExpenses.message) || []) {
      await apiCall('expense_manager.api.expenses.delete_expense', { expense: e.name })
    }
    const staleAllocs = await apiCall('expense_manager.api.pocket_money.list_allocations', { dependent: pmDepId, active_only: 0 }, false)
    for (const a of (staleAllocs && staleAllocs.message) || []) {
      await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: a.name })
    }

    const alloc = await apiCall('expense_manager.api.pocket_money.create_allocation', {
      dependent: pmDepId, allocated_amount: 1000, allocation_period: 'Monthly', carry_forward_amount: 0,
    })
    const allocId = alloc && alloc.message && alloc.message.name
    report('Created Monthly ₹1,000 pocket money allocation', Boolean(allocId && alloc.message.total_available_amount === 1000), allocId || JSON.stringify(alloc?.message))

    const bal0 = await apiCall('expense_manager.api.pocket_money.get_balance', { dependent: pmDepId }, false)
    const bal0Data = bal0 && bal0.message
    report(
      'get_balance → allocated 1000, spent 0, remaining 1000',
      Boolean(bal0Data && bal0Data.success !== false && bal0Data.allocated_amount === 1000 && bal0Data.spent_amount === 0 && bal0Data.remaining_amount === 1000),
      JSON.stringify(bal0Data || bal0),
    )

    const pmExpense = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 300, expense_date: todayIso(), dependent: pmDepId,
    })
    const pmExpenseName = pmExpense && pmExpense.message && pmExpense.message.name
    report('Dependent spent ₹300 via Food expense', Boolean(pmExpenseName), pmExpenseName || JSON.stringify(pmExpense?.message))

    const bal1 = await apiCall('expense_manager.api.pocket_money.get_balance', { dependent: pmDepId }, false)
    const bal1Data = bal1 && bal1.message
    report(
      'get_balance after spend → spent 300, remaining 700',
      Boolean(bal1Data && bal1Data.success !== false && bal1Data.spent_amount === 300 && bal1Data.remaining_amount === 700),
      JSON.stringify(bal1Data || bal1),
    )

    const roll = await apiCall('expense_manager.api.pocket_money.rollover_allocation', { dependent: pmDepId })
    const rollId = roll && roll.message && roll.message.name
    report('Manual rollover created a fresh zero allocation', Boolean(rollId && roll.message.allocated_amount === 0), rollId || JSON.stringify(roll?.message))

    const bal2 = await apiCall('expense_manager.api.pocket_money.get_balance', { dependent: pmDepId }, false)
    const bal2Data = bal2 && bal2.message
    report(
      'Unused ₹700 rolled into total_savings (carry-forward enabled)',
      Boolean(bal2Data && bal2Data.success !== false && bal2Data.total_savings === 700),
      `total_savings: ${bal2Data && bal2Data.total_savings}`,
    )

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 7: Dependents Total Savings + Reports charts + no-filters regression ---')

    // A deterministic dependent with a running allocation (₹1,500, ₹500 spent)
    // proves the Total Savings card shows allocation − spent, and the Reports
    // pocket-money summary + charts react to the dependent filter.
    const svDep = await apiCall('expense_manager.api.dependents.create_dependent', {
      dependent_name: 'E2E Savings Jr', relationship: 'Son', default_monthly_allowance: 1500, allow_carry_forward: 1,
    })
    let svDepId = svDep && svDep.message && svDep.message.name
    if (!svDepId) {
      const deps = await apiCall('expense_manager.api.dependents.list_dependents', { active_only: 0 }, false)
      const existing = ((deps && deps.message) || []).find((d) => d.dependent_name === 'E2E Savings Jr')
      svDepId = existing && existing.name
    }
    report('Created dedicated dependent for savings/charts checks', Boolean(svDepId), svDepId || JSON.stringify(svDep?.message))

    const svStaleExpenses = await apiCall('expense_manager.api.expenses.list_expenses', { dependent: svDepId }, false)
    for (const e of (svStaleExpenses && svStaleExpenses.message) || []) {
      await apiCall('expense_manager.api.expenses.delete_expense', { expense: e.name })
    }
    const svStaleAllocs = await apiCall('expense_manager.api.pocket_money.list_allocations', { dependent: svDepId, active_only: 0 }, false)
    for (const a of (svStaleAllocs && svStaleAllocs.message) || []) {
      await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: a.name })
    }

    const svAlloc = await apiCall('expense_manager.api.pocket_money.create_allocation', {
      dependent: svDepId, allocated_amount: 1500, allocation_period: 'Monthly', carry_forward_amount: 0,
    })
    const svAllocId = svAlloc && svAlloc.message && svAlloc.message.name
    report('Created Monthly ₹1,500 allocation for savings dependent', Boolean(svAllocId), svAllocId || JSON.stringify(svAlloc?.message))

    const alexStaleAllocs = await apiCall('expense_manager.api.pocket_money.list_allocations', { dependent: ALEX_ID, active_only: 0 }, false)
    for (const a of (alexStaleAllocs && alexStaleAllocs.message) || []) {
      await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: a.name })
    }

    // Give the fixture dependent an active allocation too, so the pocket-money
    // summary shows two rows BEFORE the dependent filter narrows it to one —
    // otherwise the "narrowed" and "all dependents after Reset" checks are
    // vacuous (Alex Junior has no active allocation by this point).
    const alexAlloc = await apiCall('expense_manager.api.pocket_money.create_allocation', {
      dependent: ALEX_ID, allocated_amount: 1000, allocation_period: 'Monthly', carry_forward_amount: 0,
    })
    const alexAllocId = alexAlloc && alexAlloc.message && alexAlloc.message.name
    report('Created Monthly ₹1,000 allocation for Alex Junior (filter contrast row)', Boolean(alexAllocId), alexAllocId || JSON.stringify(alexAlloc?.message))

    const svExp1 = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 500, expense_date: todayIso(), dependent: svDepId,
    })
    const svExp1Name = svExp1 && svExp1.message && svExp1.message.name
    report('Spent ₹500 for savings dependent today', Boolean(svExp1Name), svExp1Name || JSON.stringify(svExp1?.message))

    const svListDeps = await apiCall('expense_manager.api.dependents.list_dependents', { active_only: 0 }, false)
    const svListRow = ((svListDeps && svListDeps.message) || []).find((d) => d.name === svDepId)
    report(
      'list_dependents returns total_savings field',
      Boolean(svListRow && 'total_savings' in svListRow),
      JSON.stringify(svListRow ? { total_savings: svListRow.total_savings } : null),
    )

    const svPmSum = await apiCall('expense_manager.api.reports.get_pocket_money_summary', { dependent: svDepId }, false)
    const svPmRow = ((svPmSum && svPmSum.message) || []).find((r) => r.dependent === svDepId)
    report(
      'PM summary → spent 500, remaining 1000, savings 1000',
      Boolean(svPmRow && svPmRow.spent_amount === 500 && svPmRow.remaining_amount === 1000 && svPmRow.total_savings === 1000),
      JSON.stringify(svPmRow || svPmSum?.message || svPmSum),
    )

    // Dependents page: the Total Savings stat must show the running
    // allocation's remaining (allocation − spent), not the ₹0 ledger.
    // Leave the page first: scenario 5 leaves the app on /dependents, and a
    // same-route pushState + popstate does NOT remount the route component —
    // so without the detour the page would show stale dependents.
    await navigate('/dashboard')
    await navigate('/dependents')
    await waitForText('E2E Savings Jr')
    const svCardOk = await waitFor(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            el.getBoundingClientRect().height > 0 &&
            (el.innerText || '').includes('E2E Savings Jr') &&
            (el.innerText || '').includes('Total Savings'));
          return Boolean(card && /₹1[,.]?000/.test(card.innerText));
        })()
      `, 15000)
    let svCardText = ''
    if (!svCardOk) {
      svCardText = await evalCode(`
        (() => {
          const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
            el.getBoundingClientRect().height > 0 && (el.innerText || '').includes('E2E Savings Jr'));
          return card ? card.innerText.replace(/\\n+/g, ' | ') : 'CARD NOT FOUND';
        })()
      `)
    }
    report(
      'Dependents card shows ₹1,000 Total Savings (allocation − spent)',
      svCardOk,
      svCardText || '',
    )

    // Reports page: line chart + bar chart render; filter panel narrows the
    // pocket-money summary; per-dependent trend toggle works.
    await navigate('/reports')
    await waitForText('Monthly spending trend')

    console.log('DEBUG-REPORTS-TEXT:', JSON.stringify(await evalCode(`document.body.innerText.slice(0, 900)`)))
    console.log('DEBUG-REPORTS-HTML:', JSON.stringify(await evalCode(`document.body.querySelector('#app') ? document.body.querySelector('#app').innerHTML.slice(0, 600) : 'no #app'`)))
    console.log('DEBUG-REPORTS-URL:', JSON.stringify(await evalCode(`window.location.pathname`)))

    report('Trend line chart canvas rendered', await waitFor(`
      (() => {
        const section = [...document.querySelectorAll('div[class*="rounded-lg"]')].find(el =>
          (el.innerText || '').includes('Monthly spending trend'));
        return Boolean(section && section.querySelector('canvas'));
      })()
    `, 12000))
    report('Category breakdown bar chart canvas rendered', await waitFor(`
      (() => {
        const section = [...document.querySelectorAll('div[class*="rounded-lg"]')].find(el =>
          (el.innerText || '').includes('Category breakdown'));
        return Boolean(section && section.querySelector('canvas'));
      })()
    `, 12000))

    report(
      'Reports page has no Pocket money summary section (moved to Dependents)',
      await evalCode(`(() => !document.body.innerText.includes('Pocket money summary'))()`),
    )

    await navigate('/expenses')
    await waitForText('Bills')
    report(
      'Expenses page has responsive filter toggle',
      await evalCode(`(() => Boolean(document.querySelector('[data-testid="filter-toggle"]')))()`),
    )
    await evalCode(`document.querySelector('[data-testid="filter-toggle"]').click()`)
    await sleep(500)
    report(
      'Expenses page filter inputs (All dependents, All categories) render',
      await evalCode(`
        (() => [...document.querySelectorAll('input')].some(i =>
          ['All dependents', 'All categories'].includes(i.placeholder || '')))()
      `),
    )
    await sleep(300)

    await navigate('/budgets')
    await waitForText('New budget')
    report(
      'Budgets page has no Filters button',
      await evalCode(`
        (() => ![...document.querySelectorAll('button')].some(b =>
          (b.innerText || '').trim().startsWith('Filters')) )()
      `),
    )
    report(
      'Budgets page has no All categories/All dependents filter inputs',
      await evalCode(`
        (() => ![...document.querySelectorAll('input')].some(i =>
          ['All categories', 'All dependents'].includes(i.placeholder || '')))()
      `),
    )

    await navigate('/dashboard')
    await waitForText('Recent expenses')
    report(
      'Dashboard has no category quick-access section',
      await evalCode(`
        (() => !document.body.innerText.includes('Quick access to category expenses'))()
      `),
    )
    report(
      'Dashboard has no filter toggle',
      await evalCode(`(() => !document.querySelector('[data-testid="filter-toggle"]'))()`),
    )

    // Verify Dependents page has portal link buttons and reacts to new expense
    const svExp2 = await apiCall('expense_manager.api.expenses.create_expense', {
      category: FOOD_ID, amount: 200, expense_date: todayIso(), dependent: svDepId,
    })
    const svExp2Name = svExp2 && svExp2.message && svExp2.message.name
    report('Added ₹200 more expense for savings dependent', Boolean(svExp2Name), svExp2Name || JSON.stringify(svExp2?.message))
    await navigate('/dashboard')
    await navigate('/dependents')
    await waitForText('E2E Savings Jr')
    report(
      'Dependents card has Copy link action',
      await evalCode(`(() => [...document.querySelectorAll('button')].some(b => (b.innerText || '').includes('Copy link')))()`),
    )
    report(
      'Dependents card Spent updated to ₹700 (Spent: ₹700 (47%))',
      await waitFor(`
        (() => {
          const text = document.body.innerText || '';
          return text.includes('Spent: ₹700') || text.includes('₹700');
        })()
      `, 12000),
    )

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 8: Quick Expense Hover Card (dashboard) ---')

    // The Quick Add Expense hover card is a click-to-open popover with a
    // single input. Submit goes through the existing whitelisted endpoint;
    // the popover must close + toast on success, or show an inline error and
    // stay open on failure. Outcome is branched because the test site's AI
    // config decides success vs. the friendly configuration error.
    await navigate('/dashboard')
    await waitForText('Recent expenses')

    report(
      'Quick Add Expense trigger button visible',
      await waitFor(`
        (() => {
          const btn = document.querySelector('[data-testid="quick-add-trigger"]');
          return Boolean(btn && btn.getBoundingClientRect().height > 0);
        })()
      `, 10000),
    )
    report(
      'Clicked Quick Add Expense trigger',
      await evalCode(`
        (() => {
          const btn = document.querySelector('[data-testid="quick-add-trigger"]');
          if (!btn) return false;
          btn.click();
          return true;
        })()
      `),
    )
    await sleep(500)
    report(
      'Popover opens with input present',
      await waitFor(`
        (() => {
          const input = document.querySelector('[data-testid="quick-add-input"]');
          return Boolean(input && input.getBoundingClientRect().height > 0);
        })()
      `, 8000),
    )
    report(
      'Input is autofocused on open',
      await evalCode(`
        (() => document.activeElement &&
             document.activeElement.getAttribute('data-testid') === 'quick-add-input')()
      `),
    )
    report('Cancel closes popover', await clickVisibleButton('Cancel'))
    await sleep(400)
    report(
      'Popover closed after Cancel',
      await evalCode(`(() => !document.querySelector('[data-testid="quick-add-input"]'))()`),
    )

    // Reopen, type a natural-language expense, submit via Enter.
    await evalCode(`
      (() => {
        document.querySelector('[data-testid="quick-add-trigger"]').click();
        return true;
      })()
    `)
    await sleep(400)
    report(
      'Typed expense text into popover input',
      await setInputValue('[data-testid="quick-add-input"]', '100 on groceries'),
    )
    await sleep(200)
    report(
      'Submitted via Enter key',
      await evalCode(`
        (() => {
          const input = document.querySelector('[data-testid="quick-add-input"]');
          input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
          return true;
        })()
      `),
    )

    // Resolve as soon as either outcome lands (inline error → stayed open,
    // or popover closed → success), so the success toast is still visible.
    const qaResolved = await waitFor(`
      (() => {
        const errorEl = document.querySelector('[data-testid="quick-add-error"]');
        const inputEl = document.querySelector('[data-testid="quick-add-input"]');
        return Boolean(errorEl) || !Boolean(inputEl);
      })()
    `, 15000)
    report('Quick-add submit resolved (error or success)', qaResolved)
    const qaErrorSeen = await evalCode(`
      (() => Boolean(document.querySelector('[data-testid="quick-add-error"]')))()
    `)
    if (qaErrorSeen) {
      const qaErrText = await evalCode(`
        (() => {
          const el = document.querySelector('[data-testid="quick-add-error"]');
          return el ? el.innerText.trim() : '';
        })()
      `)
      report('Inline error shown on failure', qaErrText.length > 0, qaErrText)
      report(
        'Friendly configuration message surfaced when AI keys absent',
        qaErrText.includes("isn't set up yet"),
        qaErrText,
      )
      report(
        'Popover stays open on failure',
        await evalCode(`(() => Boolean(document.querySelector('[data-testid="quick-add-input"]')))()`),
      )
      report(
        'Input retains typed text on failure',
        await evalCode(`
          (() => document.querySelector('[data-testid="quick-add-input"]')?.value === '100 on groceries')()
        `),
      )
      report('Closed popover after failed submit', await clickVisibleButton('Cancel'))
    } else {
      // Success path: popover closes, toast fires, dashboard reloads.
      await sleep(300)
      report(
        'Popover closed on success',
        await evalCode(`(() => !document.querySelector('[data-testid="quick-add-input"]'))()`),
      )
      report(
        'Success toast appeared',
        await waitFor(`document.body.innerText.includes('Added ')`, 10000),
      )
      await sleep(1200)
      report(
        'Recent expenses updated after quick add',
        await waitFor(`document.body.innerText.includes('groceries')`, 12000),
      )
      // Best-effort cleanup of the parsed expense (mock parse sets the
      // description to the typed text).
      const qaList = await apiCall('expense_manager.api.expenses.list_expenses', {}, false)
      const qaMine = ((qaList && qaList.message) || []).find((e) => e.description === '100 on groceries')
      if (qaMine) {
        await apiCall('expense_manager.api.expenses.delete_expense', { expense: qaMine.name })
      }
      report('Cleaned up quick-added expense', Boolean(qaMine), qaMine ? qaMine.name : 'none found')
    }

    // ---------------------------------------------------------------
    console.log('\n--- SCENARIO 9: Dependent Portal & Theme Switcher (/dependent/<token>) ---')

    // 1. Fetch Alex's access_token and check portal data API
    const alexDepDoc = await apiCall('expense_manager.api.dependents.get_dependent', { dependent: ALEX_ID }, false)
    const alexToken = alexDepDoc && alexDepDoc.message && (alexDepDoc.message.access_token || alexDepDoc.message.name)
    report('Retrieved dependent access token', Boolean(alexToken), alexToken)

    const portalApi = await apiCall('expense_manager.api.dependents.get_portal_data', { token: alexToken }, false)
    report(
      'Portal API returns scoped dependent data',
      Boolean(portalApi && portalApi.message && portalApi.message.success && portalApi.message.dependent.dependent_name === DEPENDENT_NAME),
    )

    // 2. Test HTML serving for both /dependent and /dependent/<token>
    const portalHttpRes = await evalCode(`
      (async () => {
        const r1 = await fetch('/dependent');
        const t1 = await r1.text();
        const r2 = await fetch('/dependent/' + ${JSON.stringify(alexToken)});
        const t2 = await r2.text();
        return {
          r1Status: r1.status,
          hasEmptyText: t1.includes('Dependent Link Required'),
          r2Status: r2.status,
          hasDepName: t2.includes(${JSON.stringify(DEPENDENT_NAME)}),
          hasBalance: t2.includes('Pocket Money Balance'),
          hasCategories: t2.includes('Allowed Categories'),
          hasThemes: t2.includes('data-set-theme="lottie"') && t2.includes('data-set-theme="threejs"') && t2.includes('data-set-theme="animejs"'),
        };
      })()
    `)
    report('Empty /dependent returns status 200 with "Dependent Link Required"', Boolean(portalHttpRes && portalHttpRes.r1Status === 200 && portalHttpRes.hasEmptyText))
    report('Token route /dependent/<token> renders portal with dependent name', Boolean(portalHttpRes && portalHttpRes.r2Status === 200 && portalHttpRes.hasDepName))
    report('Portal contains hero balance and allowed categories sections', Boolean(portalHttpRes && portalHttpRes.hasBalance && portalHttpRes.hasCategories))
    report('Portal contains theme switcher buttons for all 4 themes', Boolean(portalHttpRes && portalHttpRes.hasThemes))

    // ---------------------------------------------------------------
    console.log('\n--- CLEANUP ---')

    // Remove seeded expenses so fixture budget stays consistent (refreshed in shell after).
    const cleanups = []
    // Order matters: delete the dependent Food expense first, then the household
    // one. A guardian (household) budget counts every expense for the category,
    // so refreshing it while the dependent expense still exists would inflate
    // the fixture Food budget's spent_amount.
    for (const [label, name] of [
      ['dependent Food expense', depAlexName],
      ['household Food expense', depFoodName],
      ['Shopping expense', shoppingExpName],
    ]) {
      if (name) {
        const r = await apiCall('expense_manager.api.expenses.delete_expense', { expense: name })
        cleanups.push([label, Boolean(r && r.message && r.message.success !== false)])
      }
    }

    // Resolve and delete the budgets created during this run.
    const billsBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: BILLS_ID }, false)
    for (const b of (billsBudgets && billsBudgets.message) || []) {
      const r = await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: '' })
      cleanups.push([`Bills budget ${b.name}`, Boolean(r && r.message && r.message.success !== false)])
    }
    const depFoodBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: FOOD_ID, dependent: ALEX_ID }, false)
    for (const b of (depFoodBudgets && depFoodBudgets.message) || []) {
      const r = await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: ALEX_ID })
      cleanups.push([`Alex Food budget ${b.name}`, Boolean(r && r.message && r.message.success !== false)])
    }
    const shoppingBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: SHOPPING_ID }, false)
    for (const b of (shoppingBudgets && shoppingBudgets.message) || []) {
      const r = await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: '' })
      cleanups.push([`Shopping budget ${b.name}`, Boolean(r && r.message && r.message.success !== false)])
    }

    // Phase 5 cleanup:
    // - Alex's re-allowed Food expense.
    if (reAllowedName) {
      const r = await apiCall('expense_manager.api.expenses.delete_expense', { expense: reAllowedName })
      cleanups.push([`Alex Food expense ${reAllowedName}`, Boolean(r && r.message && r.message.success !== false)])
    }

    // - If the "blocked" expense was somehow created (regression), delete it
    //   so a failed block can never accumulate leaked expenses in fixture
    //   budgets across runs.
    const blockedName = blockedExpense && blockedExpense.message && blockedExpense.message.name
    if (blockedName) {
      const r = await apiCall('expense_manager.api.expenses.delete_expense', { expense: blockedName })
      cleanups.push([`leaked blocked expense ${blockedName}`, Boolean(r && r.message && r.message.success !== false)])
    }

    // - Reset Alex's allowed-categories child table back to empty (= all
    //   allowed), so the fixture dependent keeps its default behaviour.
    const alexDoc = await apiCall('expense_manager.api.dependents.get_dependent', { dependent: ALEX_ID }, false)
    for (const row of (alexDoc && alexDoc.message && alexDoc.message.allowed_categories) || []) {
      const r = await apiCall('expense_manager.api.dependents.remove_allowed_category', { dependent: ALEX_ID, category: row.category })
      cleanups.push([`Alex allowed category ${row.category}`, Boolean(r && r.message && r.message.success !== false)])
    }
    const alexReset = await apiCall('expense_manager.api.dependents.list_allowed_categories', { dependent: ALEX_ID, active_only: 1 }, false)
    cleanups.push([
      'Alex allowed list reset to all categories (empty child table)',
      Array.isArray(alexReset && alexReset.message) && (alexReset.message).length >= 1,
    ])

    // - Pocket money lifecycle dependent: expense, both allocations, dependent.
    if (pmExpenseName) {
      const r = await apiCall('expense_manager.api.expenses.delete_expense', { expense: pmExpenseName })
      cleanups.push([`PM lifecycle expense ${pmExpenseName}`, Boolean(r && r.message && r.message.success !== false)])
    }
    for (const aId of [rollId, allocId]) {
      if (aId) {
        const r = await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: aId })
        cleanups.push([`PM allocation ${aId}`, Boolean(r && r.message && r.message.success !== false)])
      }
    }
    if (pmDepId) {
      const r = await apiCall('expense_manager.api.dependents.delete_dependent', { dependent: pmDepId })
      cleanups.push([`PM lifecycle dependent ${pmDepId}`, Boolean(r && r.message && r.message.success !== false)])
    }

    // - Scenario 7: savings-dependent expenses, allocation, dependent.
    for (const svName of [svExp2Name, svExp1Name]) {
      if (svName) {
        const r = await apiCall('expense_manager.api.expenses.delete_expense', { expense: svName })
        cleanups.push([`Savings expense ${svName}`, Boolean(r && r.message && r.message.success !== false)])
      }
    }
    if (svAllocId) {
      const r = await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: svAllocId })
      cleanups.push([`Savings allocation ${svAllocId}`, Boolean(r && r.message && r.message.success !== false)])
    }
    if (alexAllocId) {
      const r = await apiCall('expense_manager.api.pocket_money.delete_allocation', { allocation: alexAllocId })
      cleanups.push([`Alex allocation ${alexAllocId}`, Boolean(r && r.message && r.message.success !== false)])
    }
    if (svDepId) {
      const r = await apiCall('expense_manager.api.dependents.delete_dependent', { dependent: svDepId })
      cleanups.push([`Savings dependent ${svDepId}`, Boolean(r && r.message && r.message.success !== false)])
    }

    for (const [label, ok] of cleanups) {
      report(`Cleanup: ${label}`, Boolean(ok))
    }

    // ---------------------------------------------------------------
    console.log('\n--- CONSOLE ERROR CHECK ---')
    if (consoleLogs.length === 0) {
      report('No browser console errors detected', true)
    } else {
      report('No browser console errors detected', false, consoleLogs.join(' | '))
    }

    ws.close()
    chromeOk = true
  } catch (err) {
    console.error('\nE2E failed with exception:', err.message || err)
  } finally {
    try {
      chrome.kill()
    } catch (e) {
      /* noop */
    }
  }

  console.log(`\n========== RESULT: ${passed} passed, ${failed} failed ==========`)
  if (!chromeOk) process.exitCode = 1
  if (failed > 0) process.exitCode = 1
}

run()
