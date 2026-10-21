import json

import frappe
from frappe import _
from frappe.utils import flt


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
    return {"groups": groups, "items": items}


@frappe.whitelist()
def get_tables():
    """الطاولات مع حالتها والأوردر المفتوح عليها."""
    return frappe.get_all(
        "Restaurant Table",
        fields=["name", "table_name", "area", "capacity", "status", "current_order"],
        order_by="area, table_name",
    )


@frappe.whitelist()
def get_order(name):
    return frappe.get_doc("Restaurant Order", name).as_dict()


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
    return doc.as_dict()


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
    return doc.as_dict()


@frappe.whitelist()
def cancel_order(name):
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.status == "Billed":
        frappe.throw(_("Cannot cancel a billed order"))
    doc.status = "Cancelled"
    doc.save()
    return doc.as_dict()