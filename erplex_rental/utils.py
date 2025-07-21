import frappe
from frappe.utils import today, add_days, getdate, flt
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

# @frappe.whitelist()
# def get_item_rental_availability(item_code, start_date, end_date, exclude_rental_delivery=None):
#     """Check item availability for rental period"""
#     # Get total stock
#     total_stock = frappe.db.get_value("Bin", {
#         "item_code": item_code,
#         "warehouse": ["not like", "%Rented%"]
#     }, "sum(actual_qty)") or 0

#     # Get currently rented quantity
#     rented_qty = frappe.db.sql("""
#         SELECT COALESCE(SUM(rdi.pending_qty), 0)
#         FROM `tabRental Delivery` rd
#         INNER JOIN `tabRental Delivery Item` rdi ON rd.name = rdi.parent
#         WHERE rd.docstatus = 1
#         AND rd.status NOT IN ('Returned', 'Cancelled')
#         AND rdi.item_code = %s
#         AND rdi.pending_qty > 0
#         AND (
#             (rdi.rental_start_date <= %s AND rdi.rental_end_date >= %s)
#             OR (rdi.rental_start_date <= %s AND rdi.rental_end_date >= %s)
#             OR (rdi.rental_start_date >= %s AND rdi.rental_end_date <= %s)
#         )
#         {}
#     """.format(
#         f"AND rd.name != '{exclude_rental_delivery}'" if exclude_rental_delivery else ""
#     ), (item_code, start_date, start_date, end_date, end_date, start_date, end_date))[0][0]

#     available_qty = total_stock - rented_qty

#     return {
#         "total_stock": total_stock,
#         "rented_qty": rented_qty,
#         "available_qty": max(0, available_qty)
#     }


@frappe.whitelist()
def create_sales_invoice_from_rental_delivery(source_name, target_doc=None):
    """Create Sales Invoice from Rental Delivery"""
    from frappe.model.mapper import get_mapped_doc

    def validate(source, target):
        if source.docstatus != 1:
            frappe.throw("Rental Delivery must be submitted")

    def update_item(source, target, source_parent):
        target.qty = source.qty
        target.rate = source.rate
        target.amount = source.amount
        target.sales_order = source.sales_order
        target.so_detail = source.sales_order_detail
        target.rental_delivery = source_parent.name
        target.rental_delivery_detail = source.name

    def update_target(source, target):
        validate(source, target)
        target.posting_date = today()
        target.due_date = add_days(today(), 30)
        target.run_method("set_missing_values")

    doclist = get_mapped_doc(
        "Rental Delivery",
        source_name,
        {
            "Rental Delivery": {
                "doctype": "Sales Invoice",
                "validation": {"docstatus": ["=", 1], "status": ["!=", "Returned"]},
            },
            "Rental Delivery Item": {
                "doctype": "Sales Invoice Item",
                "condition": lambda doc: flt(doc.pending_qty) > 0,
                "postprocess": update_item,
            },
        },
        target_doc,
        postprocess=update_target,
        ignore_permissions=True,
    )
    return doclist


def create_monthly_rental_invoice():
    orders = frappe.db.get_all(
        "Sales Order",
        {"docstatus": 1, "status": ["!=", "Completed"], "order_type": "Rental"},
    )
    for o in orders:
        rd_docs = get_pending_deliveries(o.name)
        if rd_docs:
            si_doc = make_sales_invoice(o.name)
            si_doc.items = []
            for rd in rd_docs:
                si_doc = create_sales_invoice_from_rental_delivery(rd, si_doc)
            si_doc.flags.ignore_permissions = True
            si_doc.run_method('set_missing_values')
            si_doc.run_method('calculate_taxes_and_totals')
            si_doc.save()
    frappe.db.commit()

def remove_linked_transactions(from_doc, ref_fieldname, ref_value):
    docs = frappe.db.get_all(from_doc, {ref_fieldname: ref_value})
    for d in docs:
        doc = frappe.get_doc(from_doc, d.name)
        if doc.docstatus == 1:
            doc.cancel()
        doc.delete()

def get_pending_deliveries(so):
    data = frappe.db.sql(f"""Select rd.name
    from `tabRental Delivery` rd inner join `tabRental Delivery Item` rdi on rd.name = rdi.parent  
    where rd.docstatus = 1 and rd.status != 'Returned' and rdi.pending_qty > 0 and rdi.sales_order = '{so}' """)
    return list(set([row[0] for row in data]))

def get_total_delivered_qty(so, soi, rd=None, rdi=None):
    conds = ""
    # if rd: conds += f" and rdi.name = '{rd}' "
    # if rdi: conds += f"and rdi.sales_order_detail = '{rdi}' "
    return (
        frappe.db.sql(f"""Select SUM(rdi.qty) as total_delivered_qty
    from `tabRental Delivery` rd inner join `tabRental Delivery Item` rdi on rd.name = rdi.parent  
    where rd.docstatus = 1 and rdi.sales_order = '{so}' and rdi.sales_order_detail = '{soi}' {conds} """)[
            0
        ][0]
        or 0
    )


def get_total_returned_qty(so, soi, rd=None, rdi=None):
    conds = ""
    if rd:
        conds += f" and rri.rental_delivery = '{rd}' "
    if rdi:
        conds += f"and rri.rental_delivery_detail = '{rdi}' "
    return (
        frappe.db.sql(f"""Select (SUM(rri.return_qty)+SUM(rri.maintenance_qty)+SUM(rri.damaged_qty)) as total_returned_qty 
    from `tabRental Return` rr inner join `tabRental Return Item` rri on rr.name = rri.parent  
    where rr.docstatus = 1 and rri.sales_order = '{so}' and rri.sales_order_detail = '{soi}' {conds} """)[
            0
        ][0]
        or 0
    )
