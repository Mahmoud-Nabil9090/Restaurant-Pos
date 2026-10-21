import frappe
from restaurant_pos.api import save_order, send_to_kitchen


def run():
    o = save_order(
        {
            "order_type": "Dine In",
            "table": "T1",
            "items": [
                {"item": "Beef Burger", "qty": 2, "notes": "no onion"},
                {"item": "Pepsi", "qty": 2},
            ],
        }
    )
    print("saved:", o.name, o.grand_total, o.status)

    o = send_to_kitchen(o.name)
    print("after kitchen:", o.status)
    print("table T1:", frappe.db.get_value("Restaurant Table", "T1", "status"))

    doc = frappe.get_doc("Restaurant Order", o.name)
    doc.status = "Cancelled"
    doc.save()
    print("after cancel, T1:", frappe.db.get_value("Restaurant Table", "T1", "status"))
    frappe.db.commit()