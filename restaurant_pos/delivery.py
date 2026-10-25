import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

CUSTOMER_FIELDS = [
    "name", "customer_name", "phone", "phone2", "address",
    "building_details", "floor", "notes",
]


def _status(doc):
    return doc.get("delivery_status") or "Pending"


def _order_row(doc):
    customer = None
    if doc.get("delivery_customer"):
        customer = frappe.db.get_value(
            "Restaurant Customer", doc.delivery_customer, CUSTOMER_FIELDS, as_dict=True
        )
    return {
        "name": doc.name,
        "creation": doc.creation,
        "status": doc.status,
        "delivery_status": _status(doc),
        "driver": doc.get("driver"),
        "assigned_on": doc.get("assigned_on"),
        "delivered_on": doc.get("delivered_on"),
        "driver_settled": doc.get("driver_settled") or 0,
        "grand_total": doc.grand_total,
        "customer": customer,
        "items": [
            {
                "item_name": r.item_name,
                "qty": r.qty,
                "notes": r.notes,
                "kitchen_status": r.kitchen_status,
            }
            for r in doc.items
        ],
    }


def _get_delivery_order(name):
    doc = frappe.get_doc("Restaurant Order", name)
    if doc.order_type != "Delivery":
        frappe.throw(_("{0} is not a delivery order").format(name))
    if doc.status in ("Billed", "Cancelled"):
        frappe.throw(_("Order {0} is already {1}").format(doc.name, doc.status))
    return doc


@frappe.whitelist()
def get_drivers():
    return frappe.get_all(
        "Delivery Driver",
        filters={"is_active": 1},
        fields=["name", "driver_name", "phone"],
        order_by="driver_name",
    )


@frappe.whitelist()
def get_delivery_orders(view="active", date=None):
    """view: active | pending | out | delivered. كلهم بيعرضوا اليوم المختار بس (date، الافتراضي النهارده):
    الشغالين حسب يوم إنشاء الأوردر، والمسلَّمين حسب يوم التسليم."""
    day = getdate(date or frappe.utils.nowdate())
    span = ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]]
    filters = {"order_type": "Delivery", "status": ["!=", "Cancelled"]}
    filters["delivered_on" if view == "delivered" else "creation"] = span
    names = frappe.get_all(
        "Restaurant Order", filters=filters, pluck="name", order_by="creation desc", limit_page_length=300
    )
    rows = [_order_row(frappe.get_doc("Restaurant Order", n)) for n in names]

    wanted = {
        "active": ("Pending", "Out for Delivery"),
        "pending": ("Pending",),
        "out": ("Out for Delivery",),
        "delivered": ("Delivered",),
    }.get(view, ("Pending", "Out for Delivery"))
    return [r for r in rows if r["delivery_status"] in wanted]


@frappe.whitelist()
def assign_driver(name, driver):
    doc = _get_delivery_order(name)
    if any(not r.sent_to_kitchen for r in doc.items if r.kitchen_status != "Cancelled"):
        frappe.throw(_("Send the order to the kitchen first, then assign a driver"))
    if _status(doc) == "Delivered":
        frappe.throw(_("Order is already delivered"))
    if doc.get("driver_settled"):
        frappe.throw(_("This order was already settled with its driver"))
    if not driver or not frappe.db.exists("Delivery Driver", driver):
        frappe.throw(_("Select a valid driver"))

    doc.driver = driver
    doc.delivery_status = "Out for Delivery"
    doc.assigned_on = now_datetime()
    doc.save()
    return _order_row(doc)


@frappe.whitelist()
def unassign_driver(name):
    doc = _get_delivery_order(name)
    if _status(doc) != "Out for Delivery":
        frappe.throw(_("Only orders that are out for delivery can be unassigned"))
    if doc.get("driver_settled"):
        frappe.throw(_("This order was already settled with its driver"))

    doc.driver = None
    doc.delivery_status = "Pending"
    doc.assigned_on = None
    doc.save()
    return _order_row(doc)


@frappe.whitelist()
def mark_delivered(name):
    doc = _get_delivery_order(name)
    if not doc.get("driver"):
        frappe.throw(_("Assign a driver first"))
    if _status(doc) == "Delivered":
        frappe.throw(_("Order is already delivered"))

    doc.delivery_status = "Delivered"
    doc.delivered_on = now_datetime()
    if doc.status in ("Open", "Sent to Kitchen"):
        doc.status = "Served"
    doc.save()
    return _order_row(doc)


def _day_orders(day, driver=None):
    filters = [
        ["order_type", "=", "Delivery"],
        ["status", "!=", "Cancelled"],
        ["driver", "is", "set"],
        ["assigned_on", ">=", f"{day} 00:00:00"],
        ["assigned_on", "<=", f"{day} 23:59:59.999999"],
    ]
    if driver:
        filters.append(["driver", "=", driver])
    return frappe.get_all(
        "Restaurant Order", filters=filters, pluck="name", order_by="assigned_on asc"
    )


@frappe.whitelist()
def driver_summary(date=None):
    """حساب كل دليفري مان في يوم معيّن (حسب تاريخ تحميل الأوردر عليه)."""
    day = getdate(date)
    out = {}
    for n in _day_orders(day):
        row = _order_row(frappe.get_doc("Restaurant Order", n))
        d = out.setdefault(
            row["driver"],
            {
                "driver": row["driver"],
                "orders": [],
                "delivered_count": 0,
                "pending_count": 0,
                "delivered_total": 0,
                "pending_total": 0,
                "to_settle": 0,
            },
        )
        d["orders"].append(row)
        if row["delivery_status"] == "Delivered":
            d["delivered_count"] += 1
            d["delivered_total"] += row["grand_total"] or 0
            if not row["driver_settled"]:
                d["to_settle"] += row["grand_total"] or 0
        else:
            d["pending_count"] += 1
            d["pending_total"] += row["grand_total"] or 0

    result = []
    for driver, d in out.items():
        info = frappe.db.get_value(
            "Delivery Driver", driver, ["driver_name", "phone"], as_dict=True
        ) or {}
        d["driver_name"] = info.get("driver_name") or driver
        d["phone"] = info.get("phone") or ""
        d["total_orders"] = len(d["orders"])
        result.append(d)
    result.sort(key=lambda x: x["driver_name"])
    return result


@frappe.whitelist()
def settle_driver(driver, date=None):
    """يقفل حساب الدليفري مان: كل الأوردرات المسلّمة بتتعلّم settled."""
    day = getdate(date)
    names = _day_orders(day, driver)
    docs = [frappe.get_doc("Restaurant Order", n) for n in names]

    pending = [d.name for d in docs if _status(d) != "Delivered"]
    if pending:
        frappe.throw(
            _("{0} order(s) are still out for delivery: {1}").format(
                len(pending), ", ".join(pending)
            )
        )

    from restaurant_pos.billing import create_invoice

    for d in docs:
        if not d.get("driver_settled"):
            d.reload()
            create_invoice(d, "Cash")  # فاتورة POS على اللي بيستلم الفلوس من الدليفرى مان
            frappe.db.set_value("Restaurant Order", d.name, "driver_settled", 1)
    return driver_summary(date)