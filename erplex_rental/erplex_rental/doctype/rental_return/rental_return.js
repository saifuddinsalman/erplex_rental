cur_frm.ignore_doctypes_on_cancel_all = ['Stock Entry']
frappe.ui.form.on('Rental Return', {
    refresh: function (frm) {
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
                        customer: frm.doc.customer || undefined,
                        company: frm.doc.company || undefined
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
        let total_return_qty = 0;
        let total_damaged_qty = 0;
        let total_amount = 0;
        let total_security_deposit = 0;

        frm.doc.items.forEach(function (item) {
            total_return_qty += item.return_qty || 0;
            total_damaged_qty += item.damaged_qty || 0;
            total_amount += item.amount || 0;
        });

        frm.set_value('total_return_qty', total_return_qty);
        frm.set_value('total_damaged_qty', total_damaged_qty);
        frm.set_value('total_amount', total_amount);
        frm.set_value('total_security_deposit_returned', total_security_deposit);
        frm.set_value('grand_total', total_amount + total_security_deposit);
    }
});

frappe.ui.form.on('Rental Return Item', {
    return_qty: function (frm, cdt, cdn) {
        calculate_return_item_amount(frm, cdt, cdn);
    },

    rate: function (frm, cdt, cdn) {
        calculate_return_item_amount(frm, cdt, cdn);
    }
});

function calculate_return_item_amount(frm, cdt, cdn) {
    let item = locals[cdt][cdn];

    if (item.return_qty > item.delivered_qty) {
        frappe.msgprint(__('Return quantity cannot exceed delivered quantity'));
        frappe.model.set_value(cdt, cdn, 'return_qty', item.delivered_qty);
        return;
    }

    let amount = (item.return_qty || 0) * (item.rate || 0);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
}