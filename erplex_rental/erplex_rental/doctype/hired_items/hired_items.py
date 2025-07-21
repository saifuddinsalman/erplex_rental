# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate
from erplex_rental.erplex_rental.doctype.rental_settings.rental_settings import (
	get_default_warehouses,
)
from erplex_rental.utils import remove_linked_transactions

class HiredItems(Document):
	def validate(self):
		self.validate_items()
		self.calculate_totals()
		self.set_status()
		if self.is_return:
			self.validate_return()

	def validate_items(self):
		"""Validate items in the table"""
		if not self.items:
			frappe.throw(_("Please add at least one item"))
		
		for item in self.items:
			if flt(item.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0").format(item.idx))
			
			if flt(item.rate) < 0:
				frappe.throw(_("Row {0}: Rate cannot be negative").format(item.idx))
			
			# Calculate amount
			item.amount = flt(item.qty) * flt(item.rate)

	def validate_return(self):
		"""Validate return document"""
		if not self.return_against:
			frappe.throw(_("Return Against is mandatory for return documents"))
		
		# Get original document
		original_doc = frappe.get_doc("Hired Items", self.return_against)
		
		if original_doc.docstatus != 1:
			frappe.throw(_("Cannot create return against unsubmitted document"))
		for item in self.items:
			original_item = None
			for orig_item in original_doc.items:
				if orig_item.item_code == item.item_code:
					original_item = orig_item
					break
			if not original_item:
				frappe.throw(_("Row {0}: Item {1} not found in original document").format(
					item.idx, item.item_code))
			# Check if return qty exceeds available qty
			available_qty = flt(original_item.qty) - flt(original_item.returned_qty)
			if flt(item.qty) > available_qty:
				frappe.throw(_("Row {0}: Return qty {1} cannot exceed available qty {2}").format(
					item.idx, item.qty, available_qty))

	def calculate_totals(self):
		"""Calculate total quantity and amount"""
		self.total_qty = sum(flt(item.qty) for item in self.items)
		self.total_amount = sum(flt(item.amount) for item in self.items)

	def set_status(self):
		"""Set document status based on submission and returns"""
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 1:
			if self.is_return:
				self.status = "Submitted"
			else:
				# Check if any items have been returned
				total_returned = sum(flt(item.returned_qty) for item in self.items)
				if total_returned == 0:
					self.status = "Submitted"
				elif total_returned < self.total_qty:
					self.status = "Partially Returned"
				else:
					self.status = "Returned"

	def on_submit(self):
		"""Actions to perform on document submission"""
		self.create_stock_entry()
		
		if self.is_return:
			self.update_original_document()

	def create_stock_entry(self):
		warehouses = get_default_warehouses(self.company)
		warehouse = warehouses.get("source_warehouse")
		if self.is_return:
			stock_entry_type = "Material Issue"
			from_warehouse = warehouse
			to_warehouse = None
		else:
			stock_entry_type = "Material Receipt"
			from_warehouse = None
			to_warehouse = warehouse

		stock_entry = frappe.new_doc("Stock Entry")
		stock_entry.stock_entry_type = stock_entry_type
		stock_entry.posting_date = self.posting_date
		stock_entry.set_posting_time = 1
		stock_entry.company = self.company
		stock_entry.custom_hired_items = self.name
		for item in self.items:
			se_item = stock_entry.append("items")
			se_item.item_code = item.item_code
			se_item.qty = item.qty
			se_item.basic_rate = item.rate
			if from_warehouse:
				se_item.s_warehouse = from_warehouse
			if to_warehouse:
				se_item.t_warehouse = to_warehouse
		stock_entry.flags.ignore_permissions = True
		stock_entry.save()
		stock_entry.submit()

	def update_original_document(self, is_cancelled=False):
		"""Update original document with return quantities"""
		if not self.return_against:
			return
		original_doc = frappe.get_doc("Hired Items", self.return_against)
		for return_item in self.items:
			for orig_item in original_doc.items:
				if (orig_item.name == return_item.hired_item_detail):
					if is_cancelled:
						orig_item.returned_qty = flt(orig_item.returned_qty) - flt(return_item.qty)
					else:
						orig_item.returned_qty = flt(orig_item.returned_qty) + flt(return_item.qty)
					break
		original_doc.set_status()
		original_doc.save()		
		# frappe.msgprint(_("Original document {0} updated successfully").format(
		# 	frappe.get_desk_link("Hired Items", self.return_against)))

	@frappe.whitelist()
	def create_return(self):
		"""Create return document against this hired items"""
		if self.docstatus != 1:
			frappe.throw(_("Cannot create return against unsubmitted document"))
		
		if self.is_return:
			frappe.throw(_("Cannot create return against a return document"))
		
		# Check if there are items available for return
		has_returnable_items = False
		for item in self.items:
			available_qty = flt(item.qty) - flt(item.returned_qty)
			if available_qty > 0:
				has_returnable_items = True
				break
		
		if not has_returnable_items:
			frappe.throw(_("All items have been returned"))
		
		# Create return document
		return_doc = frappe.new_doc("Hired Items")
		return_doc.company = self.company
		return_doc.supplier = self.supplier
		return_doc.posting_date = getdate()
		return_doc.is_return = 1
		return_doc.return_against = self.name
		
		# Add items with available quantities
		for item in self.items:
			available_qty = flt(item.qty) - flt(item.returned_qty)
			if available_qty > 0:
				return_item = return_doc.append("items")
				return_item.item_code = item.item_code
				return_item.item_name = item.item_name
				return_item.description = item.description
				return_item.qty = available_qty
				return_item.rate = item.rate
				return_item.hired_item_detail = item.name
		return_doc.save()
		
		# frappe.msgprint(_("Return document {0} created successfully").format(
		# 	frappe.get_desk_link("Hired Items", return_doc.name)))
		
		return return_doc.name

	def on_cancel(self):
		remove_linked_transactions("Stock Entry", "custom_hired_items", self.name)
		if self.is_return:
			self.update_original_document(True)
