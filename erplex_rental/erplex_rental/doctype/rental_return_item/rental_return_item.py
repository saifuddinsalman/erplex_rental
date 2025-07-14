# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import flt

class RentalReturnItem(Document):
    def validate(self):
        pass