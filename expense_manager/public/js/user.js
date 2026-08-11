frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.doc.name !== frappe.session.user) return;

		frm.add_custom_button("Link Telegram", () => {
			frappe.call({
				method: "expense_manager.api.telegram.generate_link_code",
				callback: (r) => {
					if (!r.message) return;

					frappe.msgprint({
						title: "Link Telegram",
						message: `Send this to the bot:<br><b>/link ${r.message.token}</b><br><br>Expires at ${r.message.expires_at}.`,
					});
				},
			});
		});
	},
});
