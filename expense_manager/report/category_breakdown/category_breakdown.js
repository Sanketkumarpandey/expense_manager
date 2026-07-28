// Copyright (c) 2026, Sanket Kumar and contributors
// For license information, please see license.txt

frappe.query_report.on("dependent", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("date_from", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("date_to", function () {
	frappe.query_report.refresh();
});
