frappe.query_report.on("month", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("year", function () {
	frappe.query_report.refresh();
});

frappe.query_report.on("dependent", function () {
	frappe.query_report.refresh();
});
