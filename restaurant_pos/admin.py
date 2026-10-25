
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_fullname, getdate, today
import os
from restaurant_pos.auth import ADMIN, CASHIER, ROLE_SETS, make_user, require_admin


def _range(date_from, date_to):
    a, b = getdate(date_from or today()), getdate(date_to or today())
    return f"{a} 00:00:00", f"{b} 23:59:59.999999"


@frappe.whitelist()
def report(date_from=None, date_to=None):
    p = os.path.expanduser(
        "~/frappe-bench/apps/restaurant_pos/restaurant_pos/admin.py"
    )

    with open(p, encoding="utf-8") as f:
        s = f.read()

    if '"open_orders"' not in s:
        s = s.replace(
            '        "sales": sales,\n',
            '        "sales": sales,\n'
            '        "open_orders": frappe.db.count(\n'
            '            "Restaurant Order",\n'
            '            {"status": ["in", ["Open", "Sent to Kitchen", "Served"]]},\n'
            '        ),\n',
            1,
        )

        with open(p, "w", encoding="utf-8") as f:
            f.write(s)

    print("open_orders" in s)

    require_admin()

    a, b = _range(date_from, date_to)

    rows = frappe.get_all(
        "Restaurant Order",
        filters={"creation": ["between", [a, b]]},
        fields=[
            "status",
            "order_type",
            "owner",
            "grand_total",
            "creation",
        ],
    )

    live = [r for r in rows if r.status != "Cancelled"]
    cancelled = [r for r in rows if r.status == "Cancelled"]

    sales = sum(flt(r.grand_total) for r in live)


@frappe.whitelist()
def orders(status=None, date_from=None, date_to=None):
    require_admin()
    a, b = _range(date_from, date_to)
    filters = {"creation": ["between", [a, b]]}
    if status:
        filters["status"] = status
    rows = frappe.get_all(
        "Restaurant Order",
        filters=filters,
        fields=["name", "order_type", "table", "status", "grand_total", "owner", "creation"],
        order_by="creation desc",
        limit_page_length=300,
    )
    for r in rows:
        r["user"] = get_fullname(r.owner)
    return rows


@frappe.whitelist()
def cancel_order(name, reason=""):
    require_admin()
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.status in ("Billed", "Cancelled"):
        frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))
    for r in doc.items:
        if r.sent_to_kitchen and r.kitchen_status not in ("Served", "Cancelled"):
            frappe.publish_realtime(
                "kitchen_item_cancelled",
                {"order": doc.name, "table": doc.table, "order_type": doc.order_type,
                 "item_name": r.item_name, "qty": r.qty, "station": r.kitchen_station,
                 "reason": reason},
            )
    doc.status = "Cancelled"
    doc.save(ignore_permissions=True)
    doc.add_comment("Comment", _("Cancelled by {0}: {1}").format(frappe.session.user, reason or "-"))
    return doc.name


@frappe.whitelist()
def users():
    require_admin()
    out = []
    for u in frappe.get_all(
        "User",
        filters={"name": ["not in", ["Administrator", "Guest"]], "user_type": "System User"},
        fields=["name", "full_name", "username", "enabled"],
    ):
        roles = frappe.get_roles(u.name)
        role = "admin" if ADMIN in roles else ("cashier" if CASHIER in roles else None)
        if role:
            u["role"] = role
            out.append(u)
    return out


@frappe.whitelist()
def save_user(username, full_name=None, password=None, role=None, enabled=None):
    require_admin()
    username = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{2,30}", username):
        frappe.throw(_("Username: 2-30 letters/numbers only"))
    exists = frappe.db.exists("User", f"{username}@pos.local")
    if not exists and not password:
        frappe.throw(_("Password is required for a new user"))
    if enabled is not None and not cint(enabled):
        if username == frappe.db.get_value("User", frappe.session.user, "username"):
            frappe.throw(_("You cannot disable yourself"))
    make_user(
        username,
        full_name or None,
        password or None,
        ROLE_SETS.get(role) if role else (None if exists else ROLE_SETS["cashier"]),
        enabled,
    )
    return True


@frappe.whitelist()
def menu():
    require_admin()
    return frappe.get_all(
        "Item",
        filters={"is_restaurant_item": 1, "disabled": 0},
        fields=["name", "item_name", "item_group", "standard_rate", "available_today"],
        order_by="item_group, item_name",
    )


@frappe.whitelist()
def update_item(name, standard_rate=None, available_today=None):
    require_admin()
    vals = {}
    if standard_rate is not None:
        vals["standard_rate"] = flt(standard_rate)
    if available_today is not None:
        vals["available_today"] = cint(available_today)
    if vals:
        frappe.db.set_value("Item", name, vals)
    return True
