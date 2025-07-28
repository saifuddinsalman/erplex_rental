cur_frm.ignore_doctypes_on_cancel_all = ['Stock Entry']
frappe.ui.form.on('Rental Delivery', {
    refresh: function (frm) {
        frm.set_query("sales_order", function (doc) {
            return {
                filters: {
                    docstatus: 1,
                    order_type: "Rental",
                    custom_all_rental_delivered: 0
                },
            };
        });
        // Add Create Rental Return button
        if (frm.doc.docstatus === 1 && frm.doc.status !== 'Returned') {
            frm.add_custom_button(__('Rental Return'), function () {
                frappe.model.open_mapped_doc({
                    method: "erplex_rental.erplex_rental.doctype.rental_return.rental_return.create_rental_return",
                    frm: frm
                });
            }, __('Create'));
        }

        // // Add Create Sales Invoice button
        // if (frm.doc.docstatus === 1) {
        //     frm.add_custom_button(__('Sales Invoice'), function () {
        //         frappe.call({
        //             method: "erplex_rental.utils.create_sales_invoice_from_rental_delivery",
        //             args: {
        //                 source_name: frm.doc.name
        //             },
        //             callback: function (r) {
        //                 if (r.message) {
        //                     frappe.model.sync(r.message);
        //                     frappe.set_route("Form", r.message.doctype, r.message.name);
        //                 }
        //             }
        //         });
        //     }, __('Create'));
        // }

        // Show status indicators
        if (frm.doc.status === 'Delivered') {
            frm.dashboard.add_indicator(__('Delivered'), 'green');
        } else if (frm.doc.status === 'Partially Returned') {
            frm.dashboard.add_indicator(__('Partially Returned'), 'orange');
        } else if (frm.doc.status === 'Returned') {
            frm.dashboard.add_indicator(__('Fully Returned'), 'blue');
        }
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Sales Order'), function () {
                erpnext.utils.map_current_doc({
                    method: "erplex_rental.erplex_rental.doctype.rental_delivery.rental_delivery.create_rental_delivery",
                    source_doctype: "Sales Order",
                    source_name: frm.doc.sales_order,
                    target: frm,
                    setters: {
                        customer: frm.doc.customer || undefined,
                        company: frm.doc.company || undefined, 
                    },
                    get_query_filters: {
                        docstatus: 1,
                        order_type: "Rental",
                        custom_all_rental_delivered: 0
                    }
                });
            }, __('Get Items From'));
        }
    },

    calculate_totals: function (frm) {
        let total_qty = 0;
        let total_amount = 0;
        let total_security_deposit = 0;
        frm.doc.items.forEach(function (item) {
            total_qty += flt(item.qty);
            total_amount += flt(item.amount);
        });

        frm.set_value('total_qty', total_qty);
        frm.set_value('grand_total', total_amount);
    },

    validate: function (frm) {
        frm.trigger('calculate_totals');
    },

    // company: function(frm) {
    //     if (frm.doc.company && !frm.doc.sales_order) {
    //         // Get default warehouses for the company
    //         frappe.call({
    //             method: 'erplex_rental.erplex_rental.doctype.rental_settings.rental_settings.get_default_warehouses',
    //             args: {
    //                 company: frm.doc.company
    //             },
    //             callback: function(r) {
    //                 if (r.message) {
    //                     if (!frm.doc.target_warehouse) {
    //                         frm.set_value('target_warehouse', r.message.source_warehouse);
    //                     }
    //                     if (!frm.doc.rented_warehouse) {
    //                         frm.set_value('rented_warehouse', r.message.rented_warehouse);
    //                     }
    //                 }
    //             }
    //         });
    //     }
    // }
});

frappe.ui.form.on('Rental Delivery Item', {
    item_code: function (frm, cdt, cdn) {
        let item = locals[cdt][cdn];

        if (item.item_code) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item',
                    fieldname: ['item_name', 'description', 'rental_security_deposit', 'is_rental_item'],
                    filters: { name: item.item_code }
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        frappe.model.set_value(cdt, cdn, 'security_deposit', r.message.rental_security_deposit || 0);

                        // Warn if item is not a rental item
                        if (!r.message.is_rental_item) {
                            frappe.msgprint(__('Warning: {0} is not configured as a rental item', [item.item_code]));
                        }
                    }
                }
            });
        }
    },

    qty: function (frm, cdt, cdn) {
        calculate_item_amount(frm, cdt, cdn);
        frm.trigger('calculate_totals');
    },

    rate: function (frm, cdt, cdn) {
        calculate_item_amount(frm, cdt, cdn);
        frm.trigger('calculate_totals');
    },

    security_deposit: function (frm, cdt, cdn) {
        calculate_item_total(frm, cdt, cdn);
        frm.trigger('calculate_totals');
    },

    items_remove: function (frm) {
        frm.trigger('calculate_totals');
    }
});

function calculate_item_amount(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    let amount = flt(item.qty) * flt(item.rate);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    calculate_item_total(frm, cdt, cdn);
}

function calculate_item_total(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    let total_amount = flt(item.amount) + flt(item.security_deposit);
    frappe.model.set_value(cdt, cdn, 'total_amount', total_amount);

    // Set pending qty equal to qty initially
    frappe.model.set_value(cdt, cdn, 'pending_qty', item.qty || 0);
}