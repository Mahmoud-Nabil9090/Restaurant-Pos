"""يزوّد المنيو بـ 10 أصناف في كل تصنيف، ويعمل لكل صنف وتصنيف صورة.

التشغيل:
    bench --site mahmoud.local execute restaurant_pos.menu_seed.run

لو عاوز تستبدل الصور الموجودة برسومات جديدة:
    bench --site mahmoud.local execute restaurant_pos.menu_seed.run --kwargs "{'replace_images': 1}"

الأصناف الموجودة قبل كده بتفضل بأسعارها وصورها (إلا لو replace_images=1).
"""
import os

import frappe

from restaurant_pos import menu_art

IMG_URL = "/assets/restaurant_pos/images/menu"

# (التصنيف, الاسم, محطة المطبخ, السعر, وقت التحضير بالدقايق)
MENU = [
    ("Burgers", "Beef Burger", "Grill", 150, 12),
    ("Burgers", "Chicken Burger", "Grill", 130, 12),
    ("Burgers", "Cheese Burger", "Grill", 165, 12),
    ("Burgers", "Double Smash", "Grill", 210, 14),
    ("Burgers", "BBQ Bacon Burger", "Grill", 195, 14),
    ("Burgers", "Mushroom Swiss Burger", "Grill", 185, 14),
    ("Burgers", "Spicy Jalapeno Burger", "Grill", 175, 12),
    ("Burgers", "Crispy Chicken Burger", "Fryer", 145, 12),
    ("Burgers", "Veggie Burger", "Grill", 140, 12),
    ("Burgers", "Kids Mini Burger", "Grill", 95, 8),
    ("Main Dishes", "Grilled Chicken", "Grill", 180, 20),
    ("Main Dishes", "Mixed Grill", "Grill", 260, 25),
    ("Main Dishes", "Chicken Wings", "Fryer", 120, 12),
    ("Main Dishes", "Chicken Strips", "Fryer", 110, 10),
    ("Main Dishes", "Beef Steak", "Grill", 320, 22),
    ("Main Dishes", "Chicken Shawarma Plate", "Grill", 140, 12),
    ("Main Dishes", "Grilled Kofta", "Grill", 190, 18),
    ("Main Dishes", "Fish Fillet", "Fryer", 230, 15),
    ("Main Dishes", "Pasta Alfredo", "Grill", 160, 14),
    ("Main Dishes", "Chicken Fajita", "Grill", 210, 16),
    ("Sides", "French Fries", "Fryer", 50, 7),
    ("Sides", "Onion Rings", "Fryer", 55, 7),
    ("Sides", "Cheese Fries", "Fryer", 70, 8),
    ("Sides", "Sweet Potato Fries", "Fryer", 65, 8),
    ("Sides", "Coleslaw", "Cold Kitchen", 35, 3),
    ("Sides", "Mozzarella Sticks", "Fryer", 75, 8),
    ("Sides", "Potato Wedges", "Fryer", 60, 9),
    ("Sides", "Corn Cup", "Cold Kitchen", 40, 4),
    ("Sides", "Garlic Bread", "Grill", 45, 6),
    ("Sides", "Nachos", "Cold Kitchen", 85, 6),
    ("Salads", "Caesar Salad", "Cold Kitchen", 90, 5),
    ("Salads", "Greek Salad", "Cold Kitchen", 85, 5),
    ("Salads", "Tuna Salad", "Cold Kitchen", 95, 5),
    ("Salads", "Chicken Salad", "Cold Kitchen", 100, 6),
    ("Salads", "Fattoush", "Cold Kitchen", 70, 5),
    ("Salads", "Tabbouleh", "Cold Kitchen", 70, 5),
    ("Salads", "Rocca Salad", "Cold Kitchen", 75, 4),
    ("Salads", "Garden Salad", "Cold Kitchen", 60, 4),
    ("Salads", "Quinoa Salad", "Cold Kitchen", 105, 6),
    ("Salads", "Avocado Salad", "Cold Kitchen", 110, 5),
    ("Drinks", "Pepsi", "Beverages", 25, 1),
    ("Drinks", "7Up", "Beverages", 25, 1),
    ("Drinks", "Mineral Water", "Beverages", 15, 1),
    ("Drinks", "Fresh Orange Juice", "Beverages", 55, 3),
    ("Drinks", "Mango Juice", "Beverages", 60, 3),
    ("Drinks", "Lemon Mint", "Beverages", 45, 3),
    ("Drinks", "Iced Coffee", "Beverages", 55, 4),
    ("Drinks", "Turkish Coffee", "Beverages", 35, 4),
    ("Drinks", "Vanilla Milkshake", "Beverages", 75, 5),
    ("Drinks", "Chocolate Milkshake", "Beverages", 75, 5),
    ("Desserts", "Cheesecake", "Dessert", 80, 2),
    ("Desserts", "Om Ali", "Dessert", 70, 8),
    ("Desserts", "Chocolate Brownie", "Dessert", 65, 4),
    ("Desserts", "Ice Cream Cup", "Dessert", 50, 2),
    ("Desserts", "Molten Lava Cake", "Dessert", 90, 8),
    ("Desserts", "Tiramisu", "Dessert", 85, 2),
    ("Desserts", "Waffle", "Dessert", 80, 7),
    ("Desserts", "Pancakes", "Dessert", 75, 7),
    ("Desserts", "Basbousa", "Dessert", 45, 2),
    ("Desserts", "Apple Pie", "Dessert", 70, 4),
]


def _save_svg(fname, svg):
    folder = frappe.get_app_path("restaurant_pos", "public", "images", "menu")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, fname), "w", encoding="utf-8") as f:
        f.write(svg)
    return f"{IMG_URL}/{fname}"


def run(replace_images=0):
    replace_images = int(replace_images)
    created = updated = 0

    for station in sorted({m[2] for m in MENU}):
        if not frappe.db.exists("Kitchen Station", station):
            frappe.get_doc({"doctype": "Kitchen Station", "station_name": station}).insert()

    group_has_image = frappe.get_meta("Item Group").has_field("image")
    for group in menu_art.CATEGORY_ART:
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc(
                {"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups"}
            ).insert()
        if group_has_image:
            current = frappe.db.get_value("Item Group", group, "image")
            if replace_images or not current:
                url = _save_svg(f"cat-{menu_art.slug(group)}.svg", menu_art.render_category(group))
                frappe.db.set_value("Item Group", group, "image", url)

    for group, name, station, price, prep in MENU:
        existing = frappe.db.get_value("Item", {"item_name": name}, "name")
        if not existing:
            frappe.get_doc(
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
                    "available_today": 1,
                    "standard_rate": price,
                }
            ).insert()
            existing = name
            created += 1
        else:
            vals = frappe.db.get_value(
                "Item", existing, ["kitchen_station", "prep_time_min", "standard_rate"], as_dict=True
            )
            patch = {"is_restaurant_item": 1, "available_today": 1}
            if not vals.kitchen_station:
                patch["kitchen_station"] = station
            if not vals.prep_time_min:
                patch["prep_time_min"] = prep
            if not vals.standard_rate:
                patch["standard_rate"] = price
            frappe.db.set_value("Item", existing, patch)
            updated += 1

        if name in menu_art.ART:
            current = frappe.db.get_value("Item", existing, "image")
            if replace_images or not current:
                url = _save_svg(f"{menu_art.slug(name)}.svg", menu_art.render(name))
                frappe.db.set_value("Item", existing, "image", url)

    frappe.db.commit()

    counts = {}
    for g in menu_art.CATEGORY_ART:
        counts[g] = frappe.db.count("Item", {"item_group": g, "is_restaurant_item": 1})
    print(f"created={created} updated={updated}")
    print("items per category:", counts)
    print("Category images supported:", group_has_image)