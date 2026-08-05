// Copyright (c) 2026, Sanket Kumar and contributors
// For license information, please see license.txt

frappe.query_report.on("dependent", function () {
	frappe.query_report.refresh();
});
