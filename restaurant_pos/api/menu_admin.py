"""إدارة المنيو من لوحة الأدمن: أصناف ومجموعات (إضافة / تعديل اسم وسعر ومجموعة / إخفاء أو حذف).

كل الدوال للأدمن فقط. الصنف الجديد بيتعمل كـ Item (مش مخزني) بعلامة is_restaurant_item.
"""
import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from restaurant_pos.api.auth import require_admin

ROOT_GROUP = "All Item Groups"


def _as_dict(data):
    return json.loads(data) if isinstance(data, str) else (data or {})


@frappe.whitelist()
def data():
    """كل بيانات شاشة المنيو: الأصناف + المجموعات + محطات المطبخ."""
    require_admin()
    items = frappe.get_all(
        "Item",
        filters={"is_restaurant_item": 1},
        fields=["name", "item_name", "item_group", "standard_rate", "kitchen_station",
                "prep_time_min", "available_today", "disabled", "image"],
        order_by="item_group, item_name",
        limit_page_length=1000,
    )
    group_fields = ["name"] + (["image"] if frappe.get_meta("Item Group").has_field("image") else [])
    used = {i.item_group for i in items}
    # مجموعات فيها أصناف مطعم + مجموعات جديدة فاضية اتعملت بعد بداية المنيو (من غير مجموعات ERPNext الافتراضية)
    start = frappe.db.get_value("Item", {"is_restaurant_item": 1}, "creation", order_by="creation asc")
    groups = []
    for g in frappe.get_all("Item Group", filters={"is_group": 0, "name": ["!=", ROOT_GROUP]},
                            fields=group_fields + ["creation"], order_by="name"):
        if g.name in used or (start and g.creation >= start and not frappe.db.exists("Item", {"item_group": g.name})):
            g.pop("creation", None)
            groups.append(g)
    stations = frappe.get_all("Kitchen Station", pluck="name", order_by="name")
    return {"items": items, "groups": groups, "stations": stations}


@frappe.whitelist()
def save_item(name=None, data=None):
    """إضافة صنف جديد (name فاضي) أو تعديل صنف موجود."""
    require_admin()
    v = _as_dict(data)
    item_name = (v.get("item_name") or "").strip()
    if not item_name:
        frappe.throw(_("Item name is required"))
    if not v.get("item_group") or not frappe.db.exists("Item Group", v["item_group"]):
        frappe.throw(_("Select a valid group"))

    if name:
        doc = frappe.get_doc("Item", name)
    else:
        if frappe.db.exists("Item", item_name) or frappe.db.exists("Item", {"item_name": item_name}):
            frappe.throw(_("Item {0} already exists").format(item_name))
        doc = frappe.new_doc("Item")
        doc.item_code = item_name
        doc.stock_uom = "Nos"
        doc.is_stock_item = 0

    doc.item_name = item_name
    doc.item_group = v["item_group"]
    doc.standard_rate = flt(v.get("standard_rate"))
    doc.is_restaurant_item = 1
    doc.kitchen_station = v.get("kitchen_station") or None
    doc.prep_time_min = cint(v.get("prep_time_min"))
    doc.available_today = cint(v.get("available_today"))
    if v.get("image"):
        doc.image = v["image"]
    doc.save(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def quick_update(name, standard_rate=None, available_today=None):
    """تعديل سريع للسعر أو التوفر من الجدول."""
    require_admin()
    vals = {}
    if standard_rate is not None:
        vals["standard_rate"] = flt(standard_rate)
    if available_today is not None:
        vals["available_today"] = cint(available_today)
    if vals:
        frappe.db.set_value("Item", name, vals)
    return vals


def _item_used(name):
    return bool(
        frappe.db.exists("Restaurant Order Item", {"item": name})
        or frappe.db.exists("Sales Invoice Item", {"item_code": name})
    )


@frappe.whitelist()
def delete_item(name):
    """يمسح الصنف لو عمره ما اتباع، وغير كده بيخفيه من المنيو (علشان الأوردرات القديمة تفضل سليمة)."""
    require_admin()
    if _item_used(name):
        frappe.db.set_value("Item", name, {"disabled": 1, "available_today": 0})
        return "hidden"
    frappe.delete_doc("Item", name, ignore_permissions=True)
    return "deleted"


@frappe.whitelist()
def restore_item(name):
    require_admin()
    frappe.db.set_value("Item", name, {"disabled": 0, "available_today": 1})


@frappe.whitelist()
def save_group(group_name, old=None, image=None):
    """إضافة مجموعة جديدة، أو تغيير اسم/صورة مجموعة موجودة (old = الاسم الحالي)."""
    require_admin()
    group_name = (group_name or "").strip()
    if not group_name:
        frappe.throw(_("Group name is required"))
    has_image = frappe.get_meta("Item Group").has_field("image")

    if old:
        if group_name != old:
            if frappe.db.exists("Item Group", group_name):
                frappe.throw(_("Group {0} already exists").format(group_name))
            frappe.rename_doc("Item Group", old, group_name, force=True)
    else:
        if frappe.db.exists("Item Group", group_name):
            frappe.throw(_("Group {0} already exists").format(group_name))
        frappe.get_doc({"doctype": "Item Group", "item_group_name": group_name,
                        "parent_item_group": ROOT_GROUP}).insert(ignore_permissions=True)
    if image and has_image:
        frappe.db.set_value("Item Group", group_name, "image", image)
    return group_name


@frappe.whitelist()
def delete_group(name):
    require_admin()
    if frappe.db.exists("Item", {"item_group": name}):
        frappe.throw(_("Move or delete the items in this group first"))
    frappe.delete_doc("Item Group", name, ignore_permissions=True)
