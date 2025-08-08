import frappe
from frappe.utils import flt
from erplex_rental.utils import (
    update_last_billed_date_in_so,
    get_total_returned_qty,
    get_total_delivered_qty,
    get_last_billed_date,
    get_total_deposit_used,
    create_unbilled_completed_rental_invoices,
    get_last_rental_return,
)


def update_so(so_name):
    so = frappe.get_doc("Sales Order", so_name)
    so.custom_last_billed_date = get_last_billed_date(so_name)
    so.custom_remaining_security_deposit = flt(so.custom_security_deposit) - flt(
        get_total_deposit_used(so_name)
    )
    so.status = "To Deliver"
    for soi in so.items:
        custom_rental_delivered_qty = get_total_delivered_qty(so.name, soi.name)
        if custom_rental_delivered_qty > soi.qty:
            frappe.throw(
                "Cannot Deliver more than Ordered Qty, Total Remaining Qty to Deliver is {}".format(
                    soi.qty - soi.custom_rental_delivered_qty
                )
            )
        soi.custom_rental_delivered_qty = custom_rental_delivered_qty
        custom_rental_returned_qty = get_total_returned_qty(so.name, soi.name)
        if custom_rental_returned_qty > soi.qty:
            frappe.throw(
                "Cannot Return more than Ordered Qty, Total Remaining Qty to Deliver is {}".format(
                    soi.qty - soi.custom_rental_returned_qty
                )
            )
        soi.custom_rental_returned_qty = custom_rental_returned_qty
        soi.db_update()
    so.custom_all_rental_delivered = all(
        soi.custom_rental_delivered_qty == soi.qty for soi in so.items
    )
    if so.custom_all_rental_delivered:
        so.status = "To Bill"
        if sum(soi.custom_rental_returned_qty for soi in so.items) == so.total_qty:
            so.status = "Completed"
    so.db_update()
    if so.status == "Completed":
        create_unbilled_completed_rental_invoices(so.name)
        frappe.db.set_value(
            "Rental Return",
            get_last_rental_return(so.name),
            "total_security_deposit_returned",
            so.custom_remaining_security_deposit,
        )
    frappe.db.commit()


def is_rental_invoice(self):
    has_rental_order = False
    for item in self.items:
        if item.sales_order:
            order_type = frappe.db.get_value(
                "Sales Order", item.sales_order, "order_type"
            )
            if order_type == "Rental":
                has_rental_order = True
                break
    return has_rental_order


def sales_invoice_validate(self, method=None):
    if is_rental_invoice(self):
        orders = list(set([row.sales_order for row in self.items]))
        if len(orders) < 1:
            frappe.throw("At least one Sales Order is required for this Rental Invoice")
        if len(orders) > 1:
            frappe.throw("Rental Invoice cannot have multiple Sales Orders")
        if self.update_stock:
            frappe.throw("Stock Update is not allowed for Rental Invoice")


def sales_invoice_on_submit(self, method=None):
    if is_rental_invoice(self):
        orders = list(set([row.sales_order for row in self.items]))
        update_last_billed_date_in_so(orders[0])
        update_so(orders[0])


def sales_invoice_on_cancel(self, method=None):
    if is_rental_invoice(self):
        orders = list(set([row.sales_order for row in self.items]))
        last_billed_date = frappe.db.get_value(
            "Sales Order", orders[0], "custom_last_billed_date"
        )
        if last_billed_date:
            if last_billed_date > self.posting_date:
                frappe.throw(
                    "This Sales Invoice cannot be cancelled as this is not the latest Invoice"
                )
        update_last_billed_date_in_so(orders[0])
        update_so(orders[0])

def sales_order_validate(self, method=None):
    if self.order_type == "Rental":
        from erplex_rental.erplex_rental.doctype.rental_settings.rental_settings import get_defaults
        data = get_defaults(self.company)
        if not data.source_warehouse:
            frappe.throw("Please set Source Warehouse in Rental Settings")
        if not data.cost_center:
            frappe.throw("Please set Cost Center in Rental Settings")
        self.set_warehouse = data.source_warehouse
        self.cost_center = data.cost_center


def set_purchase_rental_defaluts(self):
    if self.custom_order_type == "Rental":
        from erplex_rental.erplex_rental.doctype.rental_settings.rental_settings import get_defaults
        data = get_defaults(self.company)
        if not data.source_warehouse:
            frappe.throw("Please set Source Warehouse in Rental Settings")
        if not data.cost_center:
            frappe.throw("Please set Cost Center in Rental Settings")
        self.set_warehouse = data.source_warehouse
        self.cost_center = data.cost_center

def supplier_quotation_validate(self, method=None):
    for row in self.items:
        if row.request_for_quotation:
            if self.custom_order_type != frappe.db.get_value("Request for Quotation", row.request_for_quotation, "custom_order_type"):
                frappe.throw(f"All Requests for Quotations must be of the '{self.custom_order_type}' Order Type.")
    if self.custom_order_type == "Rental":
        from erplex_rental.erplex_rental.doctype.rental_settings.rental_settings import get_defaults
        data = get_defaults(self.company)
        if not data.cost_center:
            frappe.throw("Please set Cost Center in Rental Settings")
        self.cost_center = data.cost_center


def purchase_order_validate(self, method=None):
    for row in self.items:
        if row.supplier_quotation:
            if self.custom_order_type != frappe.db.get_value("Supplier Quotation", row.supplier_quotation, "custom_order_type"):
                frappe.throw(f"All Supplier Quotations must be of the '{self.custom_order_type}' Order Type.")
    set_purchase_rental_defaluts(self)

def purchase_receipt_validate(self, method=None):
    for row in self.items:
        if row.purchase_order:
            if self.custom_order_type != frappe.db.get_value("Purchase Order", row.purchase_order, "custom_order_type"):
                frappe.throw(f"All Purchase Orders must be of the '{self.custom_order_type}' Order Type.")
    set_purchase_rental_defaluts(self)

def purchase_invoice_validate(self, method=None):
    for row in self.items:
        if row.purchase_order:
            if self.custom_order_type != frappe.db.get_value("Purchase Order", row.purchase_order, "custom_order_type"):
                frappe.throw(f"All Purchase Orders must be of the '{self.custom_order_type}' Order Type.")
    set_purchase_rental_defaluts(self)