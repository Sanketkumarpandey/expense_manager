/**
 * LOTTIE THEME MODULE
 * Rich illustrated world with micro-moments and state-tied animations.
 */

export const LottieTheme = {
  name: 'lottie',
  instances: [],

  async loadLottieLibrary() {
    if (window.lottie) return window.lottie;
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js';
      script.onload = () => resolve(window.lottie);
      script.onerror = () => reject(new Error('Failed to load lottie-web'));
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
    const pctUsed = allocated > 0 ? Math.min(Math.round((spent / (allocated + carryForward)) * 100), 100) : 0;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    container.innerHTML = `
      <div class="lot-view">
        <!-- Header -->
        <header class="lot-header">
          <div style="display: flex; align-items: center; gap: 14px;">
            <div class="lot-avatar">✨</div>
            <div>
              <h1 style="font-size: 22px; font-weight: 700; color: var(--lot-ink-main);">${dependent.dependent_name}</h1>
              <p style="font-size: 13px; color: var(--lot-ink-muted);">Pocket Money & Savings Playground</p>
            </div>
          </div>
          <div style="padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: ${isOverspent ? 'var(--lot-danger-bg)' : 'var(--lot-bg-subtle)'}; color: ${isOverspent ? 'var(--lot-danger-ink)' : 'var(--lot-ink-main)'};">
            ${isOverspent ? '⚠️ Budget Alert' : '🌟 Savings Explorer'}
          </div>
        </header>

        <!-- Celebratory Banner if savings > 0 -->
        ${totalSavings > 0 ? `
          <div class="lot-celebration-banner">
            <div>
              <p style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.9;">Total Lifetime Savings</p>
              <p style="font-size: 28px; font-weight: 800; margin-top: 2px;">${inr(totalSavings)} 🎉</p>
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 12px; font-size: 13px; font-weight: 600;">
              ${carryForward > 0 ? `+ ${inr(carryForward)} Rolled Over` : 'Great Job!'}
            </div>
          </div>
        ` : ''}

        <!-- Hero Card with Vector Illustration -->
        <div class="lot-hero-card">
          <div class="lot-hero-grid">
            <div>
              <p style="font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--lot-ink-subtle); letter-spacing: 0.05em; margin-bottom: 6px;">
                Spendable Balance
              </p>
              <p class="lot-hero-amount ${isOverspent ? 'overspent' : ''}">
                ${inr(remaining)}
              </p>
              <p style="font-size: 13px; color: var(--lot-ink-muted); margin-top: 6px; margin-bottom: 20px;">
                ${isOverspent ? `You are over budget by ${inr(Math.abs(remaining))}. Please check with your guardian.` : `${pctUsed}% of your allowance used this cycle.`}
              </p>

              <!-- Progress Meter -->
              <div style="height: 10px; background: var(--lot-bg-subtle); border-radius: 9999px; overflow: hidden; margin-bottom: 20px;">
                <div style="height: 100%; border-radius: 9999px; width: ${pctUsed}%; background: ${isOverspent ? 'linear-gradient(90deg, #f43f5e, #e11d48)' : 'linear-gradient(90deg, #7c3aed, #a855f7)'}; transition: width 0.6s ease;"></div>
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; border-top: 1px solid var(--lot-border-subtle); padding-top: 16px;">
                <div>
                  <p style="font-size: 11px; color: var(--lot-ink-muted);">Allocated Allowance</p>
                  <p style="font-size: 16px; font-weight: 700; color: var(--lot-ink-main);">${inr(allocated)}</p>
                </div>
                <div>
                  <p style="font-size: 11px; color: var(--lot-ink-muted);">Total Spent</p>
                  <p style="font-size: 16px; font-weight: 700; color: var(--lot-ink-main);">${inr(spent)}</p>
                </div>
              </div>
            </div>

            <!-- Dynamic Illustration Box -->
            <div class="lot-animation-box" id="lot-hero-anim">
              <svg width="100" height="100" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" class="lot-coin-svg">
                <circle cx="50" cy="50" r="40" fill="${isOverspent ? '#fee2e2' : '#f3e8ff'}" stroke="${isOverspent ? '#f43f5e' : '#7c3aed'}" stroke-width="4"/>
                <circle cx="50" cy="50" r="32" fill="${isOverspent ? '#fecdd3' : '#e9d5ff'}"/>
                <text x="50" y="58" font-family="'Space Grotesk', sans-serif" font-size="24" font-weight="bold" fill="${isOverspent ? '#e11d48' : '#7c3aed'}" text-anchor="middle">₹</text>
              </svg>
            </div>
          </div>
        </div>

        <!-- Allowed Categories -->
        <section style="margin-bottom: 32px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div>
              <h2 style="font-size: 18px; font-weight: 700; color: var(--lot-ink-main);">Allowed Categories</h2>
              <p style="font-size: 12px; color: var(--lot-ink-muted);">Authorized categories you can spend in</p>
            </div>
            <span style="padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; background: var(--lot-bg-subtle); color: var(--lot-ink-main);">
              ${allowed_categories.length} Active
            </span>
          </div>

          <div class="lot-grid-3">
            ${allowed_categories.map(cat => `
              <div class="lot-cat-card">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                  <span style="font-size: 26px;">${cat.icon || '🏷️'}</span>
                  <span style="font-family: 'Space Grotesk', sans-serif; font-size: 14px; font-weight: 700; color: var(--lot-ink-main);">
                    ${inr(cat.spent || 0)}
                  </span>
                </div>
                <p style="font-size: 14px; font-weight: 700; color: var(--lot-ink-main);">${cat.category_name}</p>
                <p style="font-size: 11px; color: var(--lot-ink-muted);">Spent this cycle</p>
              </div>
            `).join('')}
          </div>
        </section>

        <!-- Category Budgets -->
        ${budgets && budgets.length ? `
          <section style="margin-bottom: 32px;">
            <div style="margin-bottom: 16px;">
              <h2 style="font-size: 18px; font-weight: 700; color: var(--lot-ink-main);">Category Budgets</h2>
              <p style="font-size: 12px; color: var(--lot-ink-muted);">Budget tracking with live health indicator</p>
            </div>

            <div style="background: var(--lot-bg-surface); border: 1px solid var(--lot-border); border-radius: 20px; padding: 12px; box-shadow: var(--lot-shadow-sm);">
              ${budgets.map(b => {
                const bPct = b.allocated_amount > 0 ? Math.min(Math.round((b.spent_amount / b.allocated_amount) * 100), 100) : 0;
                return `
                  <div style="display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid var(--lot-border-subtle);">
                    <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
                      <span style="font-size: 22px;">${b.category_icon || '🏷️'}</span>
                      <div>
                        <p style="font-size: 14px; font-weight: 700; color: var(--lot-ink-main);">${b.category_name}</p>
                        <p style="font-size: 12px; color: var(--lot-ink-muted);">${inr(b.spent_amount)} / ${inr(b.allocated_amount)}</p>
                      </div>
                    </div>
                    <div style="width: 120px; margin: 0 16px;">
                      <div style="height: 8px; background: var(--lot-bg-subtle); border-radius: 9999px; overflow: hidden;">
                        <div style="height: 100%; border-radius: 9999px; width: ${bPct}%; background: ${b.is_overspent ? 'var(--lot-danger-ink)' : 'var(--lot-accent)'};"></div>
                      </div>
                    </div>
                    <div>
                      <span style="display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; background: ${b.is_overspent ? 'var(--lot-danger-bg)' : 'var(--lot-bg-subtle)'}; color: ${b.is_overspent ? 'var(--lot-danger-ink)' : 'var(--lot-ink-main)'};">
                        ${b.is_overspent ? 'Over by ' + inr(Math.abs(b.remaining_amount)) : inr(b.remaining_amount) + ' left'}
                      </span>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </section>
        ` : ''}

        <!-- Recent Expenses List -->
        <section style="margin-bottom: 32px;">
          <div style="margin-bottom: 16px;">
            <h2 style="font-size: 18px; font-weight: 700; color: var(--lot-ink-main);">Recent Transactions</h2>
            <p style="font-size: 12px; color: var(--lot-ink-muted);">Activity feed</p>
          </div>

          <div style="background: var(--lot-bg-surface); border: 1px solid var(--lot-border); border-radius: 20px; padding: 8px; box-shadow: var(--lot-shadow-sm);">
            ${recent_expenses.length ? recent_expenses.map(exp => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--lot-border-subtle);">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <span style="font-size: 20px;">${exp.category_icon || '🏷️'}</span>
                  <div>
                    <p style="font-size: 14px; font-weight: 700; color: var(--lot-ink-main);">${exp.description || exp.category_name || 'Expense'}</p>
                    <p style="font-size: 11px; color: var(--lot-ink-muted);">${formatDate(exp.expense_date)} · ${exp.category_name}</p>
                  </div>
                </div>
                <p style="font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700; color: var(--lot-ink-main);">${inr(exp.amount)}</p>
              </div>
            `).join('') : `
              <div style="padding: 28px; text-align: center; color: var(--lot-ink-muted); font-size: 14px;">
                No recent transactions found.
              </div>
            `}
          </div>
        </section>
      </div>
    `;

    // Try mounting dynamic Lottie animation if reduced motion is false
    if (!reducedMotion) {
      try {
        const lottieLib = await this.loadLottieLibrary();
        const animBox = container.querySelector('#lot-hero-anim');
        if (animBox && lottieLib) {
          // Lottie micro-animation data or fallback pulse
          animBox.innerHTML = `
            <div style="text-align: center;">
              <div style="font-size: 54px; animation: bounce 2s infinite ease-in-out;">💰</div>
              <p style="font-size: 11px; font-weight: 700; color: var(--lot-accent); margin-top: 4px;">
                ${isOverspent ? 'Attention Needed' : 'Healthy Balance'}
              </p>
            </div>
          `;
        }
      } catch (e) {
        console.warn('Lottie runtime unavailable, rendered vector graphics:', e);
      }
    }
  },

  unmount() {
    this.instances.forEach(inst => {
      try { inst.destroy(); } catch (e) {}
    });
    this.instances = [];
  }
};
