
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_fullname, getdate, today
import os
from restaurant_pos.api.auth import ADMIN, CASHIER, PERMISSIONS, ROLE_SETS, ensure_roles, make_user, require_admin


def _range(date_from, date_to):
    a, b = getdate(date_from or today()), getdate(date_to or today())
    return f"{a} 00:00:00", f"{b} 23:59:59.999999"


@frappe.whitelist()
def report(date_from=None, date_to=None):
    """قديمة: التقرير الحقيقي في api/dashboard.py. دي بتحوّل عليه (للأدمن بس)."""
    require_admin()
    from restaurant_pos.api.dashboard import report as _report

    return _report(date_from, date_to)


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
            u["perms"] = [k for k, r in PERMISSIONS.items() if r in roles]
            out.append(u)
    return out


def _final_roles(email, role, permissions):
    """يحسب الأدوار النهائية لليوزر: أدوار الـ role (كاشير/أدمن) + أدوار الصلاحيات الإضافية.
    role=None ومعاها permissions=None معناها: سيب الأدوار زي ما هي (يرجّع None). permissions=None: سيب الصلاحيات الحالية."""
    perm_roles = set(PERMISSIONS.values())
    current = [r.role for r in frappe.get_doc("User", email).roles] if email else []
    if role is None and permissions is None:
        return None if email else list(ROLE_SETS["cashier"])
    if role:
        base = list(ROLE_SETS[role])
    elif email:
        base = [r for r in current if r not in perm_roles]
    else:
        base = list(ROLE_SETS["cashier"])
    if permissions is None:
        extra = [r for r in current if r in perm_roles]
    else:
        extra = [PERMISSIONS[p] for p in permissions]
    return base + [r for r in extra if r not in base]


@frappe.whitelist()
def save_user(username, full_name=None, password=None, role=None, enabled=None, permissions=None):
    """يضيف أو يعدّل يوزر. permissions = قايمة مفاتيح الصلاحيات الإضافية (مثلًا ["discount"])، وغير كده بتفضل زي ما هي."""
    require_admin()
    username = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{2,30}", username):
        frappe.throw(_("Username: 2-30 letters/numbers only"))
    email = f"{username}@pos.local"
    exists = frappe.db.exists("User", email)
    if not exists and not password:
        frappe.throw(_("Password is required for a new user"))
    if enabled is not None and not cint(enabled):
        if username == frappe.db.get_value("User", frappe.session.user, "username"):
            frappe.throw(_("You cannot disable yourself"))
    if role and role not in ROLE_SETS:
        frappe.throw(_("Unknown role"))
    if isinstance(permissions, str):
        permissions = frappe.parse_json(permissions) if permissions else []
    if permissions is not None:
        bad = [p for p in permissions if p not in PERMISSIONS]
        if bad:
            frappe.throw(_("Unknown permission: {0}").format(", ".join(map(str, bad))))
    ensure_roles()  # يعمل دور الصلاحية لو لسه مش موجود
    make_user(
        username,
        full_name or None,
        password or None,
        _final_roles(email if exists else None, role or None, permissions),
        enabled,
    )
    return True


@frappe.whitelist()
def delete_user(username):
    """يحذف يوزر اتعمل من اللوحة (@pos.local). لو عليه أوردرات أو فواتير بيتعطّل بس بدل الحذف،
    عشان السجلات تفضل سليمة. بيرجّع "deleted" أو "disabled"."""
    require_admin()
    username = (username or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{2,30}", username):
        frappe.throw(_("Invalid username"))
    email = f"{username}@pos.local"
    if not frappe.db.exists("User", email):
        frappe.throw(_("User not found"))
    if email == frappe.session.user:
        frappe.throw(_("You cannot delete yourself"))

    used = (
        frappe.db.exists("Restaurant Order", {"owner": email})
        or frappe.db.exists("Sales Invoice", {"rp_cashier": email})
        or frappe.db.exists("Sales Invoice", {"owner": email})
    )
    if not used:
        try:
            frappe.delete_doc("User", email, ignore_permissions=True)
            return "deleted"
        except frappe.LinkExistsError:
            frappe.local.message_log = []  # مش عايزين رسالة خطأ للأدمن، هنعطّله بدل الحذف
    frappe.db.set_value("User", email, "enabled", 0)
    return "disabled"


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
