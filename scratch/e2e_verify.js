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
    // Find the row containing `rowText` and click its button with `title`.
    async function clickRowButton(rowText, title) {
      return evalCode(`
        (() => {
          const rows = [...document.querySelectorAll('div[class*="py-3"]')];
          const row = rows.find(r => (r.innerText || '').includes(${JSON.stringify(rowText)}));
          if (!row) return false;
          const btn = row.querySelector('button[title=' + ${JSON.stringify(JSON.stringify(title))} + ']');
          if (!btn) return false;
          btn.click();
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
    await waitForText('E2E Cats X')
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

    const billsApi = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: 'gfk1vrc59s' }, false)
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
      category: 'gfksgn6gdl', amount: 200, expense_date: '2026-08-05',
    })
    const depFoodName = depFood && depFood.message && depFood.message.name
    report('Seeded household Food expense (₹200)', Boolean(depFoodName), depFoodName || JSON.stringify(depFood && depFood.message))

    const depAlex = await apiCall('expense_manager.api.expenses.create_expense', {
      category: 'gfksgn6gdl', amount: 300, expense_date: '2026-08-05', dependent: 'ulk6jte33q',
    })
    const depAlexName = depAlex && depAlex.message && depAlex.message.name
    report('Seeded dependent Food expense (₹300, Alex)', Boolean(depAlexName), depAlexName || JSON.stringify(depAlex && depAlex.message))

    // Remount the budgets page so usage is recomputed from the DB.
    await navigate('/dashboard')
    await navigate('/budgets')
    await waitForText('New budget')
    await sleep(800)

    const depUsage = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: 'gfksgn6gdl', dependent: 'ulk6jte33q' }, false)
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

    const householdUsage = await apiCall('expense_manager.api.budgets.get_budget_usage', { category: 'gfksgn6gdl' }, false)
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
      category: 'gfkgsa0jbt', amount: 300, expense_date: '2026-08-05',
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

    const ALEX_ID = 'ulk6jte33q'
    const FOOD_ID = 'gfksgn6gdl'

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
    const billsBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: 'gfk1vrc59s' }, false)
    for (const b of (billsBudgets && billsBudgets.message) || []) {
      const r = await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: '' })
      cleanups.push([`Bills budget ${b.name}`, Boolean(r && r.message && r.message.success !== false)])
    }
    const depFoodBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: 'gfksgn6gdl', dependent: 'ulk6jte33q' }, false)
    for (const b of (depFoodBudgets && depFoodBudgets.message) || []) {
      const r = await apiCall('expense_manager.api.budgets.delete_budget', { budget: b.name, dependent: 'ulk6jte33q' })
      cleanups.push([`Alex Food budget ${b.name}`, Boolean(r && r.message && r.message.success !== false)])
    }
    const shoppingBudgets = await apiCall('expense_manager.api.budgets.list_budgets', { category: 'gfkgsa0jbt' }, false)
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
