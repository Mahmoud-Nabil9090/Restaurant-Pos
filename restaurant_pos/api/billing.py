"""الدفع: الأوردر -> فاتورة POS (Sales Invoice) متسجلة على الكاشير، + تقفيل الشفت.

التجهيز (مرة واحدة):
    bench --site mahmoud.local execute restaurant_pos.setup.billing.setup_billing
"""
import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from restaurant_pos.api.orders import _order_dict, _lock_and_check, _notify
from restaurant_pos.api.auth import require_admin

PROFILE = "Restaurant POS"
WALK_IN = "Walk-in Customer"
MODES = ("Cash", "Credit Card")


# ---------------------------------------------------------------- pay

@frappe.whitelist()
def pay_order(name, mode_of_payment="Cash", modified=None):
    """دفع أوردر صالة/تيك أواى من الكاشير. أوردرات الدليفرى ممنوعة هنا: بتتحاسب مع الدليفرى مان وقت التسوية.
    modified = آخر نسخة من الأوردر الكاشير شافها؛ لو اتغيّرت من جهاز تاني الدفع بيترفض."""
    _lock_and_check(name, modified)
    order = frappe.get_doc("Restaurant Order", name)
    if order.order_type == "Delivery":
        frappe.throw(_("Delivery orders are paid when settling with the driver"))
    return create_invoice(order, mode_of_payment)


def _tax_account(company):
    """حساب الضريبة (Liability / Tax). بيتعمل لوحده أول مرة تحت Duties and Taxes."""
    abbr = frappe.get_cached_value("Company", company, "abbr")
    name = f"POS Sales Tax - {abbr}"
    if frappe.db.exists("Account", name):
        return name
    parent = (frappe.db.get_value("Account", {"company": company, "account_name": "Duties and Taxes", "is_group": 1}, "name")
              or frappe.db.get_value("Account", {"company": company, "root_type": "Liability", "is_group": 1}, "name"))
    acc = frappe.get_doc({"doctype": "Account", "account_name": "POS Sales Tax", "company": company,
                          "parent_account": parent, "account_type": "Tax", "root_type": "Liability", "is_group": 0})
    acc.flags.ignore_permissions = True
    acc.insert()
    return acc.name


def _apply_adjustments(inv, order):
    """نفس حساب الأوردر: الخصم على الصافي الأول، وبعدين الضريبة على الباقي."""
    pct = flt(order.get("discount_percent"))
    amount = flt(order.get("discount_amount"))
    if pct or amount:
        inv.apply_discount_on = "Net Total"
        if pct:
            inv.additional_discount_percentage = pct
        else:
            inv.discount_amount = amount
    tax = flt(order.get("tax_percent"))
    if tax:
        inv.append("taxes", {"charge_type": "On Net Total", "account_head": _tax_account(inv.company),
                             "description": f"Tax {tax:g}%", "rate": tax})


def create_invoice(order, mode_of_payment="Cash"):
    """يعمل فاتورة POS مدفوعة للأوردر ويقفله. الفاتورة بتتسجل على اليوزر الحالي (اللي بيستلم الفلوس).
    قفل الصف بيمنع الدفع المزدوج: لو جهازين دوسوا Pay معًا، التاني بيلاقيه Billed ويترفض."""
    if mode_of_payment not in MODES:
        frappe.throw(_("Unknown payment method"))

    # قفل الأوردر لحد آخر الطلب، وبعدها نقرا نسخته الأخيرة (أصنافه وحالته)
    _lock_and_check(order.name)
    order.reload()
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
        _apply_adjustments(inv, order)

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
    _notify(order, "billed")
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
