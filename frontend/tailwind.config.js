import frappeuiPreset from "frappe-ui/tailwind";

export default {
	presets: [frappeuiPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				surface: {
					"blue-3": "var(--surface-blue-3)",
					"blue-4": "var(--surface-blue-4)",
				},
				ink: {
					"blue-4": "var(--ink-blue-4)",
					"blue-5": "var(--ink-blue-5)",
					"red-5": "var(--ink-red-5)",
				},
			},
		},
	},
	plugins: [],
};
