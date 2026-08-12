import { spawn } from "child_process";
import { writeFileSync } from "fs";

const APP_URL = "http://expense-test.localhost:8081/";
async function sleep(ms) {
	return new Promise((r) => setTimeout(r, ms));
}

async function run() {
	const chrome = spawn("google-chrome", [
		"--headless=new",
		"--remote-debugging-port=9222",
		"--no-sandbox",
		"--disable-gpu",
		"--disable-dev-shm-usage",
		"--window-size=1400,900",
		APP_URL,
	]);
	await sleep(2500);
	try {
		const listRes = await fetch("http://127.0.0.1:9222/json/list");
		const targets = await listRes.json();
		const target = targets.find((t) => t.type === "page") || targets[0];
		const ws = new WebSocket(target.webSocketDebuggerUrl);
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
		await send("Runtime.enable");
		await send("DOM.enable");
		async function evalCode(expression) {
			const res = await send("Runtime.evaluate", {
				expression,
				returnByValue: true,
				awaitPromise: true,
			});
			if (res.exceptionDetails) throw new Error(res.exceptionDetails.text || "EXC");
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
			return evalCode(`(async () => {
        const qs = new URLSearchParams(${JSON.stringify(params)});
        const url = '/api/method/' + ${JSON.stringify(
			method
		)} + (${isPost} ? '' : '?' + qs.toString());
        const res = await fetch(url, { method: ${
			isPost ? "'POST'" : "'GET'"
		}, headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: ${isPost} ? qs.toString() : undefined });
        return await res.json();
      })()`);
		}
		async function navigate(path) {
			await evalCode(
				`window.history.pushState({}, '', ${JSON.stringify(
					path
				)}); window.dispatchEvent(new PopStateEvent('popstate'));`
			);
			await sleep(1200);
		}

		await waitFor(
			`document.querySelector('#app') && document.querySelector('#app').childElementCount > 0`,
			8000
		);
		await apiCall("login", { usr: "Administrator", pwd: "admin" }, true);
		await evalCode(`window.user = "Administrator"`);

		// Reports page - open filters
		await navigate("/reports");
		await waitFor(`document.body.innerText.includes('Monthly spending trend')`, 12000);
		// Click the Filters button
		await evalCode(`(() => {
      const btn = [...document.querySelectorAll('button')].find(b => (b.innerText || '').includes('Filters'));
      if (!btn) return false; btn.click(); return true;
    })()`);
		await sleep(800);

		const layout = await evalCode(`(() => {
      const labels = [...document.querySelectorAll('label')].map(l => l.innerText.trim());
      const fields = [];
      document.querySelectorAll('label').forEach(lbl => {
        const wrap = lbl.closest('div');
        if (!wrap) return;
        const input = wrap.querySelector('input');
        if (!input) return;
        const r = input.getBoundingClientRect();
        fields.push({ label: lbl.innerText.trim(), placeholder: input.placeholder, height: Math.round(r.height), width: Math.round(r.width), py: input.computedStyleMap ? '' : getComputedStyle(input).padding });
      });
      const filterSection = [...document.querySelectorAll('section')].find(s => s.innerText.includes('Dependent') && s.innerText.includes('Category') && s.innerText.includes('From'));
      let sectionInfo = null;
      if (filterSection) {
        const children = [...filterSection.children].map(c => ({ tag: c.tagName, cls: c.className, text: (c.innerText||'').slice(0,30) }));
        const r = filterSection.getBoundingClientRect();
        sectionInfo = { height: Math.round(r.height), width: Math.round(r.width), children };
      }
      const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null).map(i => ({
        placeholder: i.placeholder, height: Math.round(i.getBoundingClientRect().height),
        padding: getComputedStyle(i).padding, cls: i.className
      }));
      return { fields, sectionInfo, inputs, labels };
    })()`);
		console.log("REPORTS FILTER LAYOUT:");
		console.log(JSON.stringify(layout, null, 2));

		// screenshot
		const shot = await send("Page.captureScreenshot", { format: "png" });
		if (shot && shot.data)
			writeFileSync("/tmp/opencode/reports_filters.png", Buffer.from(shot.data, "base64"));
		console.log("screenshot saved");

		ws.close();
	} catch (err) {
		console.error("FAILED:", err.message || err);
	} finally {
		try {
			chrome.kill();
		} catch (e) {}
	}
}
run();
