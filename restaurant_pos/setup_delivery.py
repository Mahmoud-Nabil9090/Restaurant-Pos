import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def run():
    if not frappe.db.exists("DocType", "Delivery Driver"):
        frappe.throw("Create the 'Delivery Driver' DocType first, then run this again.")

    create_custom_fields(
        {
            "Restaurant Order": [
                {
                    "fieldname": "delivery_status",
                    "label": "Delivery Status",
                    "fieldtype": "Select",
                    "options": "Pending\nOut for Delivery\nDelivered",
                    "default": "Pending",
                    "read_only": 1,
                    "insert_after": "delivery_customer",
                    "module": "Restaurant POS",
                },
                {
                    "fieldname": "driver",
                    "label": "Driver",
                    "fieldtype": "Link",
                    "options": "Delivery Driver",
                    "read_only": 1,
                    "insert_after": "delivery_status",
                    "module": "Restaurant POS",
                },
                {
                    "fieldname": "assigned_on",
                    "label": "Assigned On",
                    "fieldtype": "Datetime",
                    "read_only": 1,
                    "insert_after": "driver",
                    "module": "Restaurant POS",
                },
                {
                    "fieldname": "delivered_on",
                    "label": "Delivered On",
                    "fieldtype": "Datetime",
                    "read_only": 1,
                    "insert_after": "assigned_on",
                    "module": "Restaurant POS",
                },
                {
                    "fieldname": "driver_settled",
                    "label": "Driver Settled",
                    "fieldtype": "Check",
                    "read_only": 1,
                    "insert_after": "delivered_on",
                    "module": "Restaurant POS",
                },
            ]
        }
    )
    frappe.db.commit()
    frappe.clear_cache(doctype="Restaurant Order")

    meta = frappe.get_meta("Restaurant Order")
    present = [
        f
        for f in ("delivery_customer", "delivery_status", "driver", "assigned_on", "delivered_on", "driver_settled")
        if meta.has_field(f)
    ]
    print("Restaurant Order fields present:", present)