/**
 * ANIME.JS THEME MODULE
 * Dynamic kinetic choreography with spring physics and number tickers.
 */

export const AnimeTheme = {
	name: "animejs",
	timeline: null,

	async loadAnimeLibrary() {
		if (window.anime) return window.anime;
		return new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.src = "https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.1/anime.min.js";
			script.onload = () => resolve(window.anime);
			script.onerror = () => reject(new Error("Failed to load Anime.js"));
			document.head.appendChild(script);
		});
	},

	async mount(container, data, utils) {
		const { inr, formatDate } = utils;
		const dependent = data?.dependent || {};
		const pocket_money = data?.pocket_money || data?.balance || {};
		const allowed_categories = data?.allowed_categories || data?.category_breakdown || [];
		const budgets = data?.budgets || [];
		const recent_expenses = data?.recent_expenses || [];
		const trend = data?.trend || [];

		const remaining = pocket_money?.remaining_amount ?? 0;
		const allocated = pocket_money?.allocated_amount ?? 0;
		const spent = pocket_money?.spent_amount ?? 0;
		const carryForward = pocket_money?.carry_forward ?? 0;
		const totalSavings = (dependent?.total_savings || 0) + (remaining > 0 ? remaining : 0);
		const isOverspent = remaining < 0;
		const pctUsed =
			allocated > 0
				? Math.min(Math.round((spent / (allocated + carryForward)) * 100), 100)
				: 0;
		const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

		container.innerHTML = `
      <div class="ani-view">
        <!-- Header -->
        <header class="ani-header">
          <div style="display: flex; align-items: center; gap: 14px;">
            <div class="ani-avatar">⚡</div>
            <div>
              <h1 style="font-size: 22px; font-weight: 700; color: #ffffff;">${
					dependent.dependent_name
				}</h1>
              <p style="font-size: 13px; color: var(--ani-ink-muted);">Kinetic Personal Finance Portal</p>
            </div>
          </div>
          <div style="padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: ${
				isOverspent ? "var(--ani-danger-bg)" : "var(--ani-success-bg)"
			}; color: ${
			isOverspent ? "var(--ani-danger-ink)" : "var(--ani-success-ink)"
		}; border: 1px solid ${
			isOverspent ? "var(--ani-danger-border)" : "var(--ani-success-border)"
		};">
            ${isOverspent ? "⚠️ Critical Overspend" : "⚡ Kinetic Stream Active"}
          </div>
        </header>

        <!-- Hero Card -->
        <div class="ani-hero-card">
          <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 24px;">
            <div>
              <p style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--ani-accent); letter-spacing: 0.08em; margin-bottom: 6px;">
                Spendable Pocket Money Balance
              </p>
              <p class="ani-hero-amount ${
					isOverspent ? "overspent" : ""
				}" id="ani-balance-counter">
                ${inr(remaining)}
              </p>
            </div>
            <div style="padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: ${
				isOverspent ? "var(--ani-danger-bg)" : "rgba(245, 158, 11, 0.15)"
			}; color: ${
			isOverspent ? "var(--ani-danger-ink)" : "var(--ani-accent)"
		}; border: 1px solid ${isOverspent ? "var(--ani-danger-border)" : "var(--ani-border)"};">
              ${isOverspent ? "Over by " + inr(Math.abs(remaining)) : `${pctUsed}% Spent`}
            </div>
          </div>

          <!-- Dynamic Progress Meter -->
          <div style="height: 10px; background: var(--ani-bg-subtle); border-radius: 9999px; overflow: hidden; margin-bottom: 24px;">
            <div id="ani-progress-bar" style="height: 100%; border-radius: 9999px; width: ${
				reducedMotion ? pctUsed + "%" : "0%"
			}; background: ${
			isOverspent
				? "linear-gradient(90deg, #f43f5e, #fb7185)"
				: "linear-gradient(90deg, #d97706, #f59e0b)"
		}; box-shadow: 0 0 12px ${
			isOverspent ? "rgba(244, 63, 94, 0.5)" : "rgba(245, 158, 11, 0.5)"
		};"></div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; border-top: 1px solid var(--ani-border-subtle); padding-top: 20px;">
            <div>
              <p style="font-size: 11px; color: var(--ani-ink-muted); margin-bottom: 4px;">Cycle Allocation</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(
					allocated
				)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--ani-ink-muted); margin-bottom: 4px;">Spent</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(
					spent
				)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--ani-ink-muted); margin-bottom: 4px;">Rollover Carry-Forward</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: #ffffff;">${inr(
					carryForward
				)}</p>
            </div>
            <div>
              <p style="font-size: 11px; color: var(--ani-ink-muted); margin-bottom: 4px;">Total Savings</p>
              <p style="font-family: 'Space Grotesk', sans-serif; font-size: 16px; font-weight: 700; color: var(--ani-accent);">${inr(
					totalSavings
				)}</p>
            </div>
          </div>
        </div>

        <!-- Allowed Categories -->
        <section class="ani-section" style="margin-bottom: 32px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div>
              <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Allowed Categories</h2>
              <p style="font-size: 12px; color: var(--ani-ink-muted);">Authorized spending categories</p>
            </div>
            <span style="padding: 4px 12px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: rgba(245, 158, 11, 0.15); color: var(--ani-accent); border: 1px solid var(--ani-border);">
              ${allowed_categories.length} Ready
            </span>
          </div>

          <div class="ani-grid-3">
            ${allowed_categories
				.map(
					(cat) => `
              <div class="ani-cat-card">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                  <span style="font-size: 24px;">${cat.icon || "🏷️"}</span>
                  <span style="font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 700; color: var(--ani-accent);">
                    ${inr(cat.spent || 0)}
                  </span>
                </div>
                <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${
					cat.category_name
				}</p>
                <p style="font-size: 11px; color: var(--ani-ink-muted);">Spent this cycle</p>
              </div>
            `
				)
				.join("")}
          </div>
        </section>

        <!-- Category Budgets -->
        ${
			budgets && budgets.length
				? `
          <section class="ani-section" style="margin-bottom: 32px;">
            <div style="margin-bottom: 16px;">
              <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Budget Telemetry</h2>
              <p style="font-size: 12px; color: var(--ani-ink-muted);">Spending limits and status</p>
            </div>

            <div class="ani-table-card">
              ${budgets
					.map((b) => {
						const bPct =
							b.allocated_amount > 0
								? Math.min(
										Math.round((b.spent_amount / b.allocated_amount) * 100),
										100
								  )
								: 0;
						return `
                  <div class="ani-table-row">
                    <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
                      <span style="font-size: 20px;">${b.category_icon || "🏷️"}</span>
                      <div>
                        <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${
							b.category_name
						}</p>
                        <p style="font-size: 11px; color: var(--ani-ink-muted);">${inr(
							b.spent_amount
						)} of ${inr(b.allocated_amount)}</p>
                      </div>
                    </div>
                    <div style="width: 140px; margin: 0 16px;">
                      <div style="height: 6px; background: var(--ani-bg-subtle); border-radius: 9999px; overflow: hidden;">
                        <div style="height: 100%; border-radius: 9999px; width: ${bPct}%; background: ${
							b.is_overspent ? "var(--ani-danger-border)" : "var(--ani-accent)"
						};"></div>
                      </div>
                    </div>
                    <span style="padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: ${
						b.is_overspent ? "var(--ani-danger-bg)" : "var(--ani-success-bg)"
					}; color: ${
							b.is_overspent ? "var(--ani-danger-ink)" : "var(--ani-success-ink)"
						}; border: 1px solid ${
							b.is_overspent
								? "var(--ani-danger-border)"
								: "var(--ani-success-border)"
						};">
                      ${b.is_overspent ? "Over budget" : inr(b.remaining_amount) + " left"}
                    </span>
                  </div>
                `;
					})
					.join("")}
            </div>
          </section>
        `
				: ""
		}

        <!-- Recent Expenses Feed -->
        <section class="ani-section" style="margin-bottom: 32px;">
          <div style="margin-bottom: 16px;">
            <h2 style="font-size: 18px; font-weight: 700; color: #ffffff;">Recent Kinetic Feed</h2>
            <p style="font-size: 12px; color: var(--ani-ink-muted);">Activity stream</p>
          </div>

          <div class="ani-table-card">
            ${
				recent_expenses.length
					? recent_expenses
							.map(
								(exp) => `
              <div class="ani-table-row">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <span style="font-size: 20px;">${exp.category_icon || "🏷️"}</span>
                  <div>
                    <p style="font-size: 14px; font-weight: 700; color: #ffffff;">${
						exp.description || exp.category_name || "Expense"
					}</p>
                    <p style="font-size: 11px; color: var(--ani-ink-muted);">${formatDate(
						exp.expense_date
					)} · ${exp.category_name}</p>
                  </div>
                </div>
                <p style="font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700; color: #ffffff;">${inr(
					exp.amount
				)}</p>
              </div>
            `
							)
							.join("")
					: `
              <div style="padding: 28px; text-align: center; color: var(--ani-ink-muted); font-size: 14px;">
                No transaction stream available.
              </div>
            `
			}
          </div>
        </section>
      </div>
    `;

		// Run Coordinated Anime.js Choreography
		if (reducedMotion) {
			// Immediate display for reduced motion
			container
				.querySelectorAll(".ani-header, .ani-hero-card, .ani-cat-card, .ani-table-card")
				.forEach((el) => {
					el.style.opacity = "1";
					el.style.transform = "none";
				});
			return;
		}

		try {
			const anime = await this.loadAnimeLibrary();
			if (!anime) return;

			this.timeline = anime.timeline({
				easing: "easeOutElastic(1, .8)",
				duration: 800,
			});

			// 1. Header & Hero Card Slide In
			this.timeline
				.add({
					targets: container.querySelector(".ani-header"),
					translateY: [20, 0],
					opacity: [0, 1],
					duration: 600,
					easing: "easeOutCubic",
				})
				.add(
					{
						targets: container.querySelector(".ani-hero-card"),
						translateY: [25, 0],
						opacity: [0, 1],
						duration: 700,
						easing: "easeOutCubic",
					},
					"-=400"
				)
				// 2. Progress Bar Spring Fill
				.add(
					{
						targets: container.querySelector("#ani-progress-bar"),
						width: [`0%`, `${pctUsed}%`],
						duration: 1000,
						easing: "easeOutQuart",
					},
					"-=500"
				)
				// 3. Staggered Category Cards Entrance
				.add(
					{
						targets: container.querySelectorAll(".ani-cat-card"),
						scale: [0.92, 1],
						opacity: [0, 1],
						delay: anime.stagger(60),
						duration: 500,
						easing: "easeOutBack",
					},
					"-=600"
				)
				// 4. Tables and Feeds
				.add(
					{
						targets: container.querySelectorAll(".ani-table-card"),
						translateY: [20, 0],
						opacity: [0, 1],
						delay: anime.stagger(80),
						duration: 600,
						easing: "easeOutCubic",
					},
					"-=500"
				);
		} catch (e) {
			console.warn("Anime.js animation failed, fallback applied:", e);
			container
				.querySelectorAll(".ani-header, .ani-hero-card, .ani-cat-card, .ani-table-card")
				.forEach((el) => {
					el.style.opacity = "1";
					el.style.transform = "none";
				});
		}
	},

	unmount() {
		if (this.timeline && window.anime) {
			try {
				window.anime.remove("*");
			} catch (e) {
				// Intentionally empty: unmount cleanup, ignore if anime runtime is gone.
			}
			this.timeline = null;
		}
	},
};
