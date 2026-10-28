import json
import re

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from restaurant_pos.api.auth import has_permission, require_admin

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


def _notify(doc, action):
    """يبلّغ كل الأجهزة المفتوحة إن أوردر اتغيّر (بعد ما التعديل يتسجّل فعلًا في الداتابيز).
    src = رقم الجهاز اللي عمل التغيير، عشان نفس الجهاز ما يعملش ريفريش لنفسه."""
    frappe.publish_realtime(
        "rp_orders_changed",
        {
            "order": doc.name,
            "action": action,
            "table": doc.get("table"),
            "order_type": doc.get("order_type"),
            "src": frappe.form_dict.get("cid"),
        },
        after_commit=True,
    )


def _lock_and_check(name, modified=None):
    """يقفل صف الأوردر لحد آخر الطلب (عشان جهازين ما يكتبوش فوق بعض)،
    ولو الجهاز باعت modified قديم يرفض: معناه الأوردر اتغيّر من جهاز تاني."""
    current = frappe.db.get_value("Restaurant Order", name, "modified", for_update=True)
    if current is None:
        frappe.throw(_("Order {0} not found").format(name))
    if modified and get_datetime(current) != get_datetime(modified):
        frappe.throw(
            _("This order was changed from another device. Refresh it and try again."),
            title=_("Order changed"),
        )


def _can_discount():
    """هل اليوزر الحالي يقدر يدّي خصم؟ الأدمن دايمًا، أو كاشير اتدّاله صلاحية "discount" من لوحة الأدمن.
    (بنقرا الأدوار مباشرة عشان ما نطلعش رسالة خطأ للكاشير.)"""
    return has_permission("discount")


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
    """إنشاء أو تعديل أوردر. order = JSON فيه items كل صنف فيه item و qty و notes.
    لو الأوردر موجود لازم يبعت modified اللي شافه، ولو اتغيّر من جهاز تاني بيترفض."""
    data = json.loads(order) if isinstance(order, str) else order

    if data.get("name"):
        _lock_and_check(data["name"], data.get("modified"))
        doc = frappe.get_doc("Restaurant Order", data["name"])
        if doc.status in ("Billed", "Cancelled"):
            frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))
        is_new = False
    else:
        doc = frappe.new_doc("Restaurant Order")
        doc.waiter = frappe.session.user
        doc.company = frappe.defaults.get_global_default("company")
        is_new = True

    doc.order_type = data.get("order_type") or "Dine In"
    doc.table = data.get("table")

    if is_new and doc.order_type == "Dine In" and doc.table:
        # جهازين يفتحوا نفس الترابيزة في نفس اللحظة: الأول بس يعدّي
        current = frappe.db.get_value("Restaurant Table", doc.table, "current_order", for_update=True)
        if current and frappe.db.get_value("Restaurant Order", current, "status") not in (
            None, "Billed", "Cancelled"
        ):
            frappe.throw(
                _("Table {0} already has an open order ({1}). Refresh and open it.").format(
                    doc.table, current
                )
            )

    doc.customer = data.get("customer")
    # الخصم للأدمن/المدير بس. الكاشير العادي: القيمة بتفضل زي ما هي (صفر للأوردر الجديد،
    # أو الخصم اللي الأدمن حطّه قبل كده)، وأي خصم جاي منه بيتتجاهل.
    if _can_discount():
        doc.discount_amount = flt(data.get("discount_amount"))
        doc.discount_percent = min(max(flt(data.get("discount_percent")), 0), 100)
    doc.tax_percent = min(max(flt(data.get("tax_percent")), 0), 100)

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
    _notify(doc, "created" if is_new else "updated")
    return _order_dict(doc)


@frappe.whitelist()
def send_to_kitchen(name):
    """يعلّم الأصناف الجديدة كمبعوتة للمطبخ، وينبّه شاشة المطبخ realtime."""
    _lock_and_check(name)
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
    _notify(doc, "sent")
    return _order_dict(doc)


@frappe.whitelist()
def cancel_item(name, row_name, reason=None):
    """يلغي صنف اتبعت للمطبخ قبل كده (أدمن بس، والسبب إجباري ومتسجّل)، وينبّه المطبخ realtime."""
    require_admin()
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Please enter a cancellation reason"))

    _lock_and_check(name)
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
    doc.add_comment(
        "Comment",
        _("Item cancelled by {0}: {1} x {2}. Reason: {3}").format(
            frappe.session.user, row.item_name, row.qty, reason
        ),
    )

    frappe.publish_realtime(
        "kitchen_item_cancelled",
        {
            "order": doc.name,
            "table": doc.table,
            "order_type": doc.order_type,
            "item_name": row.item_name,
            "qty": row.qty,
            "station": row.kitchen_station,
            "reason": reason,
        },
    )
    _notify(doc, "item_cancelled")
    return _order_dict(doc)


@frappe.whitelist()
def cancel_order(name, reason=None):
    """يلغي أوردر كامل (أدمن بس، والسبب إجباري ومتسجّل كتعليق على الأوردر)."""
    require_admin()
    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("Please enter a cancellation reason"))

    _lock_and_check(name)
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.status == "Billed":
        frappe.throw(_("Cannot cancel a billed order"))
    if doc.status == "Cancelled":
        frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))
    doc.status = "Cancelled"
    doc.save()
    doc.add_comment(
        "Comment", _("Order cancelled by {0}. Reason: {1}").format(frappe.session.user, reason)
    )
    _notify(doc, "cancelled")
    return _order_dict(doc)
