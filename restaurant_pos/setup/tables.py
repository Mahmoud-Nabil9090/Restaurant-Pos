import frappe

TABLES = (
    [(f"T{i}", "Indoor", 4) for i in range(1, 7)]
    + [(f"O{i}", "Outdoor", 4) for i in range(1, 4)]
    + [("VIP1", "VIP", 8)]
)


def run():
    for name, area, cap in TABLES:
        if not frappe.db.exists("Restaurant Table", name):
            frappe.get_doc(
                {
                    "doctype": "Restaurant Table",
                    "table_name": name,
                    "area": area,
                    "capacity": cap,
                }
            ).insert()
    frappe.db.commit()
    print(sorted(frappe.get_all("Restaurant Table", pluck="name")))