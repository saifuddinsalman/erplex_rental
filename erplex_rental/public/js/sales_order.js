frappe.ui.form.on('Sales Order', {
    refresh: function (frm) {
        if (frm.doc.__islocal === 1 && frm.doc.order_type == "Rental") {
            get_rental_data(frm)
        }
        if (frm.doc.docstatus === 1 && frm.doc.order_type == "Rental") {
            frappe.run_serially([
                () => frappe.timeout(2),
                () => frm.clear_custom_buttons(),
                () => {
                    if (!frm.doc.custom_all_rental_delivered) {
                        frm.add_custom_button(__('Rental Delivery'), function () {
                            frappe.model.open_mapped_doc({
                                method: "erplex_rental.erplex_rental.doctype.rental_delivery.rental_delivery.create_rental_delivery",
                                frm: frm
                            });
                        }, __('Create'));
                    }
                },
            ]);
        }
    },

    order_type: function (frm) {
        get_rental_data(frm)
    },

    validate: function (frm) {

    }
});

function get_rental_data(frm) {
    frm.set_df_property('cost_center', 'read_only', 0);
    frm.set_df_property('set_warehouse', 'read_only', 0);
    if (frm.doc.order_type == "Rental") {
        frappe.call({
            method: 'erplex_rental.erplex_rental.doctype.rental_settings.rental_settings.get_defaults',
            args: {
                company: frm.doc.company
            },
            callback: function (r) {
                if (r.message) {
                    if (r.message.source_warehouse) {
                        frm.set_df_property('set_warehouse', 'read_only', 1);
                        frm.set_value('set_warehouse', r.message.source_warehouse);
                    } else {
                        frappe.throw("Please set Source Warehouse in Rental Settings");
                    }
                    if (r.message.cost_center) {
                        frm.set_df_property('cost_center', 'read_only', 1);
                        frm.set_value('cost_center', r.message.cost_center);
                    } else {
                        frappe.throw("Please set Cost Center in Rental Settings");
                    }
                }
            }
        });
    } else {
        frm.set_value('set_warehouse', '');
        frm.set_value('cost_center', '');
        frm.set_value('custom_all_rental_delivered', 0);
    }

    frm.refresh_fields();
}

frappe.ui.form.on('Sales Order Item', {
    // item_code: function (frm, cdt, cdn) {
    //     let item = locals[cdt][cdn];
    // },
});