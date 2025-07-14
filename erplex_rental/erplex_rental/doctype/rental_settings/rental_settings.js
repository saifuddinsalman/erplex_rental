frappe.ui.form.on('Rental Settings', {
    refresh: function (frm) {
        set_all_fields_filtrs(frm)
        // Add button to create warehouses for all companies
        frm.add_custom_button(__('Create Warehouses for All Companies'), function () {
            frappe.confirm(
                __('This will create Rented and Maintenance warehouses for all companies. Continue?'),
                function () {
                    frappe.call({
                        method: 'erplex_rental.erplex_rental.doctype.rental_settings.rental_settings.create_warehouses_for_all_companies',
                        callback: function (r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __('Success'),
                                    message: r.message.message,
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                }
            );
        }, __('Actions'));

        // Add button to create warehouses for specific company
        frm.add_custom_button(__('Create Warehouses for Company'), function () {
            frappe.prompt([
                {
                    fieldname: 'company',
                    fieldtype: 'Link',
                    label: 'Company',
                    options: 'Company',
                    reqd: 1
                }
            ], function (values) {
                frappe.call({
                    method: 'erplex_rental.erplex_rental.doctype.rental_settings.rental_settings.create_rental_warehouses',
                    args: {
                        company: values.company
                    },
                    callback: function (r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Success'),
                                message: r.message.message,
                                indicator: 'green'
                            });
                        }
                    }
                });
            }, __('Create Warehouses'));
        }, __('Actions'));
    },
});
frappe.ui.form.on('Rental Settings Defaults', {
});


function set_all_fields_filtrs(mfrm) {
    mfrm.set_query("rental_cost_center", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
            }
        };
    });
    mfrm.set_query("rental_income_account", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
                "account_type": "Income Account"
            }
        };
    });
    mfrm.set_query("security_deposit_account", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
                "account_type": ["in", ["Current Liability", "Current Asset"]]
            }
        };
    });
    mfrm.set_query("rental_source_warehouse", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
            }
        };
    });
    mfrm.set_query("rented_warehouse", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
            }
        };
    });
    mfrm.set_query("maintenance_warehouse", "defaults", function (frm, cdt, cdn) {
        let row = locals[cdt][cdn]
        return {
            filters: {
                "company": row.company,
                "is_group": 0,
            }
        };
    });
}

