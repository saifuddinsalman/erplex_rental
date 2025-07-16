// Copyright (c) 2025, ERPlexSolutions and contributors
// For license information, please see license.txt

frappe.query_reports["MRF Report"] = {
	"filters": [
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"reqd": 1,
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "sales_order",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
			"reqd": 1,
			"get_query": function() {
				return {
					filters: {
						"docstatus": 1,
						"company": frappe.query_report.get_filter_value("company"),
						"order_type": "Rental",
					}
				};
			}
		}
	]
};
