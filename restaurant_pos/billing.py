"""الدفع: الأوردر -> فاتورة POS (Sales Invoice) متسجلة على الكاشير، + تقفيل الشفت.

التجهيز (مرة واحدة):
    bench --site mahmoud.local execute restaurant_pos.billing.setup_billing
"""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from restaurant_pos.api import _order_dict
from restaurant_pos.auth import require_admin

PROFILE = "Restaurant POS"
WALK_IN = "Walk-in Customer"
MODES = ("Cash", "Credit Card")


# ---------------------------------------------------------------- setup

def _settlement_doctype():
    if frappe.db.exists("DocType", "Cashier Settlement"):
        return
    money = lambda f, l: {"fieldname": f, "label": l, "fieldtype": "Currency", "read_only": 1}
    frappe.get_doc({
        "doctype": "DocType", "name": "Cashier Settlement", "module": "Restaurant POS",
        "autoname": "format:CS-{YYYY}-{#####}", "sort_field": "creation", "sort_order": "DESC",
        "fields": [
            {"fieldname": "cashier", "label": "Cashier", "fieldtype": "Link", "options": "User", "read_only": 1, "in_list_view": 1},
            {"fieldname": "settled_on", "label": "Settled On", "fieldtype": "Datetime", "read_only": 1, "in_list_view": 1},
            {"fieldname": "settled_by", "label": "Settled By", "fieldtype": "Link", "options": "User", "read_only": 1},
            {"fieldname": "invoice_count", "label": "Invoices", "fieldtype": "Int", "read_only": 1},
            money("total_sales", "Total Sales") | {"in_list_view": 1},
            money("cash_total", "Cash"), money("card_total", "Card"),
            money("counted_cash", "Counted Cash"), money("difference", "Difference"),
            {"fieldname": "notes", "label": "Notes", "fieldtype": "Small Text"},
        ],
        "permissions": [
            {"role": "Restaurant Admin", "read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1},
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1},
        ],
    }).insert(ignore_permissions=True)


def _custom_fields():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({"Sales Invoice": [
        {"fieldname": "rp_section", "label": "Restaurant POS", "fieldtype": "Section Break", "insert_after": "remarks", "collapsible": 1},
        {"fieldname": "rp_order", "label": "Restaurant Order", "fieldtype": "Link", "options": "Restaurant Order", "insert_after": "rp_section", "read_only": 1},
        {"fieldname": "rp_cashier", "label": "Cashier", "fieldtype": "Link", "options": "User", "insert_after": "rp_order", "read_only": 1, "in_standard_filter": 1},
        {"fieldname": "rp_settlement", "label": "Cashier Settlement", "fieldtype": "Link", "options": "Cashier Settlement", "insert_after": "rp_cashier", "read_only": 1},
    ]}, update=True)


def _account(company, kinds):
    for kind in kinds:
        acc = frappe.db.get_value("Account", {"company": company, "account_type": kind, "is_group": 0}, "name")
        if acc:
            return acc


def setup_billing():
    company = frappe.defaults.get_global_default("company")
    c = frappe.get_cached_doc("Company", company)
    cash = c.default_cash_account or _account(company, ["Cash"])
    bank = c.default_bank_account or _account(company, ["Bank"]) or cash
    if not cash:
        frappe.throw(_("No cash account found for company {0}").format(company))

    for mode, acc in (("Cash", cash), ("Credit Card", bank)):
        if not frappe.db.exists("Mode of Payment", mode):
            frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode,
                            "type": "Cash" if mode == "Cash" else "Bank"}).insert()
        mop = frappe.get_doc("Mode of Payment", mode)
        mop.enabled = 1
        if not any(r.company == company for r in mop.accounts):
            mop.append("accounts", {"company": company, "default_account": acc})
        mop.save()

    if not frappe.db.exists("Customer", WALK_IN):
        # لازم مجموعة عملاء وإقليم من النوع العادي (مش Group)
        group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
        territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")
        frappe.get_doc({
            "doctype": "Customer", "customer_name": WALK_IN, "customer_type": "Individual",
            "customer_group": group, "territory": territory,
        }).insert()

    warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
    if not frappe.db.exists("POS Profile", PROFILE):
        frappe.get_doc({
            "doctype": "POS Profile", "name": PROFILE, "company": company, "customer": WALK_IN,
            "currency": c.default_currency, "warehouse": warehouse,
            "selling_price_list": frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name"),
            "write_off_account": c.write_off_account or _account(company, ["Round Off"]) or cash,
            "write_off_cost_center": c.cost_center, "write_off_limit": 0, "update_stock": 0,
            "payments": [{"mode_of_payment": "Cash", "default": 1}, {"mode_of_payment": "Credit Card"}],
        }).insert()

    _settlement_doctype()  # لازم قبل الحقول لأن حقل rp_settlement بيرتبط بيه
    _custom_fields()
    frappe.db.commit()
    print("billing ready: POS Profile =", PROFILE, "| cash account =", cash, "| card account =", bank)


# ---------------------------------------------------------------- pay

@frappe.whitelist()
def pay_order(name, mode_of_payment="Cash"):
    """دفع أوردر صالة/تيك أواى من الكاشير. أوردرات الدليفرى ممنوعة هنا: بتتحاسب مع الدليفرى مان وقت التسوية."""
    order = frappe.get_doc("Restaurant Order", name)
    if order.order_type == "Delivery":
        frappe.throw(_("Delivery orders are paid when settling with the driver"))
    return create_invoice(order, mode_of_payment)


def create_invoice(order, mode_of_payment="Cash"):
    """يعمل فاتورة POS مدفوعة للأوردر ويقفله. الفاتورة بتتسجل على اليوزر الحالي (اللي بيستلم الفلوس)."""
    if mode_of_payment not in MODES:
        frappe.throw(_("Unknown payment method"))
    if order.status in ("Billed", "Cancelled"):
        frappe.throw(_("Order {0} is already {1}").format(order.name, order.status))
    rows = [r for r in order.items if r.kitchen_status != "Cancelled"]
    if not rows:
        frappe.throw(_("Order has no items"))

    cashier = frappe.session.user
    # الكاشير مش لازم يكون عنده صلاحيات حسابات؛ نعمل الفاتورة بصلاحية النظام ونسجّلها باسمه
    frappe.set_user("Administrator")
    try:
        inv = frappe.new_doc("Sales Invoice")
        inv.update({
            "company": order.company, "is_pos": 1, "pos_profile": PROFILE, "update_stock": 0,
            "customer": frappe.db.get_value("POS Profile", PROFILE, "customer"),
            "posting_date": nowdate(), "ignore_pricing_rule": 1, "disable_rounded_total": 1,
            "rp_order": order.name, "rp_cashier": cashier,
            "remarks": f"{order.name} | {order.order_type}" + (f" | Table {order.table}" if order.table else ""),
        })
        for r in rows:
            inv.append("items", {"item_code": r.item, "qty": r.qty, "rate": r.rate, "item_name": r.item_name})
        if flt(order.discount_amount):
            inv.apply_discount_on = "Grand Total"
            inv.discount_amount = flt(order.discount_amount)

        inv.flags.ignore_permissions = True
        inv.set_missing_values()          # بيجيب طرق الدفع من الـ POS Profile
        inv.calculate_taxes_and_totals()
        inv.set("payments", [p for p in inv.payments if p.mode_of_payment == mode_of_payment])
        if not inv.payments:
            frappe.throw(_("{0} is not enabled in POS Profile {1}").format(mode_of_payment, PROFILE))
        inv.payments[0].amount = inv.grand_total
        inv.insert()
        inv.submit()
    finally:
        frappe.set_user(cashier)

    order.status = "Billed"
    order.sales_invoice = inv.name
    order.flags.ignore_permissions = True
    order.save()
    return {"invoice": inv.name, "total": inv.grand_total, "mode": mode_of_payment, "order": _order_dict(order)}


# ---------------------------------------------------------------- shift

def shift_summary(user):
    """ملخص فواتير اليوزر اللي لسه متقفلتش (محتاجة تسوية)."""
    where = "si.docstatus = 1 and si.rp_cashier = %s and ifnull(si.rp_settlement, '') = ''"
    modes = frappe.db.sql(
        f"""select sip.mode_of_payment as mode, sum(sip.amount) as total
            from `tabSales Invoice` si join `tabSales Invoice Payment` sip on sip.parent = si.name
            where {where} group by sip.mode_of_payment""", user, as_dict=True)
    invoices = frappe.db.sql(
        f"""select si.name, si.rp_order as `order`, si.grand_total as total, si.creation
            from `tabSales Invoice` si where {where} order by si.creation desc limit 100""", user, as_dict=True)
    by = {m.mode: flt(m.total) for m in modes}
    count = frappe.db.sql(f"select count(*) from `tabSales Invoice` si where {where}", user)[0][0]
    return {
        "user": user, "invoice_count": count,
        "cash": by.get("Cash", 0), "card": by.get("Credit Card", 0),
        "total": sum(by.values()), "invoices": invoices,
    }


@frappe.whitelist()
def my_shift():
    return shift_summary(frappe.session.user)


@frappe.whitelist()
def settle_cashier(user, counted_cash=None, notes=None):
    """الأدمن بيقفل حساب كاشير: يسجّل التسوية ويعلّم فواتيره."""
    require_admin()
    s = shift_summary(user)
    if not s["invoice_count"]:
        frappe.throw(_("No unsettled invoices for {0}").format(user))
    counted = flt(counted_cash) if counted_cash not in (None, "") else s["cash"]
    doc = frappe.get_doc({
        "doctype": "Cashier Settlement", "cashier": user, "settled_by": frappe.session.user,
        "settled_on": now_datetime(), "invoice_count": s["invoice_count"], "total_sales": s["total"],
        "cash_total": s["cash"], "card_total": s["card"], "counted_cash": counted,
        "difference": counted - s["cash"], "notes": notes,
    }).insert(ignore_permissions=True)
    frappe.db.sql(
        """update `tabSales Invoice` set rp_settlement = %s
           where docstatus = 1 and rp_cashier = %s and ifnull(rp_settlement, '') = ''""", (doc.name, user))
    return doc.as_dict()
