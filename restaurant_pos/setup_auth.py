
import frappe
from frappe.permissions import add_permission, update_permission_property

from restaurant_pos.auth import ADMIN, CASHIER, ROLE_SETS, ensure_roles, make_user

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


def run():
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

    make_user("mahmoud", "Mahmoud", "1", ROLE_SETS["cashier"])
    make_user("admin", "Admin", "123", ROLE_SETS["admin"])

    frappe.db.set_single_value("System Settings", "allow_login_using_user_name", 1)
    frappe.db.set_single_value("Website Settings", "disable_signup", 1)
    frappe.db.set_single_value("Website Settings", "app_name", "Restaurant POS")
    frappe.db.commit()
    frappe.clear_cache()
    print("done: users mahmoud (cashier), admin (admin)")
