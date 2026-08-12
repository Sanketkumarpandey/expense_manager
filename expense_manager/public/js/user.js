frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.doc.name !== frappe.session.user) return;

		frm.add_custom_button(__("Link Telegram"), () => {
			frappe.call({
				method: "expense_manager.api.telegram.generate_link_code",
				callback: (r) => {
					if (!r.message) return;

					frappe.msgprint({
						title: __("Link Telegram"),
						message: __(
							"Send this to the bot:<br><b>/link {0}</b><br><br>Expires at {1}.",
							[r.message.token, r.message.expires_at]
						),
					});
				},
			});
		});
	},
});
