/**
 * THEME SHELL & LIFECYCLE MANAGER
 * Coordinates dynamic theme loading, mounting, teardown, and switcher interactions.
 */

import { StandardTheme } from '../themes/standard/standard.js';
import { LottieTheme } from '../themes/lottie/lottie.js';
import { ThreejsTheme } from '../themes/threejs/threejs.js';
import { AnimeTheme } from '../themes/anime/anime.js';

export const ThemeShell = {
  currentTheme: null,
  activeThemeModule: null,
  portalData: null,

  themes: {
    standard: StandardTheme,
    lottie: LottieTheme,
    threejs: ThreejsTheme,
    animejs: AnimeTheme,
  },

  utils: {
    inr: (val) => {
      return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(val || 0);
    },

    formatDate: (val) => {
      if (!val) return '';
      return new Date(val).toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    },
  },

  normalizeData(raw) {
    const d = raw || {};
    const pocket_money = d.pocket_money || d.balance || {};
    const allowed_categories = d.allowed_categories || d.category_breakdown || [];
    const budgets = d.budgets || [];
    const recent_expenses = d.recent_expenses || [];
    const trend = d.trend || [];
    const dependent = d.dependent || {};

    return {
      ...d,
      dependent,
      pocket_money,
      balance: pocket_money,
      allowed_categories,
      category_breakdown: allowed_categories,
      budgets,
      recent_expenses,
      trend,
    };
  },

  init(portalData) {
    this.portalData = this.normalizeData(portalData);

    // Determine initial theme from localStorage or default to 'standard'
    const savedTheme = localStorage.getItem('expenso_dependent_theme') || 'standard';
    const initialTheme = this.themes[savedTheme] ? savedTheme : 'standard';

    this.bindSwitcher();
    this.setTheme(initialTheme);
  },

  bindSwitcher() {
    const switcher = document.querySelector('.theme-switcher-bar');
    if (!switcher) return;

    switcher.querySelectorAll('[data-set-theme]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const targetTheme = btn.getAttribute('data-set-theme');
        this.setTheme(targetTheme);
      });
    });
  },

  async setTheme(themeName) {
    const targetModule = this.themes[themeName] || this.themes.standard;
    if (!targetModule) return;

    // 1. Unmount active theme cleanly
    if (this.activeThemeModule && this.activeThemeModule.unmount) {
      try {
        this.activeThemeModule.unmount();
      } catch (e) {
        console.warn('Error unmounting previous theme:', e);
      }
    }

    this.currentTheme = themeName;
    this.activeThemeModule = targetModule;

    // 2. Set HTML attribute and save
    document.documentElement.setAttribute('data-theme', themeName);
    localStorage.setItem('expenso_dependent_theme', themeName);

    // 3. Update Switcher active state
    document.querySelectorAll('.theme-pill-btn').forEach(btn => {
      if (btn.getAttribute('data-set-theme') === themeName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // 4. Mount new theme into view container
    const appContainer = document.querySelector('#theme-viewport');
    if (appContainer && this.portalData) {
      try {
        await targetModule.mount(appContainer, this.portalData, this.utils);
      } catch (e) {
        console.error(`Failed to mount theme [${themeName}]:`, e);
      }
    }
  }
};
