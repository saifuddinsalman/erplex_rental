if (cur_frm?.doctype) {
    frappe.ui.form.on(cur_frm.doctype, {
        refresh: function (frm) {
            clear_custom_buttons(frm)
            if (frm.doc.__islocal === 1 && frm.doc.custom_order_type == "Rental") {
                get_rental_data(frm)
            }
            set_field_properties(frm)
        },
        custom_order_type: function (frm) {
            get_rental_data(frm)
        },
    });
}

function get_rental_data(frm) {
    let cost_center_fieldname = "cost_center"
    let warehouse_fieldname = "set_warehouse"
    let item_warehouse_fieldname = "warehouse"

    if (frm.doc.custom_order_type == "Rental") {
        frappe.call({
            method: 'erplex_rental.erplex_rental.doctype.rental_settings.rental_settings.get_defaults',
            args: {
                company: frm.doc.company
            },
            callback: function (r) {
                if (r.message) {
                    if (r.message.source_warehouse) {
                        let warehouse = r.message.source_warehouse
                        if (frm.get_field(warehouse_fieldname)) {
                            frm.set_value(warehouse_fieldname, warehouse);
                        }
                        if (frm.fields_dict.items.grid.get_docfield(item_warehouse_fieldname)) {
                            for (let d of frm.doc.items) { d[item_warehouse_fieldname] = warehouse }
                            frm.refresh_field("items");
                        }
                    } else {
                        frappe.throw("Please set Source Warehouse in Rental Settings");
                    }
                    if (r.message.cost_center) {
                        if (frm.get_field(cost_center_fieldname)) {
                            frm.set_value(cost_center_fieldname, r.message.cost_center);
                        }
                    } else {
                        frappe.throw("Please set Cost Center in Rental Settings");
                    }
                }
                set_field_properties(frm)
            }
        });
    } else {
        if (frm.get_field(cost_center_fieldname)) { frm.set_value(cost_center_fieldname, '') }
        if (frm.get_field(warehouse_fieldname)) { frm.set_value(warehouse_fieldname, '') }
        if (frm.fields_dict.items.grid.get_docfield(item_warehouse_fieldname)) { for (let d of frm.doc.items) { d[item_warehouse_fieldname] = "" } }
    }
    set_field_properties(frm)
    frm.refresh_fields();
}

function set_field_properties(frm) {
    let cost_center_fieldname = "cost_center"
    if (frm.get_field(cost_center_fieldname)) {
        frm.set_df_property(cost_center_fieldname, 'read_only', 0);
        if (frm.doc.custom_order_type == "Rental") {
            frm.set_df_property(cost_center_fieldname, 'read_only', 1);
        }
    }

    let warehouse_fieldname = "set_warehouse"
    if (frm.get_field(warehouse_fieldname)) {
        frm.set_df_property(warehouse_fieldname, 'read_only', 0);
        if (frm.doc.custom_order_type == "Rental") {
            frm.set_df_property(warehouse_fieldname, 'read_only', 1);
        }
    }

    let item_warehouse_fieldname = "warehouse"
    if (frm.fields_dict.items.grid.get_docfield(item_warehouse_fieldname)) {
        frm.fields_dict.items.grid.update_docfield_property(item_warehouse_fieldname, 'read_only', 0);
        if (frm.doc.custom_order_type == "Rental") {
            frm.fields_dict.items.grid.update_docfield_property(item_warehouse_fieldname, 'read_only', 1);
        }
    }
}

function clear_custom_buttons(frm) {
    let intervalCount = 0;
    const interval = setInterval(() => {
        clear_custom_buttons_in_rental(frm)
        intervalCount++;
        if (intervalCount >= 10) {
            clearInterval(interval);
        }
    }, 1000);
}

function clear_custom_buttons_in_rental(frm) {
    if(frm.doc.custom_order_type == "Rental"){
        let btns_to_show = ["Supplier Quotation", "Purchase Order", "Purchase Receipt", "Purchase Return"]
        for (let btn in frm.custom_buttons || {}) {
            if (!btns_to_show.includes(btn)) {
                frm.remove_custom_button(__(btn))
                frm.remove_custom_button(__(btn), __("Tools"))
                frm.remove_custom_button(__(btn), __("Create"))
                frm.remove_custom_button(__(btn), __("Get Items From"))
            }
        }
    }
}