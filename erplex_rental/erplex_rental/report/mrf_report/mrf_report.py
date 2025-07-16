# Copyright (c) 2025, ERPlexSolutions and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, cstr


def execute(filters=None):
    columns, data = [], []
    if not filters.get("sales_order"):
        frappe.throw("Please select a Sales Order")
    so = frappe.get_doc("Sales Order", filters.get("sales_order"))
    validate_sales_order(so)
    deliveries_data, deliveries = get_deliveries(so)
    returns_data, returns = get_returns(so)
    columns = get_columns(deliveries, returns)
    HeaderRow = {"description": so.customer}
    SubHeaderRow = {"description": date_to_user(so.transaction_date)}
    for d in deliveries:
        d_id, d_date = d
        HeaderRow[frappe.scrub(d_id)] = d_id
        SubHeaderRow[frappe.scrub(d_id)] = date_to_user(d_date)
    for r in returns:
        r_id, r_date = r
        HeaderRow[frappe.scrub(r_id)] = r_id
        SubHeaderRow[frappe.scrub(r_id)] = date_to_user(r_date)
    data.append(HeaderRow)
    data.append(SubHeaderRow)
    data.append({})
    for soi in so.items:
        row = {
            "description": soi.item_code,
            "order_qty": soi.qty,
            "balance_return": 0,
            "balance_delivery": 0,
            "total_delivered_qty": 0,
            "total_returned_qty": 0,
        }
        for dd in deliveries_data:
            if dd.item_code == soi.item_code:
                k = frappe.scrub(dd.name)
                if k not in row:
                    row[k] = 0
                row[k] += flt(dd.qty)
                row["total_delivered_qty"] += flt(dd.qty)
        for rd in returns_data:
            if rd.item_code == soi.item_code:
                k = frappe.scrub(rd.name)
                if k not in row:
                    row[k] = 0
                row[k] += flt(rd.return_qty) + flt(rd.damaged_qty)
                row["total_returned_qty"] += flt(rd.return_qty) + flt(rd.damaged_qty)
        row["balance_delivery"] = row.get("order_qty") - row.get("total_delivered_qty")
        row["balance_return"] = row.get("total_delivered_qty") - row.get(
            "total_returned_qty"
        )
        data.append(row)
    return columns, data

def date_to_user(date_str):
    return "-".join(reversed(cstr(date_str).split("-")))

def validate_sales_order(so):
    if not so:
        frappe.throw("Sales Order not found")
    if so.docstatus != 1:
        return frappe.throw("Sales Order is not in submitted state")
    if so.order_type != "Rental":
        return frappe.throw("Sales Order is not a Rental Order")


def get_deliveries(so):
    unique_ids = []
    data = (
        frappe.db.sql(
            f"""Select rd.name, rd.posting_date, rdi.item_code, rdi.qty
	from `tabRental Delivery` rd inner join `tabRental Delivery Item` rdi on rd.name = rdi.parent  
	where rd.docstatus = 1 and rdi.sales_order = '{so.name}' order by rd.posting_date """,
            as_dict=1,
        )
        or []
    )
    for d in data:
        if d.name not in unique_ids:
            unique_ids.append([d.name, d.posting_date])
    return data, unique_ids


def get_returns(so):
    unique_ids = []
    data = (
        frappe.db.sql(
            f"""Select rr.name, rr.posting_date, rri.item_code, rri.return_qty, rri.damaged_qty
	from `tabRental Return` rr inner join `tabRental Return Item` rri on rr.name = rri.parent  
	where rr.docstatus = 1 and rri.sales_order = '{so.name}' order by rr.posting_date """,
            as_dict=1,
        )
        or []
    )
    for d in data:
        if d.name not in unique_ids:
            unique_ids.append([d.name, d.posting_date])
    return data, unique_ids


def get_columns(deliveries, returns):
    columns = [
        {
            "fieldname": "art",
            "label": "Art #",
            "fieldtype": "Data",
            "width": 100,
        },
        {
            "fieldname": "description",
            "label": "Description",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "fieldname": "order_qty",
            "label": "Order QTY",
            "fieldtype": "Data",
            "width": 150,
        },
    ]
    for idx, delivery in enumerate(deliveries):
        idxxx = idx + 1
        columns.append(
            {
                "fieldname": frappe.scrub(delivery[0]),
                "label": f"Delivery {idxxx}",
                "fieldtype": "Data",
                "width": 150,
            }
        )
    columns.append(
        {
            "fieldname": "total_delivered_qty",
            "label": "Total Delivered QTY",
            "fieldtype": "Data",
            "width": 150,
        }
    )
    columns.append(
        {
            "fieldname": "balance_delivery",
            "label": "Balance for Delivery",
            "fieldtype": "Data",
            "width": 150,
        }
    )
    for idx, _return in enumerate(returns):
        idxxx = idx + 1
        columns.append(
            {
                "fieldname": frappe.scrub(_return[0]),
                "label": f"Return {idxxx}",
                "fieldtype": "Data",
                "width": 150,
            }
        )
    columns.append(
        {
            "fieldname": "total_returned_qty",
            "label": "Total Returned QTY",
            "fieldtype": "Data",
            "width": 150,
        }
    )
    columns.append(
        {
            "fieldname": "balance_return",
            "label": "Balance for Return",
            "fieldtype": "Data",
            "width": 150,
        }
    )
    return columns
