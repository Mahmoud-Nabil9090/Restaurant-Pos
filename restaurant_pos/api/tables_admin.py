"""إدارة الترابيزات من لوحة الأدمن: إضافة / تعديل / حذف / تغيير حالة.

كل الدوال للأدمن فقط.
"""
import frappe
from frappe import _
from frappe.utils import cint

from restaurant_pos.api.auth import require_admin


@frappe.whitelist()
def data():
    """كل الترابيزات + المناطق المتاحة + حالات الترابيزة."""
    require_admin()
    tables = frappe.get_all(
        "Restaurant Table",
        fields=["name", "table_name", "area", "capacity", "status", "current_order"],
        order_by="area, table_name",
    )
    meta = frappe.get_meta("Restaurant Table")
    area_df = meta.get_field("area")
    areas = [o for o in (area_df.options or "").split("\n") if o] if area_df else []
    status_df = meta.get_field("status")
    statuses = [o for o in (status_df.options or "").split("\n") if o] if status_df else []
    return {"tables": tables, "areas": areas, "statuses": statuses}


@frappe.whitelist()
def save_table(table_name, area=None, capacity=None, old=None):
    """إضافة ترابيزة جديدة (old فاضي) أو تعديل واحدة موجودة (old = الاسم الحالي)."""
    require_admin()
    table_name = (table_name or "").strip()
    if not table_name:
        frappe.throw(_("Table name is required"))

    if old:
        if not frappe.db.exists("Restaurant Table", old):
            frappe.throw(_("Table {0} not found").format(old))
        if table_name != old:
            if frappe.db.exists("Restaurant Table", table_name) or frappe.db.exists(
                "Restaurant Table", {"table_name": table_name}
            ):
                frappe.throw(_("Table {0} already exists").format(table_name))
            frappe.rename_doc("Restaurant Table", old, table_name, force=True)
        doc = frappe.get_doc("Restaurant Table", table_name)
    else:
        if frappe.db.exists("Restaurant Table", table_name) or frappe.db.exists(
            "Restaurant Table", {"table_name": table_name}
        ):
            frappe.throw(_("Table {0} already exists").format(table_name))
        doc = frappe.new_doc("Restaurant Table")
        doc.table_name = table_name

    if area is not None:
        doc.area = area
    if capacity is not None:
        doc.capacity = cint(capacity) or 4
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def update_status(name, status):
    """تغيير حالة الترابيزة (Available / Occupied / Reserved / Cleaning)."""
    require_admin()
    if not frappe.db.exists("Restaurant Table", name):
        frappe.throw(_("Table not found"))
    frappe.db.set_value("Restaurant Table", name, "status", status)
    return True


@frappe.whitelist()
def delete_table(name):
    """حذف ترابيزة. لو عليها أوردرات مفتوحة بيرفض، ولو عليها أوردرات قديمة بيرفض برضو عشان السجلات."""
    require_admin()
    if frappe.db.exists(
        "Restaurant Order",
        {"table": name, "status": ["not in", ["Billed", "Cancelled"]]},
    ):
        frappe.throw(_("Table has open orders. Close or cancel them first."))
    if frappe.db.exists("Restaurant Order", {"table": name}):
        frappe.throw(
            _("Table was used in past orders and cannot be deleted. You can rename it instead.")
        )
    frappe.delete_doc("Restaurant Table", name, ignore_permissions=True)
    return "deleted"
