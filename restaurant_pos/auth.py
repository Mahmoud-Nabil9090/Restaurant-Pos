"""تسجيل الدخول والأدوار: كل يوزر يفتح على صفحته (كاشير -> cashier، أدمن -> admin-panel)."""
import frappe

CASHIER = "Restaurant Cashier"
ADMIN = "Restaurant Admin"
ADMIN_ROLE = ADMIN
CASHIER_ROLE = CASHIER
ROLE_SETS = {"cashier": [CASHIER], "admin": [ADMIN, CASHIER, "System Manager"]}

ADMIN_PAGE = "admin-panel"
CASHIER_PAGE = "cashier"


def ensure_roles():
    """يعمل الدورين لو مش موجودين."""
    for r in (CASHIER, ADMIN):
        if not frappe.db.exists("Role", r):
            frappe.get_doc({"doctype": "Role", "role_name": r, "desk_access": 1}).insert(ignore_permissions=True)


def is_admin(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or ADMIN in frappe.get_roles(user)


def require_admin():
    if not is_admin():
        frappe.throw("هذه العملية للأدمن فقط / Admin only", frappe.PermissionError)


def boot_session(bootinfo):
    """بعد الدخول: الأدمن يفتح على admin-panel والكاشير على cashier."""
    if frappe.session.user == "Guest":
        return
    roles = frappe.get_roles()
    if ADMIN in roles:
        bootinfo["home_page"] = ADMIN_PAGE
    elif CASHIER in roles:
        bootinfo["home_page"] = CASHIER_PAGE


def make_user(username, full_name=None, password=None, roles=None, enabled=None):
    email = f"{username}@pos.local"
    if frappe.db.exists("User", email):
        u = frappe.get_doc("User", email)
    else:
        u = frappe.new_doc("User")
        u.email = email
        u.first_name = full_name or username
        u.send_welcome_email = 0
        u.user_type = "System User"
        u.enabled = 1
    u.username = username
    if full_name:
        u.first_name = full_name
    if enabled is not None:
        u.enabled = int(enabled)
    if password:
        u.new_password = password
        u.flags.ignore_password_policy = True
    if roles is not None:
        u.set("roles", [])
        for r in roles:
            u.append("roles", {"role": r})
    u.save(ignore_permissions=True)
    return u


@frappe.whitelist()
def whoami():
    """بتتندّه بعد تسجيل الدخول عشان صفحة الدخول تعرف توديك فين."""
    user = frappe.session.user
    admin = is_admin(user)
    return {
        "user": user,
        "full_name": frappe.utils.get_fullname(user),
        "role": "admin" if admin else "cashier",
        "route": f"/app/{ADMIN_PAGE}" if admin else f"/app/{CASHIER_PAGE}",
    }
