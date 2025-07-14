frappe.ui.form.on('Item', {
    is_rental_item: function(frm) {
        if (frm.doc.is_rental_item) {
            // Set default rental period type
            if (!frm.doc.rental_period_type) {
                frm.set_value('rental_period_type', 'Day');
            }
            
            // Show rental fields
            frm.toggle_display(['rental_rate', 'rental_period', 'rental_period_type', 'rental_security_deposit'], true);
        } else {
            // Clear rental fields when unchecked
            frm.set_value('rental_rate', 0);
            frm.set_value('rental_period', 0);
            frm.set_value('rental_period_type', '');
            frm.set_value('rental_security_deposit', 0);
            
            // Hide rental fields
            frm.toggle_display(['rental_rate', 'rental_period', 'rental_period_type', 'rental_security_deposit'], false);
        }
    },
    
    refresh: function(frm) {
        // Toggle rental fields visibility based on is_rental_item
        if (frm.doc.is_rental_item) {
            frm.toggle_display(['rental_rate', 'rental_period', 'rental_period_type', 'rental_security_deposit'], true);
        } else {
            frm.toggle_display(['rental_rate', 'rental_period', 'rental_period_type', 'rental_security_deposit'], false);
        }
    },
    
    validate: function(frm) {
        if (frm.doc.is_rental_item) {
            if (!frm.doc.rental_rate || frm.doc.rental_rate <= 0) {
                frappe.msgprint(__('Rental Rate is required for rental items'));
                frappe.validated = false;
            }
            
            if (!frm.doc.rental_period || frm.doc.rental_period <= 0) {
                frappe.msgprint(__('Rental Period is required for rental items'));
                frappe.validated = false;
            }
            
            if (!frm.doc.rental_period_type) {
                frappe.msgprint(__('Rental Period Type is required for rental items'));
                frappe.validated = false;
            }
        }
    }
});