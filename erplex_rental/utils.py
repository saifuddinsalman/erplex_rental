import frappe
from frappe.utils import today, add_days, getdate, flt, date_diff, add_to_date, cstr, get_first_day
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice


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
        # target.rental_delivery = source_parent.name
        # target.rental_delivery_detail = source.name

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


def get_ongoing_rental_orders_for_invoicing():
    data = (
        frappe.db.sql(
            """Select so.name 
    from `tabSales Order` so inner join `tabSales Order Item` soi on so.name = soi.parent
    where so.order_type = 'Rental' and so.docstatus = 1 and so.status not in ('Completed', 'Cancelled')
    and soi.custom_rental_returned_qty < soi.custom_rental_delivered_qty
    """,
            as_dict=True,
        )
        or []
    )
    return list(set([row.name for row in data]))


def get_unbilled_completed_rental_orders(order=None):
    conds = ""
    if order:
        conds += f" and so.name = '{order}' "
    data = (
        frappe.db.sql(
            f"""Select so.name 
    from `tabSales Order` so inner join `tabSales Order Item` soi on so.name = soi.parent
    where so.order_type = 'Rental' and so.docstatus = 1 and so.status = 'Completed'
    and soi.custom_rental_returned_qty = soi.custom_rental_delivered_qty {conds}
    and (custom_last_billed_date is Null or custom_last_billed_date = "" or custom_last_billed_date < (Select rr.posting_date 
    from `tabRental Return` rr inner join `tabRental Return Item` rri on rr.name = rri.parent
    where rri.sales_order = so.name and rr.docstatus = 1 Order By rr.posting_date DESC, rr.posting_time DESC, rr.creation DESC LIMIT 1))
    """,
            as_dict=True,
        )
        or []
    )
    return list(set([row.name for row in data]))


def get_last_rental_return(so_name):
    last_rental_return = None
    data = frappe.db.sql(f""" Select rr.name 
    from `tabRental Return` rr inner join `tabRental Return Item` rri on rr.name = rri.parent
    where rri.sales_order = '{so_name}' and rr.docstatus = 1 Order By rr.posting_date DESC, rr.posting_time DESC, rr.creation DESC LIMIT 1
    """)
    if data:
        last_rental_return = data[0][0]
    return last_rental_return


def create_ongoing_rental_invoices():
    for so_name in get_ongoing_rental_orders_for_invoicing():
        so = frappe.get_doc("Sales Order", so_name)
        si_doc = make_sales_invoice(so_name)
        si_doc.update_stock = 0
        si_doc.items = []
        for soi in so.items:
            avg_daily_rate = soi.rate / 30
            days = 0
            if soi.custom_rental_delivered_qty != soi.custom_rental_returned_qty:
                days = date_diff(
                    getdate(), so.custom_last_billed_date or so.transaction_date
                )
            elif soi.custom_rental_delivered_qty == soi.custom_rental_returned_qty:
                return_date = frappe.db.get_value(
                    "Rental Return", get_last_rental_return(so_name), "return_date"
                )
                days = date_diff(
                    return_date, so.custom_last_billed_date or so.transaction_date
                )
            if days > 0:
                si_doc.append(
                    "items",
                    {
                        "item_code": soi.item_code,
                        "qty": soi.custom_rental_delivered_qty,
                        "rate": (avg_daily_rate * days),
                        "sales_order": soi.parent,
                        "so_detail": soi.name,
                    },
                )
        if si_doc.items:
            si_doc.flags.ignore_permissions = True
            si_doc.run_method("set_missing_values")
            si_doc.run_method("calculate_taxes_and_totals")
            si_doc.save()
        frappe.db.commit()


def create_unbilled_completed_rental_invoices(order=None):
    for so_name in get_unbilled_completed_rental_orders(order):
        so = frappe.get_doc("Sales Order", so_name)
        si_doc = make_sales_invoice(so_name)
        si_doc.update_stock = 0
        si_doc.items = []
        if so.custom_last_billed_date:
            rr = frappe.get_doc("Rental Return", get_last_rental_return(so_name))
            for rri in rr.items:
                soi_rate = frappe.db.get_value(
                    "Sales Order Item", rri.sales_order_detail, "rate"
                )
                avg_daily_rate = soi_rate / 30
                days = date_diff(
                    rr.return_date, so.custom_last_billed_date or so.transaction_date
                )
                si_doc.append(
                    "items",
                    {
                        "item_code": rri.item_code,
                        "qty": rri.return_qty + rri.maintenance_qty + rri.damaged_qty,
                        "rate": avg_daily_rate * days,
                        "sales_order": rri.sales_order,
                        "so_detail": rri.sales_order_detail,
                    },
                )
        else:
            for soi in so.items:
                avg_daily_rate = soi.rate / 30
                days = date_diff(
                    getdate(), so.custom_last_billed_date or so.transaction_date
                )
                if days > 0:
                    si_doc.append(
                        "items",
                        {
                            "item_code": soi.item_code,
                            "qty": soi.custom_rental_delivered_qty,
                            "rate": avg_daily_rate * days,
                            "sales_order": soi.parent,
                            "so_detail": soi.name,
                        },
                    )
        if si_doc.items:
            si_doc.flags.ignore_permissions = True
            si_doc.run_method("set_missing_values")
            si_doc.run_method("calculate_taxes_and_totals")
            si_doc.save()
        frappe.db.commit()


def create_monthly_rental_invoice():
    create_ongoing_rental_invoices()
    create_unbilled_completed_rental_invoices()


def get_ongoing_rental_orders_for_purchase_invoicing():
    data = (
        frappe.db.sql(
            """Select so.name 
    from `tabPurchase Order` so inner join `tabPurchase Order Item` soi on so.name = soi.parent
    where so.cutom_order_type = 'Rental' and so.docstatus = 1 and soi.returned_qty < soi.qty
    and so.per_received > 0 """,
            as_dict=True,
        )
        or []
    )
    return list(set([row.name for row in data]))


def get_unbilled_completed_rental_purchase_orders(order=None):
    conds = ""
    if order:
        conds += f" and so.name = '{order}' "
    data = (
        frappe.db.sql(
            f"""Select so.name from `tabPurchase Order` so inner join `tabPurchase Order Item` soi on so.name = soi.parent
            where so.cutom_order_type = 'Rental' and so.docstatus = 1 and soi.returned_qty = soi.qty {conds}
            (Select pi.posting_date from `tabPurchase Invoice` pi inner join `tabPurchase Invoice Item` pii on pi.name = pii.parent 
            where pii.purchase_order = so.name and pi.docstatus = 1 Order by pi.posting_date desc limit 1) as last_billed_date""",
            as_dict=True,
        )
        or []
    )
    return list(set([row.name for row in data]))


def create_ongoing_rental_purchase_invoices():
    for so_name in get_ongoing_rental_orders_for_purchase_invoicing():
        so = frappe.get_doc("Sales Order", so_name)
        si_doc = make_sales_invoice(so_name)
        si_doc.update_stock = 0
        si_doc.items = []
        for soi in so.items:
            avg_daily_rate = soi.rate / 30
            days = 0
            if soi.custom_rental_delivered_qty != soi.custom_rental_returned_qty:
                days = date_diff(
                    getdate(), so.custom_last_billed_date or so.transaction_date
                )
            elif soi.custom_rental_delivered_qty == soi.custom_rental_returned_qty:
                return_date = frappe.db.get_value(
                    "Rental Return", get_last_rental_return(so_name), "return_date"
                )
                days = date_diff(
                    return_date, so.custom_last_billed_date or so.transaction_date
                )
            if days > 0:
                si_doc.append(
                    "items",
                    {
                        "item_code": soi.item_code,
                        "qty": soi.custom_rental_delivered_qty,
                        "rate": (avg_daily_rate * days),
                        "sales_order": soi.parent,
                        "so_detail": soi.name,
                    },
                )
        if si_doc.items:
            si_doc.flags.ignore_permissions = True
            si_doc.run_method("set_missing_values")
            si_doc.run_method("calculate_taxes_and_totals")
            si_doc.save()
        frappe.db.commit()


def create_unbilled_completed_rental_purchase_invoices(order=None):
    for so_name in get_unbilled_completed_rental_purchase_orders(order):
        so = frappe.get_doc("Sales Order", so_name)
        si_doc = make_sales_invoice(so_name)
        si_doc.update_stock = 0
        si_doc.items = []
        if so.custom_last_billed_date:
            rr = frappe.get_doc("Rental Return", get_last_rental_return(so_name))
            for rri in rr.items:
                soi_rate = frappe.db.get_value(
                    "Sales Order Item", rri.sales_order_detail, "rate"
                )
                avg_daily_rate = soi_rate / 30
                days = date_diff(
                    rr.return_date, so.custom_last_billed_date or so.transaction_date
                )
                si_doc.append(
                    "items",
                    {
                        "item_code": rri.item_code,
                        "qty": rri.return_qty + rri.maintenance_qty + rri.damaged_qty,
                        "rate": avg_daily_rate * days,
                        "sales_order": rri.sales_order,
                        "so_detail": rri.sales_order_detail,
                    },
                )
        else:
            for soi in so.items:
                avg_daily_rate = soi.rate / 30
                days = date_diff(
                    getdate(), so.custom_last_billed_date or so.transaction_date
                )
                if days > 0:
                    si_doc.append(
                        "items",
                        {
                            "item_code": soi.item_code,
                            "qty": soi.custom_rental_delivered_qty,
                            "rate": avg_daily_rate * days,
                            "sales_order": soi.parent,
                            "so_detail": soi.name,
                        },
                    )
        if si_doc.items:
            si_doc.flags.ignore_permissions = True
            si_doc.run_method("set_missing_values")
            si_doc.run_method("calculate_taxes_and_totals")
            si_doc.save()
        frappe.db.commit()


def create_monthly_rental_purchase_invoice():
    create_ongoing_rental_purchase_invoices()
    create_unbilled_completed_rental_purchase_invoices()


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


def get_total_deposit_used(so, soi=None, rd=None, rdi=None):
    conds = ""
    if soi:
        conds += f" and rri.sales_order_detail = '{soi}' "
    if rd:
        conds += f" and rri.rental_delivery = '{rd}' "
    if rdi:
        conds += f" and rri.rental_delivery_detail = '{rdi}' "
    return (
        frappe.db.sql(f"""Select (SUM(rri.maintenance_amount)+SUM(rri.damaged_amount)) as total_deposit_used 
    from `tabRental Return` rr inner join `tabRental Return Item` rri on rr.name = rri.parent  
    where rr.docstatus = 1 and rri.sales_order = '{so}' {conds} """)[0][0]
        or 0
    )


def get_last_billed_date(so_name):
    last_billed_date = None
    si_data = frappe.db.sql(f"""Select si.posting_date
    from `tabSales Invoice` si inner join `tabSales Invoice Item` sii on si.name = sii.parent
    where si.docstatus = 1 and sii.sales_order = '{so_name}' Order By si.posting_date DESC, si.posting_time DESC, si.creation DESC LIMIT 1""")
    if si_data:
        last_billed_date = si_data[0][0]
    return last_billed_date


def update_last_billed_date_in_so(so_name):
    frappe.db.set_value(
        "Sales Order", so_name, "custom_last_billed_date", get_last_billed_date(so_name)
    )
    frappe.db.commit()

def get_rental_order_per_day_rate(so, so_detail, item):
    rate = frappe.db.get_value("Sales Order Item", so_detail, "rate") or 0
    if not rate:
        rate = frappe.db.get_value("Sales Order Item", {"parent": so, "item_code": item}, "rate") or 0
    return flt(rate/30, 2)


def get_rental_opening_qty(so_name, item, date):
    conds = ""
    if date:
        conds += f" and p.posting_date < '{date}' "
    if item:
        conds += f" and c.item_code = '{item}' "
    if so_name:
        conds += f" and c.sales_order = '{so_name}' "
    delivered_qty = (
        frappe.db.sql(f"""Select SUM(c.qty) as total_delivered_qty
    from `tabRental Delivery` p inner join `tabRental Delivery Item` c on p.name = c.parent  
    where p.docstatus = 1 {conds} """)[0][0]
        or 0
    )
    returned_qty = (
        frappe.db.sql(f"""Select (SUM(c.return_qty)+SUM(c.maintenance_qty)+SUM(c.damaged_qty)) as total_returned_qty 
    from `tabRental Return` p inner join `tabRental Return Item` c on p.name = c.parent  
    where p.docstatus = 1 {conds} """)[0][0]
        or 0
    )
    return delivered_qty - returned_qty

def get_deliveries_and_returns(so_name, item, from_date, to_date):
    conds = ""
    if from_date:
        conds += f" and p.posting_date >= '{from_date}' "
    if to_date:
        conds += f" and p.posting_date <= '{to_date}' "
    if item:
        conds += f" and c.item_code = '{item}' "
    if so_name:
        conds += f" and c.sales_order = '{so_name}' "
    deliveries = frappe.db.sql(f"""Select p.name, p.posting_date, c.qty
    from `tabRental Delivery` p inner join `tabRental Delivery Item` c on p.name = c.parent  
    where p.docstatus = 1 {conds} """, as_dict=True) or []
    returns = frappe.db.sql(f"""Select p.name, p.posting_date, -1*(c.return_qty+c.maintenance_qty+c.damaged_qty) as qty 
    from `tabRental Return` p inner join `tabRental Return Item` c on p.name = c.parent  
    where p.docstatus = 1 {conds} """, as_dict=True) or []
    data = deliveries + returns
    return sorted(data, key=lambda x: x['posting_date'])

def get_rental_inv_opening_date(so_name, date):
    opening_date = date
    if cstr(date).split("-")[-1] == "01":
        opening_date = get_first_day(add_to_date(date, days=-2)) 
    else:
        opening_date = get_first_day(date)
    # order_date = frappe.db.get_value("Sales Order", so_name, "transaction_date")
    # return order_date if order_date > opening_date else opening_date
    return opening_date