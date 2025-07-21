# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, nowtime, flt
from erplex_rental.utils import remove_linked_transactions, get_total_returned_qty, get_total_delivered_qty


class RentalDelivery(Document):
    def before_insert(self):
        self.status = "Draft"
    def validate(self):
        self.validate_items()
        self.sales_order_count()
        self.calculate_totals()

    def sales_order_count(self):
        orders = list(set([row.sales_order for row in self.items]))
        if len(orders) < 1:
            frappe.throw("At least one Sales Order is required for this Rental Delivery")
        if len(orders) > 1:
            frappe.throw("Rental Delivery cannot have multiple Sales Orders")
        if self.sales_order != orders[0]:
            frappe.throw("Rental Delivery must be for the same Sales Order Selected.")

    def validate_items(self):
        if not self.items:
            frappe.throw("Please add items to the Rental Delivery")
        for item in self.items:
            if not item.item_code:
                frappe.throw("Item Code is required for all items")
            if not item.qty or item.qty <= 0:
                frappe.throw("Quantity must be greater than 0 for all items")
            if not item.rate or item.rate <= 0:
                frappe.throw("Rate must be greater than 0 for all items")
            item.amount = flt(item.qty * item.rate, 2)
            item.pending_qty = item.qty

    def calculate_totals(self):
        self.total_qty = sum(flt(item.qty) for item in self.items)
        self.grand_total = sum(flt(item.amount) for item in self.items)
    def before_submit(self):
        self.status = "Delivered"
    def on_submit(self):
        self.status = "Delivered"
        self.create_stock_entry()
        self.update_sales_order()
    
    def after_submit(self):
        self.update_sales_order()

    def create_stock_entry(self):
        """Create stock entry to move items from target warehouse to rented warehouse"""
        if not self.items:
            return

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Transfer"
        stock_entry.company = self.company
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.rental_delivery = self.name
        for item in self.items:
            stock_entry.append(
                "items",
                {
                    "item_code": item.item_code,
                    "s_warehouse": self.rental_source_warehouse,
                    "t_warehouse": self.rented_warehouse,
                    "qty": item.qty,
                    "basic_rate": item.rate,
                },
            )
        stock_entry.flags.ignore_permissions = True
        stock_entry.save()
        stock_entry.submit()

    def before_cancel(self):
        self.status = "Cancelled"
    def on_cancel(self):
        # self.ignore_linked_doctypes = ("Stock Entry")
        self.status = "Cancelled"
        remove_linked_transactions("Stock Entry", "rental_delivery", self.name)
        self.update_sales_order()

    def after_cancel(self):
        self.update_sales_order()

    def update_sales_order(self):
        orders = list(set([row.sales_order for row in self.items]))
        for order in orders:
            so = frappe.get_doc("Sales Order", order)
            so.status = "To Deliver"
            for soi in so.items:
                custom_rental_delivered_qty = get_total_delivered_qty(so.name, soi.name)
                if custom_rental_delivered_qty > soi.qty:
                    frappe.throw("Cannot Deliver more than Ordered Qty, Total Remaining Qty to Deliver is {}".format(soi.qty - soi.custom_rental_delivered_qty))
                soi.custom_rental_delivered_qty = custom_rental_delivered_qty
                custom_rental_returned_qty = get_total_returned_qty(so.name, soi.name)
                if custom_rental_returned_qty > soi.qty:
                    frappe.throw("Cannot Return more than Ordered Qty, Total Remaining Qty to Deliver is {}".format(soi.qty - soi.custom_rental_returned_qty))
                soi.custom_rental_returned_qty = custom_rental_returned_qty 
                soi.db_update()
            so.custom_all_rental_delivered = all(soi.custom_rental_delivered_qty == soi.qty for soi in so.items)
            if so.custom_all_rental_delivered:
                so.status = "To Bill"
                if sum(soi.custom_rental_returned_qty for soi in so.items) == so.total_qty:
                    so.status = "Completed"
            so.db_update()
        frappe.db.commit()

@frappe.whitelist()
def create_rental_delivery(source_name, target_doc=None):
    """Create Rental Delivery from Sales Order"""
    from frappe.model.mapper import get_mapped_doc
    def validate(source, target):
        if source.order_type != "Rental":
            frappe.throw("Sales Order must be a rental order to create Rental Delivery")

    def update_item(source, target, source_parent):
        target.sales_order = source_parent.name
        target.sales_order_detail = source.name
        target.qty = source.qty - source.custom_rental_delivered_qty

    def update_target(source, target):
        validate(source, target)
        target.sales_order = source.name 
        target.delivery_date = source.delivery_date
        target.posting_date = today()
        target.posting_time = nowtime()
        from erplex_rental.erplex_rental.doctype.rental_settings.rental_settings import (
            get_default_warehouses,
        )
        warehouses = get_default_warehouses(source.company)
        target.rental_source_warehouse = source.set_warehouse or warehouses.get(
            "source_warehouse"
        )
        target.rented_warehouse = warehouses.get("rented_warehouse")
        if not target.rented_warehouse:
            frappe.throw("Please configure Rented Warehouse in Rental Settings")
        target.run_method('calculate_totals')

    doclist = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Rental Delivery",
                "validation": {
                    "docstatus": ["=", 1],
                    "custom_all_rental_delivered": ["=", 0],
                },
            },
            "Sales Order Item": {
                "doctype": "Rental Delivery Item",
                "condition": lambda doc: doc.custom_rental_delivered_qty != doc.qty,
                "postprocess": update_item,
            },
        },
        target_doc,
        postprocess=update_target,
        ignore_permissions=True,
    )

    return doclist


def validate_sales_order_rental(doc, method):
    """Validate sales order rental fields"""
    if doc.order_type == "Rental":
        pass
        # if not doc.rental_start_date:
        #     frappe.throw("Rental Start Date is required for rental orders")
        # if not doc.rental_end_date:
        #     frappe.throw("Rental End Date is required for rental orders")
        # if doc.rental_start_date > doc.rental_end_date:
        #     frappe.throw("Rental Start Date cannot be greater than Rental End Date")


def create_rental_delivery_from_sales_order(doc, method):
    """Auto create rental delivery button in sales order"""
    # This function can be used to add custom logic when sales order is submitted
    pass
