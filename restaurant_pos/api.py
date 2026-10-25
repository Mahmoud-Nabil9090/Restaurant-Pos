import json
import re

import frappe
from frappe import _
from frappe.utils import flt

from restaurant_pos.auth import require_admin

CUSTOMER_FIELDS = [
    "name", "customer_name", "phone", "phone2", "address",
    "building_details", "floor", "notes",
]


def _digits(value):
    return re.sub(r"\D", "", value or "")


def _order_dict(doc):
    """الأوردر كـ dict، ومعاه بيانات عميل الدليفري لو موجودة."""
    d = doc.as_dict()
    customer = doc.get("delivery_customer")
    if customer:
        d["customer_info"] = frappe.db.get_value(
            "Restaurant Customer", customer, CUSTOMER_FIELDS, as_dict=True
        )
    return d


@frappe.whitelist()
def get_menu():
    """كل أصناف المطعم المتاحة، مجمعة بالأقسام."""
    items = frappe.get_all(
        "Item",
        filters={"is_restaurant_item": 1, "available_today": 1, "disabled": 0},
        fields=[
            "name", "item_name", "item_group", "standard_rate",
            "kitchen_station", "prep_time_min", "image",
        ],
        order_by="item_group, item_name",
    )
    groups = sorted({i.item_group for i in items})

    # صور التصنيفات (حقل image في Item Group لو موجود)
    group_images = {}
    if groups and frappe.get_meta("Item Group").has_field("image"):
        for g in frappe.get_all(
            "Item Group", filters={"name": ["in", groups]}, fields=["name", "image"]
        ):
            if g.image:
                group_images[g.name] = g.image
    return {"groups": groups, "items": items, "group_images": group_images}


@frappe.whitelist()
def get_tables():
    """الطاولات مع حالتها والأوردر المفتوح عليها."""
    return frappe.get_all(
        "Restaurant Table",
        fields=["name", "table_name", "area", "capacity", "status", "current_order"],
        order_by="area, table_name",
    )


@frappe.whitelist()
def get_customer(phone):
    """بيانات عميل الدليفري من رقم التليفون (أو None لو أول مرة)."""
    phone = _digits(phone)
    if not phone or not frappe.db.exists("Restaurant Customer", phone):
        return None
    return frappe.get_doc("Restaurant Customer", phone).as_dict()


@frappe.whitelist()
def save_customer(data):
    """يحفظ أو يحدّث عميل دليفري، والرقم هو المفتاح."""
    data = json.loads(data) if isinstance(data, str) else data
    phone = _digits(data.get("phone"))
    if len(phone) < 8:
        frappe.throw(_("Enter a valid phone number"))

    if frappe.db.exists("Restaurant Customer", phone):
        doc = frappe.get_doc("Restaurant Customer", phone)
    else:
        doc = frappe.new_doc("Restaurant Customer")
        doc.phone = phone

    for f in ("customer_name", "phone2", "address", "building_details", "floor", "notes"):
        doc.set(f, (data.get(f) or "").strip())
    doc.phone2 = _digits(doc.phone2)
    doc.save()
    return doc.as_dict()


@frappe.whitelist()
def get_order(name):
    return _order_dict(frappe.get_doc("Restaurant Order", name))


@frappe.whitelist()
def save_order(order):
    """إنشاء أو تعديل أوردر. order = JSON فيه items كل صنف فيه item و qty و notes."""
    data = json.loads(order) if isinstance(order, str) else order

    if data.get("name"):
        doc = frappe.get_doc("Restaurant Order", data["name"])
        if doc.status in ("Billed", "Cancelled"):
            frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))
    else:
        doc = frappe.new_doc("Restaurant Order")
        doc.waiter = frappe.session.user
        doc.company = frappe.defaults.get_global_default("company")

    doc.order_type = data.get("order_type") or "Dine In"
    doc.table = data.get("table")
    doc.customer = data.get("customer")
    doc.discount_amount = flt(data.get("discount_amount"))

    if doc.order_type == "Delivery":
        if not data.get("delivery_customer"):
            frappe.throw(_("Delivery orders need customer details"))
        doc.delivery_customer = data["delivery_customer"]
    else:
        doc.delivery_customer = None

    # نحافظ على حالة الأصناف اللي اتبعتت للمطبخ قبل كده
    old = {r.name: r for r in doc.items}
    doc.items = []
    for row in data.get("items", []):
        item = frappe.db.get_value(
            "Item", row["item"], ["item_name", "standard_rate", "kitchen_station"], as_dict=True
        )
        previous = old.get(row.get("name"))
        doc.append(
            "items",
            {
                "item": row["item"],
                "item_name": item.item_name,
                "qty": flt(row.get("qty")) or 1,
                "rate": item.standard_rate,
                "notes": row.get("notes"),
                "kitchen_station": item.kitchen_station,
                "kitchen_status": previous.kitchen_status if previous else "New",
                "sent_to_kitchen": previous.sent_to_kitchen if previous else 0,
            },
        )

    doc.save()
    return _order_dict(doc)


@frappe.whitelist()
def send_to_kitchen(name):
    """يعلّم الأصناف الجديدة كمبعوتة للمطبخ، وينبّه شاشة المطبخ realtime."""
    doc = frappe.get_doc("Restaurant Order", name)
    new_rows = [r for r in doc.items if not r.sent_to_kitchen]
    if not new_rows:
        frappe.throw(_("No new items to send"))

    for r in new_rows:
        r.sent_to_kitchen = 1
        r.kitchen_status = "New"

    if doc.status == "Open":
        doc.status = "Sent to Kitchen"
    doc.save()

    frappe.publish_realtime(
        "kitchen_new_ticket",
        {
            "order": doc.name,
            "table": doc.table,
            "order_type": doc.order_type,
            "items": [
                {"item_name": r.item_name, "qty": r.qty, "notes": r.notes,
                 "station": r.kitchen_station}
                for r in new_rows
            ],
        },
    )
    return _order_dict(doc)


@frappe.whitelist()
def cancel_item(name, row_name, reason=None):
    require_admin()
    """يلغي صنف اتبعت للمطبخ قبل كده، وينبّه المطبخ realtime."""
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.status in ("Billed", "Cancelled"):
        frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))

    row = next((r for r in doc.items if r.name == row_name), None)
    if not row:
        frappe.throw(_("Item not found in order"))
    if row.kitchen_status == "Cancelled":
        frappe.throw(_("Item is already cancelled"))
    if row.kitchen_status == "Served":
        frappe.throw(_("Item was already served"))

    row.kitchen_status = "Cancelled"
    doc.save()

    frappe.publish_realtime(
        "kitchen_item_cancelled",
        {
            "order": doc.name,
            "table": doc.table,
            "order_type": doc.order_type,
            "item_name": row.item_name,
            "qty": row.qty,
            "station": row.kitchen_station,
            "reason": (reason or "").strip(),
        },
    )
    return _order_dict(doc)


@frappe.whitelist()
def cancel_order(name):
    require_admin()
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.status == "Billed":
        frappe.throw(_("Cannot cancel a billed order"))
    doc.status = "Cancelled"
    doc.save()
    return _order_dict(doc)