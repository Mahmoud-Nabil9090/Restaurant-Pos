"""تجهيز الدفع (مرة واحدة): bench --site <site> execute restaurant_pos.setup.billing.setup_billing"""
import frappe
from frappe import _

from restaurant_pos.api.billing import PROFILE, WALK_IN

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
