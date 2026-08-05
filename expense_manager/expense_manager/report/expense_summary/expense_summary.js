frappe.query_report.on("from_date", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("to_date", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("individual", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("dependent", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("category", function () {
	frappe.query_report.refresh();
});
