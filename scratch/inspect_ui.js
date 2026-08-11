import { spawn } from "child_process";

const APP_URL = "http://expense-test.localhost:8081/";

async function sleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run() {
	const chrome = spawn("google-chrome", [
		"--headless=new",
		"--remote-debugging-port=9222",
		"--no-sandbox",
		"--disable-gpu",
		"--disable-dev-shm-usage",
		APP_URL,
	]);

	await sleep(2500);

	let ws = null;
	try {
		const listRes = await fetch("http://127.0.0.1:9222/json/list");
		const targets = await listRes.json();
		const target = targets.find((t) => t.type === "page") || targets[0];
		ws = new WebSocket(target.webSocketDebuggerUrl);

		let idCounter = 1;
		const pending = new Map();
		ws.onmessage = (event) => {
			const msg = JSON.parse(event.data);
			if (msg.id && pending.has(msg.id)) {
				const { resolve, reject } = pending.get(msg.id);
				pending.delete(msg.id);
				if (msg.error) reject(msg.error);
				else resolve(msg.result);
			}
		};
		await new Promise((resolve, reject) => {
			ws.onopen = resolve;
			ws.onerror = reject;
		});

		function send(method, params = {}) {
			return new Promise((resolve, reject) => {
				const id = idCounter++;
				pending.set(id, { resolve, reject });
				ws.send(JSON.stringify({ id, method, params }));
			});
		}

		await send("Page.enable");
		await send("DOM.enable");
		await send("Runtime.enable");
		await send("Network.enable");

		async function evalCode(expression) {
			const res = await send("Runtime.evaluate", {
				expression,
				returnByValue: true,
				awaitPromise: true,
			});
			if (res.exceptionDetails) {
				throw new Error(
					res.exceptionDetails.exception?.description ||
						res.exceptionDetails.text ||
						"JS Evaluation Exception"
				);
			}
			return res.result ? res.result.value : null;
		}

		async function waitFor(expression, timeout = 10000, step = 350) {
			const deadline = Date.now() + timeout;
			while (Date.now() < deadline) {
				const ok = await evalCode(`Boolean(${expression})`);
				if (ok) return true;
				await sleep(step);
			}
			return false;
		}

		async function apiCall(method, params = {}, isPost = true) {
			return evalCode(`
        (async () => {
          const qs = new URLSearchParams(${JSON.stringify(params)});
          const url = '/api/method/' + ${JSON.stringify(
				method
			)} + (${isPost} ? '' : '?' + qs.toString());
          const res = await fetch(url, {
            method: ${isPost ? "'POST'" : "'GET'"},
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: ${isPost} ? qs.toString() : undefined,
          });
          return await res.json();
        })()
      `);
		}

		async function navigate(path) {
			await evalCode(
				`window.history.pushState({}, '', ${JSON.stringify(
					path
				)}); window.dispatchEvent(new PopStateEvent('popstate'));`
			);
			await sleep(1200);
		}

		const bootOk = await waitFor(
			`document.querySelector('#app') && document.querySelector('#app').childElementCount > 0`,
			8000
		);
		console.log("SPA mounted:", bootOk);

		const loginRes = await apiCall("login", { usr: "Administrator", pwd: "admin" }, true);
		console.log("login:", JSON.stringify(loginRes?.message || loginRes));
		await evalCode(`window.user = "Administrator"`);

		// ----- Seed: create a dependent with allocation + expenses to inspect displays
		const dep = await apiCall("expense_manager.api.dependents.create_dependent", {
			dependent_name: "Inspect Jr",
			relationship: "Son",
			default_monthly_allowance: 0,
			allow_carry_forward: 1,
		});
		let depId = dep && dep.message && dep.message.name;
		console.log("seeded dependent:", depId);

		const alloc = await apiCall("expense_manager.api.pocket_money.create_allocation", {
			dependent: depId,
			allocated_amount: 1500,
			allocation_period: "Monthly",
			carry_forward_amount: 0,
		});
		console.log("allocation:", JSON.stringify(alloc?.message));

		const d = new Date();
		const p = (n) => String(n).padStart(2, "0");
		const todayIso = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;

		const exp1 = await apiCall("expense_manager.api.expenses.create_expense", {
			category: "gfksgn6gdl",
			amount: 400,
			expense_date: todayIso,
			dependent: depId,
		});
		const exp2 = await apiCall("expense_manager.api.expenses.create_expense", {
			category: "gfkgsa0jbt",
			amount: 100,
			expense_date: todayIso,
			dependent: depId,
		});
		console.log("expenses:", Boolean(exp1?.message?.name), Boolean(exp2?.message?.name));

		const bal = await apiCall(
			"expense_manager.api.pocket_money.get_balance",
			{ dependent: depId },
			false
		);
		console.log("balance:", JSON.stringify(bal?.message));

		const pmSummary = await apiCall(
			"expense_manager.api.reports.get_pocket_money_summary",
			{},
			false
		);
		console.log("pm summary:", JSON.stringify(pmSummary?.message));

		const depList = await apiCall(
			"expense_manager.api.dependents.list_dependents",
			{ active_only: 1 },
			false
		);
		console.log(
			"list_dependents fields:",
			JSON.stringify(
				depList?.message?.map((d) => ({
					name: d.name,
					name2: d.dependent_name,
					total_savings: d.total_savings,
				}))
			)
		);

		// ----- Dependents page DOM
		await navigate("/dependents");
		await waitFor(`document.body.innerText.includes('Inspect Jr')`, 10000);
		const depCard = await evalCode(`
      (() => {
        const card = [...document.querySelectorAll('div[class*="bg-surface-white"]')].find(el =>
          (el.innerText || '').includes('Inspect Jr'));
        return card ? (card.innerText || '') : '(no card)';
      })()
    `);
		console.log("--- DEPENDENTS CARD TEXT ---");
		console.log(depCard);

		// ----- Reports page DOM
		await navigate("/reports");
		await waitFor(`document.body.innerText.includes('Monthly spending trend')`, 12000);
		const reportsText = await evalCode(`document.body.innerText`);
		console.log("--- REPORTS PAGE (first 3000 chars) ---");
		console.log(reportsText.slice(0, 3000));

		// cleanup
		await apiCall("expense_manager.api.expenses.delete_expense", {
			expense: exp1?.message?.name,
		});
		await apiCall("expense_manager.api.expenses.delete_expense", {
			expense: exp2?.message?.name,
		});
		const allocs = await apiCall(
			"expense_manager.api.pocket_money.list_allocations",
			{ dependent: depId, active_only: 0 },
			false
		);
		for (const a of allocs?.message || [])
			await apiCall("expense_manager.api.pocket_money.delete_allocation", {
				allocation: a.name,
			});
		await apiCall("expense_manager.api.dependents.delete_dependent", { dependent: depId });
		console.log("cleaned up");

		ws.close();
	} catch (err) {
		console.error("INSPECT FAILED:", err.message || err);
	} finally {
		try {
			chrome.kill();
		} catch (e) {
			/* noop */
		}
	}
}

run();
