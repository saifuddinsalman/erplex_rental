# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, nowtime
from erpnext.stock.utils import get_stock_balance
from erplex_rental.utils import remove_linked_transactions 


class ChangeInventory(Document):
    def validate(self):
        self.validate_source_item()
        self.validate_target_items()
        self.calculate_totals()
        self.validate_stock_availability()

    def validate_source_item(self):
        """Validate source item details"""
        if not self.source_item:
            frappe.throw("Source Item is required")

        if not self.source_qty or self.source_qty <= 0:
            frappe.throw("Source Qty must be greater than 0")

        # if not self.source_rate or self.source_rate <= 0:
        #     frappe.throw("Source Rate must be greater than 0")

        # Get item details
        item_doc = frappe.get_doc("Item", self.source_item)
        self.source_item_name = item_doc.item_name

        # # Calculate source amount
        # self.source_amount = flt(self.source_qty * self.source_rate, 2)

    def validate_target_items(self):
        """Validate target items"""
        if not self.target_items:
            frappe.throw("At least one target item is required")

        for item in self.target_items:
            if not item.item_code:
                frappe.throw("Item Code is required for all target items")
            if item.item_code == self.source_item:
                frappe.throw("Target Item Code cannot be the same as Source Item")
            if not item.qty or item.qty <= 0:
                frappe.throw("Qty must be greater than 0 for all target items")

            # if not item.rate or item.rate <= 0:
            #     frappe.throw("Rate must be greater than 0 for all target items")

            # Get item details
            item_doc = frappe.get_doc("Item", item.item_code)
            item.item_name = item_doc.item_name
            item.description = item_doc.description

            # # Calculate amount
            # item.amount = flt(item.qty * item.rate, 2)

    def calculate_totals(self):
        """Calculate totals"""
        self.total_target_qty = sum(flt(item.qty) for item in self.target_items)
        # self.total_target_amount = sum(flt(item.amount) for item in self.target_items)
        # self.difference_amount = flt(self.total_target_amount - self.source_amount, 2)

    def validate_stock_availability(self):
        """Validate if source item has sufficient stock"""
        if not self.warehouse:
            frappe.throw("Warehouse is required")

        available_qty = get_stock_balance(
            item_code=self.source_item,
            warehouse=self.warehouse,
            posting_date=self.posting_date,
            posting_time=self.posting_time,
        )

        if flt(available_qty) < flt(self.source_qty):
            frappe.throw(
                f"Insufficient stock for item {self.source_item} in warehouse {self.warehouse}. "
                f"Available: {available_qty}, Required: {self.source_qty}"
            )

    def on_submit(self):
        """Create stock entry on submit"""
        self.create_stock_entry()

    def create_stock_entry(self):
        """Create stock entry for inventory change"""
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Repack"
        stock_entry.company = self.company
        stock_entry.posting_date = self.posting_date
        stock_entry.posting_time = self.posting_time
        stock_entry.from_warehouse = self.warehouse
        stock_entry.to_warehouse = self.warehouse
        stock_entry.purpose = "Repack"
        # Add source item (consumed)
        stock_entry.append(
            "items",
            {
                "item_code": self.source_item,
                "s_warehouse": self.warehouse,
                "qty": self.source_qty,
                # "basic_rate": self.source_rate,
                "serial_no": self.source_serial_no,
                "batch_no": self.source_batch_no,
                "is_finished_item": 0,
                "is_scrap_item": 0,
            },
        )

        # Add target items (produced)
        for item in self.target_items:
            stock_entry.append(
                "items",
                {
                    "item_code": item.item_code,
                    "t_warehouse": self.warehouse,
                    "qty": item.qty,
                    # "basic_rate": item.rate,
                    "serial_no": item.serial_no,
                    "batch_no": item.batch_no,
                    "is_finished_item": 1,
                    "is_scrap_item": 0,
                },
            )

        # Add reference to change inventory
        stock_entry.change_inventory = self.name
        stock_entry.remarks = f"Inventory change from {self.name}: {self.remarks or ''}"

        # # Handle difference amount if any
        # if abs(self.difference_amount) > 0.01:  # If there's a significant difference
        #     # Add difference adjustment item
        #     difference_account = frappe.get_value(
        #         "Company", self.company, "stock_adjustment_account"
        #     )
        #     if difference_account:
        #         stock_entry.additional_costs = [
        #             {
        #                 "expense_account": difference_account,
        #                 "description": f"Inventory Change Difference - {self.name}",
        #                 "amount": abs(self.difference_amount),
        #             }
        #         ]
        stock_entry.flags.ignore_permissions = True
        stock_entry.save()
        stock_entry.submit()
        # frappe.msgprint(f"Stock Entry {stock_entry.name} created successfully")

    def on_cancel(self):
        remove_linked_transactions("Stock Entry", "change_inventory", self.name)

# @frappe.whitelist()
# def get_item_rate(item_code, warehouse=None):
#     """Get item rate for auto-calculation"""
#     if not item_code:
#         return 0

#     # Try to get valuation rate first
#     valuation_rate = frappe.db.sql(
#         """
#         SELECT valuation_rate 
#         FROM `tabStock Ledger Entry` 
#         WHERE item_code = %s 
#         AND warehouse = %s 
#         AND valuation_rate > 0
#         ORDER BY posting_date DESC, posting_time DESC 
#         LIMIT 1
#     """,
#         (item_code, warehouse),
#     )

#     if valuation_rate and valuation_rate[0][0]:
#         return valuation_rate[0][0]

#     # Fallback to standard rate
#     standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
#     return standard_rate or 0


@frappe.whitelist()
def get_item_stock_balance(item_code, warehouse, posting_date=None, posting_time=None):
    """Get current stock balance for an item"""
    if not posting_date:
        posting_date = today()
    if not posting_time:
        posting_time = nowtime()

    balance = get_stock_balance(
        item_code=item_code,
        warehouse=warehouse,
        posting_date=posting_date,
        posting_time=posting_time,
    )

    return balance


@frappe.whitelist()
def create_change_inventory_from_template(source_item, template_name):
    """Create change inventory from predefined template"""
    # This can be extended to support templates for common conversions
    # For now, it's a placeholder for future enhancement
    pass
