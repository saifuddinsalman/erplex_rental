# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RentalSettings(Document):
    def validate(self):
        for row in self.defaults:
            if row.rented_warehouse and row.rental_source_warehouse:
                if row.rented_warehouse == row.rental_source_warehouse:
                    frappe.throw(
                        "Rented Warehouse and Source Warehouse cannot be the same"
                    )

            if row.maintenance_warehouse:
                if row.maintenance_warehouse == row.rented_warehouse:
                    frappe.throw(
                        "Maintenance Warehouse and Rented Warehouse cannot be the same"
                    )
                if row.maintenance_warehouse == row.rental_source_warehouse:
                    frappe.throw(
                        "Maintenance Warehouse and Source Warehouse cannot be the same"
                    )

            if row.rental_income_account:
                account = frappe.get_doc("Account", row.rental_income_account)
                if account.account_type != "Income Account":
                    frappe.throw("Rental Income Account must be an Income Account")

            if row.security_deposit_account:
                account = frappe.get_doc("Account", row.security_deposit_account)
                if account.account_type not in ["Current Liability", "Current Asset"]:
                    frappe.throw(
                        "Security Deposit Account must be a Current Liability or Current Asset Account"
                    )


@frappe.whitelist()
def get_rental_settings():
    """Get rental settings"""
    settings = frappe.get_single("Rental Settings")
    return settings


@frappe.whitelist()
def get_default_warehouses(company):
    warehouses = frappe._dict()
    """Get default warehouses for rental operations"""
    settings = frappe.get_single("Rental Settings")
    warehouse_row = None
    for w in settings.defaults:
        if w.company == company:
            warehouse_row = w
    if warehouse_row:
        warehouses = {
            "rented_warehouse": warehouse_row.rented_warehouse,
            "source_warehouse": warehouse_row.rental_source_warehouse,
            "maintenance_warehouse": warehouse_row.maintenance_warehouse,
        }
    if (not warehouse_row) and (settings.auto_create_warehouses) and (company):
        warehouses = create_missing_warehouses(company, warehouses, settings)
        settings.append(
            "defaults",
            {
                "company": company,
                "rented_warehouse": warehouses.rented_warehouse,
                "rental_source_warehouse": warehouses.source_warehouse,
                "maintenance_warehouse": warehouses.maintenance_warehouse,
            },
        )
        settings.save()
    return warehouses


@frappe.whitelist()
def get_defaults(company):
    defaults = frappe._dict()
    settings = frappe.get_single("Rental Settings")
    defaults_row = None
    for d in settings.defaults:
        if d.company == company:
            defaults_row = d
    if defaults_row:
        defaults = frappe._dict(
            {
                "cost_center": defaults_row.rental_cost_center,
                "income_account": defaults_row.rental_income_account,
                "security_deposit_account": defaults_row.security_deposit_account,
                "rented_warehouse": defaults_row.rented_warehouse,
                "source_warehouse": defaults_row.rental_source_warehouse,
                "maintenance_warehouse": defaults_row.maintenance_warehouse,
            }
        )
    return defaults


def create_missing_warehouses(company, warehouses, settings):
    """Create missing warehouses if auto create is enabled"""
    company_doc = frappe.get_doc("Company", company)
    company_abbr = company_doc.abbr

    # Create rented warehouse if not exists
    if not warehouses.get("rented_warehouse"):
        rented_warehouse_name = f"Rented - {company_abbr}"
        if not frappe.db.exists("Warehouse", rented_warehouse_name):
            warehouse = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": "Rented",
                    "company": company,
                    "is_group": 0,
                }
            )
            warehouse.insert()
            warehouses["rented_warehouse"] = warehouse.name
        else:
            warehouses["rented_warehouse"] = rented_warehouse_name

    # Create maintenance warehouse if not exists
    if not warehouses.get("maintenance_warehouse"):
        maintenance_warehouse_name = f"Maintenance - {company_abbr}"
        if not frappe.db.exists("Warehouse", maintenance_warehouse_name):
            warehouse = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": "Maintenance",
                    "company": company,
                    "is_group": 0,
                }
            )
            warehouse.save()
            warehouses["maintenance_warehouse"] = warehouse.name
        else:
            warehouses["maintenance_warehouse"] = maintenance_warehouse_name

    return warehouses


@frappe.whitelist()
def create_rental_warehouses(company):
    """Manually create rental warehouses for a company"""
    if not company:
        frappe.throw("Company is required")

    company_doc = frappe.get_doc("Company", company)
    company_abbr = company_doc.abbr
    created_warehouses = []

    # Create Rented warehouse
    rented_warehouse_name = f"Rented - {company_abbr}"
    if not frappe.db.exists("Warehouse", rented_warehouse_name):
        rented_warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "Rented",
                "company": company,
                "is_group": 0,
            }
        )
        rented_warehouse.insert()
        created_warehouses.append(rented_warehouse.name)

    # Create Maintenance warehouse
    maintenance_warehouse_name = f"Maintenance - {company_abbr}"
    if not frappe.db.exists("Warehouse", maintenance_warehouse_name):
        maintenance_warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "Maintenance",
                "company": company,
                "is_group": 0,
            }
        )
        maintenance_warehouse.insert()
        created_warehouses.append(maintenance_warehouse.name)

    return {
        "created_warehouses": created_warehouses,
        "message": f"Created {len(created_warehouses)} warehouses for {company}",
    }


@frappe.whitelist()
def create_warehouses_for_all_companies():
    """Create rental warehouses for all companies"""
    companies = frappe.get_all("Company", fields=["name"])
    total_created = 0

    for company in companies:
        result = create_rental_warehouses(company.name)
        total_created += len(result["created_warehouses"])

    return {
        "message": f"Created {total_created} warehouses across {len(companies)} companies"
    }
