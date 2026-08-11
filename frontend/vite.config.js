import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";
import { fileURLToPath, URL } from "node:url";
import frappeui from "frappe-ui/vite";

const webServerPort = process.env.FRAPPE_WEB_SERVER_PORT || 8000;

export default defineConfig({
	plugins: [
		frappeui({
			frontendRoute: "/expense_manager",
			frappeProxy: {
				source: "^/(desk|app|login|api|assets|files|private|dependent)",
			},
		}),
		vue(),
	],
	resolve: {
		alias: {
			"@": fileURLToPath(new URL("./src", import.meta.url)),
		},
	},
	optimizeDeps: {
		exclude: ["frappe-ui"],
		include: ["feather-icons", "socket.io-client", "tippy.js"],
	},
});
