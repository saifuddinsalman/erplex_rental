# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, nowtime, flt
from erplex_rental.utils import (
    remove_linked_transactions,
    get_total_returned_qty,
)


class RentalReturn(Document):
    def before_insert(self):
        self.status = "Draft"

    def validate(self):
        self.validate_items()
        self.sales_order_count()
        self.calculate_totals()

    def validate_items(self):
        if not self.items:
            frappe.throw("Please add items to return")
        for item in self.items:
            if not item.item_code:
                frappe.throw("Item Code is required for all items")
            if (
                item.return_qty <= 0
                and item.maintenance_qty <= 0
                and item.damaged_qty <= 0
            ):
                frappe.throw(
                    "Return, Maintenance or Damaged Quantity must be greater than 0"
                )
            if (
                flt(item.return_qty) + flt(item.maintenance_qty) + flt(item.damaged_qty)
            ) > flt(item.delivered_qty):
                frappe.throw(
                    "Return + Maintenance + Damaged Quantity must be less than or equal to Delivered Quantity"
                )
            if (not item.rental_delivery) or (not item.rental_delivery_detail):
                frappe.throw(
                    "Rental Delivery and Rental Delivery Item are required for all items"
                )
            item.amount = (
                flt(item.return_qty) + flt(item.maintenance_qty) + flt(item.damaged_qty)
            ) * flt(item.rate, 2)

    def sales_order_count(self):
        orders = list(set([row.sales_order for row in self.items]))
        if len(orders) < 1:
            frappe.throw("At least one Sales Order is required for this Rental Return")
        if len(orders) > 1:
            frappe.throw("Rental Return cannot have multiple Sales Orders")
        if self.sales_order != orders[0]:
            frappe.throw(
                "Rental Return must be for the same Sales Order as the Rental Delivery"
            )

    def calculate_totals(self):
        for item in self.items:
            item.amount = flt(item.return_qty) * flt(item.rate)
            item.maintenance_amount = flt(item.maintenance_qty) * flt(
                item.maintenance_rate
            )
            item.damaged_amount = flt(item.damaged_qty) * flt(item.damaged_rate)
        self.total_return_qty = sum(flt(item.return_qty) for item in self.items)
        self.total_amount = sum(flt(item.amount) for item in self.items)
        self.total_maintenance_qty = sum(
            flt(item.maintenance_qty) for item in self.items
        )
        self.total_maintenance_amount = sum(
            flt(item.maintenance_amount) for item in self.items
        )
        self.total_damaged_qty = sum(flt(item.damaged_qty) for item in self.items)
        self.total_damaged_amount = sum(flt(item.damaged_amount) for item in self.items)
        self.grand_total = flt(
            self.total_amount + self.total_security_deposit_returned, 2
        )

    def before_submit(self):
        self.status = "Returned"

    def on_submit(self):
        if self.total_return_qty > 0 or self.total_maintenance_qty > 0:
            self.create_return_stock_entry()
        if self.total_damaged_qty > 0:
            self.create_damaged_stock_entry()
        self.update_rental_delivery()

    def after_submit(self):
        self.update_rental_delivery()

    def create_return_stock_entry(self):
        """Create stock entry to move items from rented warehouse back to main warehouse"""
        if not self.items:
            return
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Transfer"
        stock_entry.company = self.company
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.rental_return = self.name
        for item in self.items:
            if item.return_qty > 0 or item.maintenance_qty > 0:
                stock_entry.append(
                    "items",
                    {
                        "item_code": item.item_code,
                        "s_warehouse": self.source_warehouse,
                        "t_warehouse": self.target_warehouse,
                        "qty": item.return_qty + item.maintenance_qty,
                        "basic_rate": item.rate,
                    },
                )
        stock_entry.flags.ignore_permissions = True
        stock_entry.save()
        stock_entry.submit()

    def create_damaged_stock_entry(self):
        """Create stock entry to move items from rented warehouse back to main warehouse"""
        if not self.items:
            return
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = self.company
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.rental_return = self.name
        for item in self.items:
            if item.damaged_qty > 0:
                stock_entry.append(
                    "items",
                    {
                        "item_code": item.item_code,
                        "s_warehouse": self.source_warehouse,
                        # "t_warehouse": self.target_warehouse,
                        "qty": item.damaged_qty,
                        "basic_rate": item.rate,
                    },
                )
        stock_entry.flags.ignore_permissions = True
        stock_entry.save()
        stock_entry.submit()

    def update_rental_delivery(self):
        deliveries = list(set([row.rental_delivery for row in self.items]))
        for delivery in deliveries:
            rental_delivery = frappe.get_doc("Rental Delivery", delivery)
            for rd_item in rental_delivery.items:
                rd_item.returned_qty = get_total_returned_qty(
                    rd_item.sales_order,
                    rd_item.sales_order_detail,
                    rental_delivery.name,
                    rd_item.name,
                )
                rd_item.pending_qty = flt(rd_item.qty) - flt(rd_item.returned_qty)
                if rd_item.pending_qty <= 0:
                    rd_item.return_status = "Fully Returned"
                elif rd_item.returned_qty > 0:
                    rd_item.return_status = "Partially Returned"
                else:
                    rd_item.return_status = "Not Returned"
                rd_item.db_update()
            all_returned = all(
                item.return_status == "Fully Returned" for item in rental_delivery.items
            )
            any_returned = any(
                item.return_status in ["Partially Returned", "Fully Returned"]
                for item in rental_delivery.items
            )
            if all_returned:
                rental_delivery.status = "Returned"
            elif any_returned:
                rental_delivery.status = "Partially Returned"
            else:
                rental_delivery.status = "Delivered"
            rental_delivery.db_update()
            rental_delivery.update_sales_order()

    def before_cancel(self):
        self.status = "Cancelled"

    def on_cancel(self):
        remove_linked_transactions("Stock Entry", "rental_return", self.name)
        self.update_rental_delivery()

    def after_cancel(self):
        self.update_rental_delivery()


@frappe.whitelist()
def create_rental_return(source_name, target_doc=None):
    """Create Rental Return from Rental Delivery"""
    from frappe.model.mapper import get_mapped_doc

    def validate(source, target):
        if source.docstatus != 1:
            frappe.throw("Rental Delivery must be submitted")
        if source.status == "Returned":
            frappe.throw("All items have already been returned")

    def update_item(source, target, source_parent):
        if flt(source.pending_qty) > 0:
            target.delivered_qty = source.qty
            target.return_qty = source.pending_qty
            target.damaged_qty = 0
            target.rate = source.rate
            target.maintenance_rate, target.damaged_rate = frappe.db.get_value(
                "Item",
                source.item_code,
                ["custom_maintenance_charge", "custom_damage_charge"],
            ) or [0, 0]
            target.amount = flt(source.pending_qty * source.rate, 2)
            target.sales_order = source.sales_order
            target.sales_order_detail = source.sales_order_detail
            target.rental_delivery = source_parent.name
            target.rental_delivery_detail = source.name
        else:
            target.return_qty = 0  # This will exclude fully returned items

    def update_target(source, target):
        validate(source, target)
        target.sales_order = source.sales_order
        target.posting_date = today()
        target.posting_time = nowtime()
        target.return_date = today()
        target.source_warehouse = source.rented_warehouse
        target.target_warehouse = source.rental_source_warehouse

    doclist = get_mapped_doc(
        "Rental Delivery",
        source_name,
        {
            "Rental Delivery": {
                "doctype": "Rental Return",
                "validation": {"docstatus": ["=", 1]},
            },
            "Rental Delivery Item": {
                "doctype": "Rental Return Item",
                "condition": lambda doc: flt(doc.pending_qty) > 0,
                "postprocess": update_item,
            },
        },
        target_doc,
        postprocess=update_target,
        ignore_permissions=True,
    )

    return doclist
