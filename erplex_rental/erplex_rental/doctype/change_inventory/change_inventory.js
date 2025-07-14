cur_frm.ignore_doctypes_on_cancel_all = ['Stock Entry']
frappe.ui.form.on('Change Inventory', {
    refresh: function(frm) {
        frm.set_query("warehouse", function() {
            return {
                filters: {
                    'company': frm.doc.company,
                    'is_group': 0,
                }
            };
        });
        // Show linked stock entry
        if (frm.doc.stock_entry) {
            frm.add_custom_button(__('View Stock Entry'), function() {
                frappe.set_route('Form', 'Stock Entry', frm.doc.stock_entry);
            });
        }
        
        // Add quick action buttons
        if (frm.doc.docstatus === 0) {
            // frm.add_custom_button(__('Get Item Rate'), function() {
            //     if (frm.doc.source_item && frm.doc.warehouse) {
            //         frappe.call({
            //             method: 'erplex_rental.erplex_rental.doctype.change_inventory.change_inventory.get_item_rate',
            //             args: {
            //                 item_code: frm.doc.source_item,
            //                 warehouse: frm.doc.warehouse
            //             },
            //             callback: function(r) {
            //                 if (r.message) {
            //                     frm.set_value('source_rate', r.message);
            //                 }
            //             }
            //         });
            //     } else {
            //         frappe.msgprint(__('Please select Source Item and Warehouse first'));
            //     }
            // }, __('Actions'));
            
            frm.add_custom_button(__('Check Stock Balance'), function() {
                if (frm.doc.source_item && frm.doc.warehouse) {
                    frappe.call({
                        method: 'erplex_rental.erplex_rental.doctype.change_inventory.change_inventory.get_item_stock_balance',
                        args: {
                            item_code: frm.doc.source_item,
                            warehouse: frm.doc.warehouse,
                            posting_date: frm.doc.posting_date,
                            posting_time: frm.doc.posting_time
                        },
                        callback: function(r) {
                            if (r.message !== undefined) {
                                frappe.msgprint(__('Available Stock: {0}', [r.message]));
                            }
                        }
                    });
                } else {
                    frappe.msgprint(__('Please select Source Item and Warehouse first'));
                }
            }, __('Actions'));
        }
        
        // Show status indicators
        // if (frm.doc.docstatus === 1) {
        //     if (frm.doc.difference_amount > 0) {
        //         frm.dashboard.add_indicator(__('Value Increased'), 'green');
        //     } else if (frm.doc.difference_amount < 0) {
        //         frm.dashboard.add_indicator(__('Value Decreased'), 'red');
        //     } else {
        //         frm.dashboard.add_indicator(__('Value Neutral'), 'blue');
        //     }
        // }
    },
    
    source_item: function(frm) {
        if (frm.doc.source_item) {
            // Get item details
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item',
                    fieldname: ['item_name', 'standard_rate'],
                    filters: {name: frm.doc.source_item}
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('source_item_name', r.message.item_name);
                        // if (!frm.doc.source_rate && r.message.standard_rate) {
                        //     frm.set_value('source_rate', r.message.standard_rate);
                        // }
                    }
                }
            });
            
            // Auto-get rate if warehouse is selected
            // if (frm.doc.warehouse) {
            //     frappe.call({
            //         method: 'erplex_rental.erplex_rental.doctype.change_inventory.change_inventory.get_item_rate',
            //         args: {
            //             item_code: frm.doc.source_item,
            //             warehouse: frm.doc.warehouse
            //         },
            //         callback: function(r) {
            //             if (r.message && !frm.doc.source_rate) {
            //                 frm.set_value('source_rate', r.message);
            //             }
            //         }
            //     });
            // }
        }
    },
    
    // warehouse: function(frm) {
    //     // Auto-get rate when warehouse changes
    //     if (frm.doc.source_item && frm.doc.warehouse) {
    //         frappe.call({
    //             method: 'erplex_rental.erplex_rental.doctype.change_inventory.change_inventory.get_item_rate',
    //             args: {
    //                 item_code: frm.doc.source_item,
    //                 warehouse: frm.doc.warehouse
    //             },
    //             callback: function(r) {
    //                 if (r.message && !frm.doc.source_rate) {
    //                     frm.set_value('source_rate', r.message);
    //                 }
    //             }
    //         });
    //     }
    // },
    
    // source_qty: function(frm) {
    //     calculate_source_amount(frm);
    // },
    
    // source_rate: function(frm) {
    //     calculate_source_amount(frm);
    // },
    
    // validate: function(frm) {
    //     calculate_totals(frm);
    // }
});

frappe.ui.form.on('Change Inventory Item', {
    item_code: function(frm, cdt, cdn) {
        let item = locals[cdt][cdn];
        
        // if (item.item_code) {
        //     frappe.call({
        //         method: 'frappe.client.get_value',
        //         args: {
        //             doctype: 'Item',
        //             fieldname: ['item_name', 'description', 'standard_rate'],
        //             filters: {name: item.item_code}
        //         },
        //         callback: function(r) {
        //             if (r.message) {
        //                 frappe.model.set_value(cdt, cdn, 'item_name', r.message.item_name);
        //                 frappe.model.set_value(cdt, cdn, 'description', r.message.description);
                        
        //                 if (!item.rate && r.message.standard_rate) {
        //                     frappe.model.set_value(cdt, cdn, 'rate', r.message.standard_rate);
        //                 }
        //             }
        //         }
        //     });
            
        //     // Auto-get rate from warehouse if available
        //     if (frm.doc.warehouse) {
        //         frappe.call({
        //             method: 'erplex_rental.erplex_rental.doctype.change_inventory.change_inventory.get_item_rate',
        //             args: {
        //                 item_code: item.item_code,
        //                 warehouse: frm.doc.warehouse
        //             },
        //             callback: function(r) {
        //                 if (r.message && !item.rate) {
        //                     frappe.model.set_value(cdt, cdn, 'rate', r.message);
        //                 }
        //             }
        //         });
        //     }
        // }
    },
    
    // qty: function(frm, cdt, cdn) {
    //     calculate_item_amount(frm, cdt, cdn);
    //     calculate_totals(frm);
    // },
    
    // rate: function(frm, cdt, cdn) {
    //     calculate_item_amount(frm, cdt, cdn);
    //     calculate_totals(frm);
    // },
    
    // target_items_remove: function(frm) {
    //     calculate_totals(frm);
    // }
});

// function calculate_source_amount(frm) {
//     let source_amount = flt(frm.doc.source_qty) * flt(frm.doc.source_rate);
//     frm.set_value('source_amount', source_amount);
//     calculate_totals(frm);
// }

// function calculate_item_amount(frm, cdt, cdn) {
//     let item = locals[cdt][cdn];
//     let amount = flt(item.qty) * flt(item.rate);
//     frappe.model.set_value(cdt, cdn, 'amount', amount);
// }

// function calculate_totals(frm) {
//     let total_target_qty = 0;
//     let total_target_amount = 0;
    
//     frm.doc.target_items.forEach(function(item) {
//         total_target_qty += flt(item.qty);
//         total_target_amount += flt(item.amount);
//     });
    
//     frm.set_value('total_target_qty', total_target_qty);
//     frm.set_value('total_target_amount', total_target_amount);
    
//     let difference_amount = flt(total_target_amount) - flt(frm.doc.source_amount);
//     frm.set_value('difference_amount', difference_amount);
    
//     // Show warning if significant difference
//     if (Math.abs(difference_amount) > (flt(frm.doc.source_amount) * 0.1)) { // 10% difference
//         frm.dashboard.add_comment(__('Warning: Significant value difference detected'), 'yellow');
//     }
// }