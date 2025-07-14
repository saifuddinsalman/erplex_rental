frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        // Add button to create invoice from rental delivery
        if (!frm.doc.name && !frm.doc.rental_delivery) {
            frm.add_custom_button(__('Rental Delivery'), function() {
                frappe.prompt([
                    {
                        fieldname: 'rental_delivery',
                        fieldtype: 'Link',
                        label: 'Rental Delivery',
                        options: 'Rental Delivery',
                        reqd: 1
                    }
                ], function(values) {
                    frappe.call({
                        method: "erplex_rental.erplex_rental.doctype.rental_delivery.rental_delivery.create_sales_invoice_from_rental_delivery",
                        args: {
                            source_name: values.rental_delivery
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.model.sync(r.message);
                                frappe.set_route("Form", r.message.doctype, r.message.name);
                            }
                        }
                    });
                }, __('Create Sales Invoice from Rental Delivery'));
            }, __('Get Items From'));
        }
        
        // Show rental delivery link if exists
        if (frm.doc.rental_delivery) {
            frm.add_custom_button(__('View Rental Delivery'), function() {
                frappe.set_route('Form', 'Rental Delivery', frm.doc.rental_delivery);
            });
        }
    },
    
    rental_delivery: function(frm) {
        if (frm.doc.rental_delivery) {
            // Fetch rental delivery details
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Rental Delivery',
                    name: frm.doc.rental_delivery
                },
                callback: function(r) {
                    if (r.message) {
                        let rental_delivery = r.message;
                        
                        // Set customer and company
                        frm.set_value('customer', rental_delivery.customer);
                        frm.set_value('company', rental_delivery.company);
                        
                        // Clear existing items
                        frm.clear_table('items');
                        
                        // Add rental delivery items
                        rental_delivery.items.forEach(function(item) {
                            let invoice_item = frm.add_child('items');
                            invoice_item.item_code = item.item_code;
                            invoice_item.item_name = item.item_name;
                            invoice_item.description = item.description;
                            invoice_item.qty = item.qty;
                            invoice_item.rate = item.rate;
                            invoice_item.amount = item.amount;
                        });
                        
                        frm.refresh_field('items');
                        frm.trigger('calculate_taxes_and_totals');
                    }
                }
            });
        }
    }
});