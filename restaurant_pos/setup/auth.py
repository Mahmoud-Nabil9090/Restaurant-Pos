"""إعداد الأدوار واليوزرز والصلاحيات (مرة واحدة):
    bench --site <site> execute restaurant_pos.setup.auth.run

اليوزرز وكلمات السر بتتقرا من ملف محلي مش بيترفع على Git:
    restaurant_pos/setup/users.local.json      (ده ملفك الحقيقي - متجاهَل في .gitignore)
    restaurant_pos/setup/users.example.json    (مثال بدون أسرار - بيترفع)
"""
import json
import os

import frappe
from frappe.permissions import add_permission, update_permission_property

from restaurant_pos.api.auth import ADMIN, CASHIER, ROLE_SETS, ensure_roles, make_user

HERE = os.path.dirname(__file__)
USERS_FILE = os.path.join(HERE, "users.local.json")

PAGES = {
    "cashier": [CASHIER, ADMIN],
    "delivery-orders": [CASHIER, ADMIN],
    "admin-panel": [ADMIN],
}
PERMS = {
    "Restaurant Order": ["read", "write", "create"],
    "Restaurant Customer": ["read", "write", "create"],
    "Delivery Driver": ["read"],
}


def load_users():
    """يقرا اليوزرز من users.local.json ويرفض أي باسورد فاضي أو CHANGE_ME."""
    if not os.path.exists(USERS_FILE):
        frappe.throw(
            "ملف users.local.json مش موجود. انسخ users.example.json باسم users.local.json "
            "جوه فولدر setup واكتب فيه يوزراتك وباسوراتك."
        )
    with open(USERS_FILE, encoding="utf-8") as f:
        users = json.load(f).get("users", [])
    for u in users:
        if u.get("role") not in ROLE_SETS:
            frappe.throw(f"role غلط لليوزر {u.get('username')}: لازم cashier أو admin")
        if not u.get("password") or u["password"] == "CHANGE_ME":
            frappe.throw(f"اكتب باسورد حقيقي لليوزر {u.get('username')} في users.local.json")
    return users


def run():
    users = load_users()  # نتأكد من الملف الأول قبل أي تغيير
    ensure_roles()

    for dt, ptypes in PERMS.items():
        add_permission(dt, CASHIER, 0)
        for p in ptypes:
            update_permission_property(dt, CASHIER, 0, p, 1)

    for page, roles in PAGES.items():
        if not frappe.db.exists("Page", page):
            print("page not found (run migrate):", page)
            continue
        have = set(frappe.get_all("Has Role", filters={"parent": page, "parenttype": "Page"}, pluck="role"))
        for r in roles:
            if r not in have:
                frappe.get_doc({"doctype": "Has Role", "parent": page, "parenttype": "Page",
                                "parentfield": "roles", "role": r}).insert(ignore_permissions=True)

    for u in users:
        make_user(u["username"], u.get("full_name") or u["username"], u["password"], ROLE_SETS[u["role"]])

    frappe.db.set_single_value("System Settings", "allow_login_using_user_name", 1)
    frappe.db.set_single_value("Website Settings", "disable_signup", 1)
    frappe.db.set_single_value("Website Settings", "app_name", "Restaurant POS")
    frappe.db.commit()
    frappe.clear_cache()
    print("done:", ", ".join(f"{u['username']} ({u['role']})" for u in users))
