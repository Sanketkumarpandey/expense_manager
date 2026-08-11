/**
 * STANDARD THEME MODULE
 * Editorial, restrained typography and clean whitespace rhythm.
 */

export const StandardTheme = {
  name: 'standard',
  
  mount(container, data, utils) {
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

    container.innerHTML = `
      <div class="std-view">
        <!-- Header -->
        <header class="std-header">
          <div class="std-brand">
            <div class="std-avatar">👤</div>
            <div>
              <h1 class="std-title">${dependent.dependent_name}</h1>
              <p class="std-subtitle">Pocket Money & Personal Finance Portal · ${dependent.relationship || 'Dependent'}</p>
            </div>
          </div>
          <div class="std-hero-badge ${isOverspent ? 'danger' : 'success'}">
            <span>●</span> ${isOverspent ? 'Over Allowance' : 'Active Period'}
          </div>
        </header>

        <!-- Hero Balance Card -->
        <div class="std-hero-card">
          <div class="std-hero-top">
            <div>
              <p class="std-hero-label">Pocket Money Balance</p>
              <p class="std-hero-amount ${isOverspent ? 'overspent' : ''}">${inr(remaining)}</p>
            </div>
            <div class="std-hero-badge ${isOverspent ? 'danger' : 'success'}">
              ${isOverspent ? 'Over budget by ' + inr(Math.abs(remaining)) : inr(remaining) + ' remaining'}
            </div>
          </div>

          <div class="std-progress-track">
            <div class="std-progress-fill ${isOverspent ? 'danger' : ''}" style="width: ${pctUsed}%;"></div>
          </div>

          <div class="std-stats-grid">
            <div>
              <p class="std-stat-label">Allocated</p>
              <p class="std-stat-val">${inr(allocated)}</p>
            </div>
            <div>
              <p class="std-stat-label">Spent This Period</p>
              <p class="std-stat-val">${inr(spent)} (${pctUsed}%)</p>
            </div>
            <div>
              <p class="std-stat-label">Rollover Carry-Forward</p>
              <p class="std-stat-val">${inr(carryForward)}</p>
            </div>
            <div>
              <p class="std-stat-label">Total Lifetime Savings</p>
              <p class="std-stat-val" style="color: var(--std-accent-ink);">${inr(totalSavings)}</p>
            </div>
          </div>
        </div>

        <!-- Allowed Categories -->
        <section class="std-section">
          <div class="std-section-header">
            <div>
              <h2 class="std-section-title">Allowed Categories</h2>
              <p class="std-section-sub">Categories authorized by your guardian</p>
            </div>
            <span class="std-hero-badge success">${allowed_categories.length} Allowed</span>
          </div>

          <div class="std-grid-3">
            ${allowed_categories.map(cat => `
              <div class="std-cat-card">
                <div class="std-cat-top">
                  <div class="std-cat-icon">${cat.icon || '🏷️'}</div>
                  <span class="std-cat-spend">${inr(cat.spent || 0)}</span>
                </div>
                <p class="std-cat-name">${cat.category_name}</p>
                <p class="std-section-sub">Spent this period</p>
              </div>
            `).join('')}
          </div>
        </section>

        <!-- Category Budgets -->
        ${budgets && budgets.length ? `
          <section class="std-section">
            <div class="std-section-header">
              <div>
                <h2 class="std-section-title">Category Budgets</h2>
                <p class="std-section-sub">Spending vs allocated budget limits</p>
              </div>
            </div>

            <div class="std-table-card">
              ${budgets.map(b => {
                const bPct = b.allocated_amount > 0 ? Math.min(Math.round((b.spent_amount / b.allocated_amount) * 100), 100) : 0;
                return `
                  <div class="std-table-row">
                    <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
                      <div class="std-cat-icon">${b.category_icon || '🏷️'}</div>
                      <div style="min-width: 0;">
                        <p class="std-cat-name">${b.category_name}</p>
                        <p class="std-section-sub">${inr(b.spent_amount)} of ${inr(b.allocated_amount)}</p>
                      </div>
                    </div>
                    <div style="width: 140px; margin: 0 16px;">
                      <div class="std-progress-track" style="margin-bottom: 0;">
                        <div class="std-progress-fill ${b.is_overspent ? 'danger' : ''}" style="width: ${bPct}%;"></div>
                      </div>
                    </div>
                    <div style="text-align: right;">
                      <span class="std-hero-badge ${b.is_overspent ? 'danger' : 'success'}">
                        ${b.is_overspent ? 'Over budget' : inr(b.remaining_amount) + ' left'}
                      </span>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </section>
        ` : ''}

        <!-- 6-Month Spending Trend -->
        ${trend && trend.length ? `
          <section class="std-section">
            <div class="std-section-header">
              <div>
                <h2 class="std-section-title">6-Month Spending Trend</h2>
                <p class="std-section-sub">Historical monthly spending</p>
              </div>
            </div>
            <div class="std-table-card" style="padding: 24px;">
              <div style="display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; height: 160px; padding-top: 20px;">
                ${(() => {
                  const maxSpend = Math.max(...trend.map(t => t.total_amount || 0), 1);
                  return trend.map(t => {
                    const h = Math.max(Math.round(((t.total_amount || 0) / maxSpend) * 120), 4);
                    return `
                      <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px;">
                        <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--std-ink-muted);">
                          ${(t.total_amount || 0) > 0 ? inr(t.total_amount) : '₹0'}
                        </span>
                        <div style="width: 100%; max-width: 48px; height: ${h}px; background: var(--std-accent); border-radius: 6px 6px 0 0; opacity: 0.85;"></div>
                        <span style="font-size: 11px; font-weight: 600; color: var(--std-ink-subtle);">${t.month}</span>
                      </div>
                    `;
                  }).join('');
                })()}
              </div>
            </div>
          </section>
        ` : ''}

        <!-- Recent Expenses -->
        <section class="std-section">
          <div class="std-section-header">
            <div>
              <h2 class="std-section-title">Recent Expenses</h2>
              <p class="std-section-sub">Your latest transactions</p>
            </div>
            <span class="std-section-sub">${recent_expenses.length} Records</span>
          </div>

          <div class="std-table-card">
            ${recent_expenses.length ? recent_expenses.map(exp => `
              <div class="std-table-row">
                <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
                  <div class="std-cat-icon">${exp.category_icon || '🏷️'}</div>
                  <div style="min-width: 0;">
                    <p class="std-cat-name">${exp.description || exp.category_name || 'Expense'}</p>
                    <p class="std-section-sub">${formatDate(exp.expense_date)} · ${exp.category_name}</p>
                  </div>
                </div>
                <p class="std-stat-val">${inr(exp.amount)}</p>
              </div>
            `).join('') : `
              <div style="padding: 32px; text-align: center; color: var(--std-ink-muted); font-size: 14px;">
                No recent expenses logged yet.
              </div>
            `}
          </div>
        </section>
      </div>
    `;
  },

  unmount() {
    // Standard theme uses pure CSS/DOM without external event loops.
  }
};
