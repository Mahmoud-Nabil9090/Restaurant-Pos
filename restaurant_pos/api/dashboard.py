"""تقارير سريعة للأدمن: لوحة الإحصائيات + تقرير نهاية اليوم (End Day).

كل تقرير بيتحسب بكام استعلام تجميعي (SQL) بدل ما نقرا الأوردرات واحد واحد، علشان يفتح بسرعة.
المبيعات كلها من فواتير Sales Invoice المدفوعة (docstatus = 1) المربوطة بأوردرات المطعم.
"""
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from restaurant_pos.api.auth import require_admin

ORDER_TYPES = ("Dine In", "Takeaway", "Delivery")
ACTIVE = ("Open", "Sent to Kitchen", "Served")


def _range(date_from, date_to):
    d1 = getdate(date_from or nowdate())
    d2 = getdate(date_to or date_from or nowdate())
    return d1, d2


@frappe.whitelist()
def report(date_from=None, date_to=None):
    """بيانات لوحة الداشبورد (نفس الشكل اللي الصفحة متوقعاه)."""
    require_admin()
    d1, d2 = _range(date_from, date_to)
    p = (d1, d2)
    inv = "si.docstatus = 1 and si.rp_order is not null and si.posting_date between %s and %s"

    t = frappe.db.sql(
        f"select count(*) n, ifnull(sum(si.grand_total), 0) total from `tabSales Invoice` si where {inv}", p, as_dict=True
    )[0]
    by_day = frappe.db.sql(
        f"""select si.posting_date as day, sum(si.grand_total) as total from `tabSales Invoice` si
            where {inv} group by si.posting_date order by si.posting_date""", p, as_dict=True)
    by_type = frappe.db.sql(
        f"""select ro.order_type as type, count(*) as orders, sum(si.grand_total) as total
            from `tabSales Invoice` si join `tabRestaurant Order` ro on ro.name = si.rp_order
            where {inv} group by ro.order_type""", p, as_dict=True)
    top_items = frappe.db.sql(
        f"""select sii.item_name, sum(sii.qty) as qty from `tabSales Invoice Item` sii
            join `tabSales Invoice` si on si.name = sii.parent where {inv}
            group by sii.item_name order by qty desc limit 8""", p, as_dict=True)
    by_user = frappe.db.sql(
        f"""select ifnull(si.rp_cashier, '-') as user, count(*) as orders, sum(si.grand_total) as total
            from `tabSales Invoice` si where {inv} group by si.rp_cashier order by total desc""", p, as_dict=True)
    by_hour = frappe.db.sql(
        f"""select hour(si.creation) as hour, count(*) as orders, sum(si.grand_total) as total
            from `tabSales Invoice` si where {inv} group by hour(si.creation) order by hour""", p, as_dict=True)
    cancelled = frappe.db.sql(
        """select count(*) from `tabRestaurant Order`
           where status = 'Cancelled' and date(creation) between %s and %s""", p)[0][0]
    open_orders = frappe.db.sql(
        "select count(*) from `tabRestaurant Order` where status in %s", (ACTIVE,))[0][0]

    n = t.n or 0
    return {
        "sales": flt(t.total), "orders": n, "avg": flt(t.total) / n if n else 0,
        "cancelled": cancelled, "open_orders": open_orders,
        "by_day": by_day, "by_hour": by_hour, "by_type": by_type, "top_items": top_items, "by_user": by_user,
    }


@frappe.whitelist()
def end_day(date=None, close=0):
    """تقرير نهاية اليوم المختصر. close=1 يقفل حساب كل الكاشيرز (تسوية) بعد التقرير."""
    require_admin()
    day = getdate(date or nowdate())
    p = (day,)
    inv = "si.docstatus = 1 and si.rp_order is not null and si.posting_date = %s"

    types = {k: {"type": k, "orders": 0, "total": 0.0} for k in ORDER_TYPES}
    for r in frappe.db.sql(
        f"""select ro.order_type as type, count(*) as orders, sum(si.grand_total) as total
            from `tabSales Invoice` si join `tabRestaurant Order` ro on ro.name = si.rp_order
            where {inv} group by ro.order_type""", p, as_dict=True):
        types[r.type] = {"type": r.type, "orders": r.orders, "total": flt(r.total)}

    modes = frappe.db.sql(
        f"""select sip.mode_of_payment as mode, sum(sip.amount) as total
            from `tabSales Invoice` si join `tabSales Invoice Payment` sip on sip.parent = si.name
            where {inv} group by sip.mode_of_payment""", p, as_dict=True)
    cashiers = frappe.db.sql(
        f"""select ifnull(si.rp_cashier, '-') as user, count(*) as orders, sum(si.grand_total) as total,
                   sum(ifnull(si.rp_settlement, '') = '') as unsettled
            from `tabSales Invoice` si where {inv} group by si.rp_cashier order by total desc""", p, as_dict=True)
    cx = frappe.db.sql(
        """select count(*) n, ifnull(sum(grand_total), 0) total from `tabRestaurant Order`
           where status = 'Cancelled' and date(creation) = %s""", p, as_dict=True)[0]
    still_open = frappe.db.sql(
        "select count(*) from `tabRestaurant Order` where status in %s", (ACTIVE,))[0][0]

    out = {
        "date": str(day),
        "types": list(types.values()),
        "orders": sum(v["orders"] for v in types.values()),
        "total": sum(v["total"] for v in types.values()),
        "modes": [{"mode": m.mode, "total": flt(m.total)} for m in modes],
        "cashiers": [{"user": c.user, "orders": c.orders, "total": flt(c.total), "unsettled": int(c.unsettled or 0)} for c in cashiers],
        "cancelled": cx.n, "cancelled_total": flt(cx.total), "still_open": still_open,
        "settled_now": [],
    }

    if int(close):
        if still_open:
            frappe.throw(_("There are {0} open orders. Finish or cancel them before ending the day.").format(still_open))
        from restaurant_pos.api.billing import settle_cashier, shift_summary

        for c in out["cashiers"]:
            if c["user"] != "-" and shift_summary(c["user"])["invoice_count"]:
                s = settle_cashier(c["user"], None, "End of day " + str(day))
                out["settled_now"].append(s["name"])
    return out
