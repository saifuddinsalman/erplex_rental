cur_frm.ignore_doctypes_on_cancel_all = ['Stock Entry']
frappe.ui.form.on('Rental Return', {
    refresh: function (frm) {
        frm.set_query("sales_order", function (doc) {
            return {
                filters: {
                    docstatus: 1,
                    order_type: "Rental",
                    // custom_all_rental_delivered: 0
                },
            };
        });
        // Show status indicators
        if (frm.doc.status === 'Returned') {
            frm.dashboard.add_indicator(__('Returned'), 'green');
        }
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Rental Delivery'), function () {
                erpnext.utils.map_current_doc({
                    method: "erplex_rental.erplex_rental.doctype.rental_return.rental_return.create_rental_return",
                    source_doctype: "Rental Delivery",
                    target: frm,
                    setters: {
                        sales_order: frm.doc.sales_order || undefined,
                        customer: frm.doc.customer || undefined,
                    },
                    get_query_filters: {
                        docstatus: 1,
                        status: ["!=", "Returned"],
                    }
                });
            }, __('Get Items From'));
        }
    },
    validate: function (frm) {
        calculate_totals(frm)
    }
});

frappe.ui.form.on('Rental Return Item', {
    return_qty: function (frm, cdt, cdn) {
        calculate_totals(frm)
    },

    rate: function (frm, cdt, cdn) {
        calculate_totals(frm)
    }
});

function calculate_totals(frm) {
    let total_return_qty = 0;
    let total_amount = 0;
    let total_damaged_qty = 0;
    let total_maintenance_qty = 0;
    let total_maintenance_amount = 0;
    let total_damaged_amount = 0;
    let total_security_deposit = 0;

    frm.doc.items.forEach(function (item) {
        item.amount = flt(item.return_qty) * flt(item.rate)
        item.maintenance_amount = flt(item.maintenance_qty) * flt(item.maintenance_rate)
        item.damaged_amount = flt(item.damaged_qty) * flt(item.damaged_rate)
        total_return_qty += item.return_qty || 0;
        total_amount += item.amount || 0;
        total_maintenance_qty += item.maintenance_qty || 0;
        total_maintenance_amount += item.maintenance_amount || 0;
        total_damaged_qty += item.damaged_qty || 0;
        total_damaged_amount += item.damaged_amount || 0;
    });
    frm.refresh_field('items');
    frm.set_value('total_return_qty', total_return_qty);
    frm.set_value('total_amount', total_amount);
    frm.set_value('total_maintenance_qty', total_maintenance_qty);
    frm.set_value('total_maintenance_amount', total_maintenance_amount);
    frm.set_value('total_damaged_qty', total_damaged_qty);
    frm.set_value('total_damaged_amount', total_damaged_amount);

    frm.set_value('total_security_deposit_returned', total_security_deposit);
    frm.set_value('grand_total', total_amount + total_security_deposit);
}