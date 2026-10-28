import frappe

STATIONS = ["Grill", "Fryer", "Cold Kitchen", "Beverages", "Dessert"]

TABLES = (
    [(f"T{i}", "Indoor", 4) for i in range(1, 7)]
    + [(f"O{i}", "Outdoor", 4) for i in range(1, 4)]
    + [("VIP1", "VIP", 8)]
)

# (item_name, group, station, price, prep_minutes)
MENU = [
    ("Beef Burger", "Burgers", "Grill", 150, 12),
    ("Chicken Burger", "Burgers", "Grill", 130, 12),
    ("Grilled Chicken", "Main Dishes", "Grill", 180, 20),
    ("Mixed Grill", "Main Dishes", "Grill", 260, 25),
    ("French Fries", "Sides", "Fryer", 50, 7),
    ("Onion Rings", "Sides", "Fryer", 55, 7),
    ("Caesar Salad", "Salads", "Cold Kitchen", 90, 5),
    ("Greek Salad", "Salads", "Cold Kitchen", 85, 5),
    ("Pepsi", "Drinks", "Beverages", 25, 1),
    ("Fresh Orange Juice", "Drinks", "Beverages", 55, 3),
    ("Turkish Coffee", "Drinks", "Beverages", 35, 4),
    ("Cheesecake", "Desserts", "Dessert", 80, 2),
    ("Om Ali", "Desserts", "Dessert", 70, 8),
]


def run():
    company = frappe.defaults.get_global_default("company")
    price_list = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")

    for s in STATIONS:
        if not frappe.db.exists("Kitchen Station", s):
            frappe.get_doc({"doctype": "Kitchen Station", "station_name": s}).insert()

    for name, area, cap in TABLES:
        if not frappe.db.exists("Restaurant Table", name):
            frappe.get_doc(
                {"doctype": "Restaurant Table", "table_name": name, "area": area, "capacity": cap}
            ).insert()

    for name, group, station, price, prep in MENU:
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc(
                {"doctype": "Item Group", "item_group_name": group,
                 "parent_item_group": "All Item Groups"}
            ).insert()

        if frappe.db.exists("Item", {"item_name": name}):
            continue

        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": name,
                "item_name": name,
                "item_group": group,
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_restaurant_item": 1,
                "kitchen_station": station,
                "prep_time_min": prep,
                "standard_rate": price,
            }
        ).insert()

        if price_list:
            frappe.get_doc(
                {"doctype": "Item Price", "item_code": item.name,
                 "price_list": price_list, "price_list_rate": price}
            ).insert()

    frappe.db.commit()
    print(f"Done. Company: {company}, Price List: {price_list}")