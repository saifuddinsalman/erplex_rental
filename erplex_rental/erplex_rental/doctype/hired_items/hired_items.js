// Copyright (c) 2025, ERPlexSolutions and contributors
// For license information, please see license.txt
cur_frm.ignore_doctypes_on_cancel_all = ['Stock Entry']
frappe.ui.form.on('Hired Items', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 1 && !frm.doc.is_return && frm.doc.status != "Returned") {
            // Add Create Return button for submitted non-return documents
            frm.add_custom_button(__('Create Return'), function() {
                frm.call('create_return').then(r => {
                    if (r.message) {
                        frappe.set_route('Form', 'Hired Items', r.message);
                    }
                });
            }, __('Actions'));
        }
        
        // Set form behavior based on document type
        if (frm.doc.is_return) {
            frm.set_df_property('supplier', 'read_only', 1);
            frm.set_df_property('return_against', 'read_only', 1);
        }
        
        // Refresh totals
        frm.trigger('calculate_totals');
    },
    
    supplier: function(frm) {
        // Clear items when supplier changes
        if (frm.doc.supplier && !frm.doc.is_return) {
            frm.clear_table('items');
            frm.refresh_field('items');
        }
    },
    
    calculate_totals: function(frm) {
        let total_qty = 0;
        let total_amount = 0;
        
        frm.doc.items.forEach(function(item) {
            total_qty += flt(item.qty);
            total_amount += flt(item.amount);
        });
        
        frm.set_value('total_qty', total_qty);
        frm.set_value('total_amount', total_amount);
    },
    
    return_against: function(frm) {
        if (frm.doc.return_against && frm.doc.is_return) {
            // Fetch original document items
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Hired Items',
                    name: frm.doc.return_against
                },
                callback: function(r) {
                    if (r.message) {
                        // Clear existing items
                        frm.clear_table('items');
                        
                        // Add items with available quantities
                        r.message.items.forEach(function(orig_item) {
                            let available_qty = flt(orig_item.qty) - flt(orig_item.returned_qty);
                            if (available_qty > 0) {
                                let item = frm.add_child('items');
                                item.item_code = orig_item.item_code;
                                item.item_name = orig_item.item_name;
                                item.description = orig_item.description;
                                item.qty = available_qty;
                                item.rate = orig_item.rate;
                                item.amount = available_qty * orig_item.rate;
                            }
                        });
                        
                        frm.refresh_field('items');
                        frm.trigger('calculate_totals');
                    }
                }
            });
        }
    },
    
    validate: function(frm) {
        // Additional client-side validations
        if (!frm.doc.items || frm.doc.items.length === 0) {
            frappe.msgprint(__('Please add at least one item'));
            frappe.validated = false;
            return;
        }
        
        // Validate items
        let has_error = false;
        frm.doc.items.forEach(function(item, idx) {
            if (!item.item_code) {
                frappe.msgprint(__('Row {0}: Please select Item Code', [idx + 1]));
                has_error = true;
            }
            
            if (flt(item.qty) <= 0) {
                frappe.msgprint(__('Row {0}: Qty must be greater than 0', [idx + 1]));
                has_error = true;
            }
        });
        
        if (has_error) {
            frappe.validated = false;
        }
    }
});

frappe.ui.form.on('Hired Items Detail', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.item_code) {
            // Fetch item details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Item',
                    name: row.item_code
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
                        frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        // Set default rate from item's standard_rate
                        if (r.message.standard_rate) {
                            frappe.model.set_value(cdt, cdn, 'rate', r.message.standard_rate);
                        }
                    }
                }
            });
            
            // Set query for item_code
            frm.set_query('item_code', 'items', function() {
                return {
                    filters: {
                        'is_stock_item': 1,
                        'disabled': 0
                    }
                };
            });
        }
    },
    
    qty: function(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
        frm.trigger('calculate_totals');
    },
    
    rate: function(frm, cdt, cdn) {
        calculate_amount(frm, cdt, cdn);
        frm.trigger('calculate_totals');
    },
    
    items_remove: function(frm) {
        frm.trigger('calculate_totals');
    }
});

function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let amount = flt(row.qty) * flt(row.rate);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
}