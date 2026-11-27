"""ملف إضافة بيانات أساسية للمطعم: مجموعات أصناف + أصناف + ترابيزات + محطات مطبخ + سواقين دليفري.

الملف ده بيديك تحكم كامل في البيانات اللي تضيفها من غير ما تحتاج تفتح ERPNext.
كل اللي عليك تعدّل القوائم اللي تحت (STATIONS / GROUPS / ITEMS / TABLES / DRIVERS)
وبعدين تشغّل الأمر ده:

    bench --site YOUR_SITE execute restaurant_pos.setup.seed_data.seed

مسح البيانات اللي الملف ده ضافها:
    bench --site YOUR_SITE execute restaurant_pos.setup.seed_data.remove

ملاحظات:
  - آمن يتشغّل أكتر من مرة: اللي موجود بيتخطّاه.
  - مش بيمسح أي بيانات من عندك.
  - الأصناف المستخدمة في أوردرات بتتخفى بدل ما تتمسح.
"""

import frappe
from frappe.utils import cint

# ═══════════════════════════════════════════════════════════════
# 1. محطات المطبخ  (Kitchen Stations)
#    التذكرة بتروح لمحطة الصنف اللي الكاشير طلبه
# ═══════════════════════════════════════════════════════════════
STATIONS = [
    "Grill",
    "Fryer",
    "Cold Kitchen",
    "Beverages",
    "Dessert",
]

# ═══════════════════════════════════════════════════════════════
# 2. مجموعات الأصناف (Item Groups)
#    كل مجموعة بتظهر كـ tab في شاشة الكاشير
# ═══════════════════════════════════════════════════════════════
GROUPS = [
    "Burgers",
    "Main Dishes",
    "Sides",
    "Salads",
    "Drinks",
    "Desserts",
]

# ═══════════════════════════════════════════════════════════════
# 3. الأصناف (Items)
#    (المجموعة، اسم الصنف، السعر، محطة المطبخ، وقت التحضير بالدقايق)
#
#    عدّل الأسعار والأسماء حسب المطعم بتاعك.
#    الأصناف الجديدة اللي تضيفها هنا هتظهر في الكاشير فورًا بعد التشغيل.
# ═══════════════════════════════════════════════════════════════
ITEMS = [
    # --- Burgers ---
    ("Burgers", "Classic Beef Burger", 120, "Grill", 12),
    ("Burgers", "Cheese Burger", 140, "Grill", 12),
    ("Burgers", "Double Smash Burger", 180, "Grill", 14),
    ("Burgers", "Crispy Chicken Burger", 130, "Fryer", 12),
    ("Burgers", "Mushroom Swiss Burger", 160, "Grill", 14),
    ("Burgers", "Spicy Jalapeno Burger", 155, "Grill", 12),
    ("Burgers", "BBQ Bacon Burger", 170, "Grill", 14),
    ("Burgers", "Veggie Burger", 110, "Grill", 12),

    # --- Main Dishes ---
    ("Main Dishes", "Grilled Chicken", 160, "Grill", 20),
    ("Main Dishes", "Mixed Grill Platter", 240, "Grill", 25),
    ("Main Dishes", "Chicken Wings (8 pcs)", 110, "Fryer", 12),
    ("Main Dishes", "Chicken Strips", 100, "Fryer", 10),
    ("Main Dishes", "Beef Steak", 280, "Grill", 22),
    ("Main Dishes", "Pasta Alfredo", 140, "Grill", 14),
    ("Main Dishes", "Chicken Shawarma Plate", 130, "Grill", 12),
    ("Main Dishes", "Fish Fillet", 200, "Fryer", 15),

    # --- Sides ---
    ("Sides", "French Fries", 45, "Fryer", 7),
    ("Sides", "Cheese Fries", 65, "Fryer", 8),
    ("Sides", "Onion Rings", 50, "Fryer", 7),
    ("Sides", "Mozzarella Sticks", 70, "Fryer", 8),
    ("Sides", "Garlic Bread", 40, "Grill", 6),
    ("Sides", "Coleslaw", 30, "Cold Kitchen", 3),
    ("Sides", "Potato Wedges", 55, "Fryer", 9),
    ("Sides", "Nachos", 80, "Cold Kitchen", 6),

    # --- Salads ---
    ("Salads", "Caesar Salad", 85, "Cold Kitchen", 5),
    ("Salads", "Greek Salad", 80, "Cold Kitchen", 5),
    ("Salads", "Chicken Salad", 95, "Cold Kitchen", 6),
    ("Salads", "Fattoush", 65, "Cold Kitchen", 5),
    ("Salads", "Garden Salad", 55, "Cold Kitchen", 4),

    # --- Drinks ---
    ("Drinks", "Pepsi", 20, "Beverages", 1),
    ("Drinks", "7Up", 20, "Beverages", 1),
    ("Drinks", "Mineral Water", 10, "Beverages", 1),
    ("Drinks", "Fresh Orange Juice", 50, "Beverages", 3),
    ("Drinks", "Mango Juice", 55, "Beverages", 3),
    ("Drinks", "Lemon Mint", 40, "Beverages", 3),
    ("Drinks", "Iced Coffee", 50, "Beverages", 4),
    ("Drinks", "Turkish Coffee", 30, "Beverages", 4),

    # --- Desserts ---
    ("Desserts", "Cheesecake", 75, "Dessert", 2),
    ("Desserts", "Chocolate Brownie", 60, "Dessert", 4),
    ("Desserts", "Ice Cream Cup", 45, "Dessert", 2),
    ("Desserts", "Om Ali", 65, "Dessert", 8),
    ("Desserts", "Tiramisu", 80, "Dessert", 2),
    ("Desserts", "Waffle", 75, "Dessert", 7),
]

# ═══════════════════════════════════════════════════════════════
# 4. الترابيزات (Tables)
#    (المنطقة، اسم الترابيزة، السعة)
#
#    المناطق المتاحة في الـ DocType: Indoor / Outdoor / VIP
#    تقدر تضيف مناطق جديدة بتعديل ملف restaurant_table.json
# ═══════════════════════════════════════════════════════════════
TABLES = [
    # Indoor
    ("Indoor", "T1", 2),
    ("Indoor", "T2", 4),
    ("Indoor", "T3", 4),
    ("Indoor", "T4", 2),
    ("Indoor", "T5", 6),
    ("Indoor", "T6", 4),
    ("Indoor", "T7", 4),
    ("Indoor", "T8", 2),
    # Outdoor
    ("Outdoor", "O1", 4),
    ("Outdoor", "O2", 4),
    ("Outdoor", "O3", 6),
    ("Outdoor", "O4", 4),
    # VIP
    ("VIP", "VIP1", 8),
    ("VIP", "VIP2", 6),
]

# ═══════════════════════════════════════════════════════════════
# 5. سواقين دليفري (Delivery Drivers)
#    (الاسم، رقم التليفون)
# ═══════════════════════════════════════════════════════════════
DRIVERS = [
    ("أحمد محمد", "01000000001"),
    ("محمود على", "01000000002"),
    ("خالد حسن", "01000000003"),
]


# ═══════════════════════════════════════════════════════════════
#  أدوات مساعدة (مش محتاج تعدّل فيها)
# ═══════════════════════════════════════════════════════════════

def _field_ok(meta, fieldname):
    """يتأكد إن الحقل موجود في الـ DocType."""
    return meta.has_field(fieldname)


def _select_ok(meta, fieldname, value):
    """يتأكد إن القيمة ضمن اختيارات حقل Select."""
    df = meta.get_field(fieldname)
    if not df or df.fieldtype != "Select":
        return True
    opts = [o for o in (df.options or "").split("\n") if o]
    return not opts or value in opts


def _ensure_station(name):
    if not frappe.db.exists("Kitchen Station", name):
        try:
            frappe.get_doc({"doctype": "Kitchen Station", "station_name": name}).insert(ignore_permissions=True)
            frappe.db.commit()
            return "✓ created"
        except Exception as e:
            frappe.db.rollback()
            return f"✗ {e}"
    return "– exists"


def _ensure_group(name):
    if not frappe.db.exists("Item Group", name):
        try:
            frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }).insert(ignore_permissions=True)
            frappe.db.commit()
            return "✓ created"
        except Exception as e:
            frappe.db.rollback()
            return f"✗ {e}"
    return "– exists"


def _ensure_item(group, name, price, station, prep_time):
    if frappe.db.exists("Item", name) or frappe.db.exists("Item", {"item_name": name}):
        # update missing fields only
        existing = frappe.db.get_value("Item", {"item_name": name}, "name") or name
        patch = {"is_restaurant_item": 1, "available_today": 1}
        if not frappe.db.get_value("Item", existing, "kitchen_station"):
            patch["kitchen_station"] = station
        if not frappe.db.get_value("Item", existing, "standard_rate"):
            patch["standard_rate"] = price
        frappe.db.set_value("Item", existing, patch)
        return "– exists (updated)"
    try:
        frappe.get_doc({
            "doctype": "Item",
            "item_code": name,
            "item_name": name,
            "item_group": group,
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_restaurant_item": 1,
            "kitchen_station": station,
            "prep_time_min": prep_time,
            "available_today": 1,
            "standard_rate": price,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        return "✓ created"
    except Exception as e:
        frappe.db.rollback()
        return f"✗ {e}"


def _ensure_table(area, name, capacity):
    meta = frappe.get_meta("Restaurant Table")
    if frappe.db.exists("Restaurant Table", name) or frappe.db.exists("Restaurant Table", {"table_name": name}):
        return "– exists"
    # لو المنطقة مش من الاختيارات المتاحة، ياخد أول اختيار
    if not _select_ok(meta, "area", area):
        df = meta.get_field("area")
        opts = [o for o in (df.options or "").split("\n") if o]
        area = opts[0] if opts else area
    try:
        frappe.get_doc({
            "doctype": "Restaurant Table",
            "table_name": name,
            "area": area,
            "capacity": capacity,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        return "✓ created"
    except Exception as e:
        frappe.db.rollback()
        return f"✗ {e}"


def _ensure_driver(name, phone):
    meta = frappe.get_meta("Delivery Driver")
    key = None
    for c in ("driver_name", "full_name", "title"):
        if meta.has_field(c):
            key = c
            break
    if key and frappe.db.exists("Delivery Driver", {key: name}):
        return "– exists"
    vals = {"doctype": "Delivery Driver"}
    if meta.has_field("driver_name"):
        vals["driver_name"] = name
    if meta.has_field("phone"):
        vals["phone"] = phone
    if meta.has_field("mobile"):
        vals["mobile"] = phone
    if meta.has_field("mobile_no"):
        vals["mobile_no"] = phone
    if meta.has_field("is_active"):
        vals["is_active"] = 1
    try:
        frappe.get_doc(vals).insert(ignore_permissions=True)
        frappe.db.commit()
        return "✓ created"
    except Exception as e:
        frappe.db.rollback()
        return f"✗ {e}"


# ═══════════════════════════════════════════════════════════════
#  التشغيل
# ═══════════════════════════════════════════════════════════════

def seed():
    """إضافة كل البيانات.

    bench --site YOUR_SITE execute restaurant_pos.setup.seed_data.seed
    """
    print("\n🔧 بدأنا إضافة البيانات...\n")

    print("━━━ محطات المطبخ ━━━")
    for s in STATIONS:
        print(f"  {s}: {_ensure_station(s)}")

    print("\n━━━ مجموعات الأصناف ━━━")
    for g in GROUPS:
        print(f"  {g}: {_ensure_group(g)}")

    print("\n━━━ الأصناف ━━━")
    created = exists = failed = 0
    for group, name, price, station, prep in ITEMS:
        result = _ensure_item(group, name, price, station, prep)
        if "created" in result:
            created += 1
        elif "exists" in result:
            exists += 1
        else:
            failed += 1
            print(f"  ✗ {name}: {result}")
    print(f"  جديد: {created} | موجود: {exists} | فشل: {failed}")

    print("\n━━━ الترابيزات ━━━")
    for area, name, cap in TABLES:
        print(f"  {name} ({area}, {cap} أشخاص): {_ensure_table(area, name, cap)}")

    print("\n━━━ سواقين الدليفري ━━━")
    for name, phone in DRIVERS:
        print(f"  {name}: {_ensure_driver(name, phone)}")

    frappe.clear_cache()
    print("\n✅ خلصنا! افتح الكاشير واعمل Ctrl+Shift+R.\n")


def remove():
    """مسح البيانات اللي الملف ده ضافها بس.

    bench --site YOUR_SITE execute restaurant_pos.setup.seed_data.remove
    """
    print("\n🗑️  بنمسح البيانات...")

    # مسح الأصناف (أو إخفائها لو مستخدمة في أوردرات)
    for _g, name, *_ in ITEMS:
        if not frappe.db.exists("Item", name) and not frappe.db.exists("Item", {"item_name": name}):
            continue
        actual = frappe.db.get_value("Item", {"item_name": name}, "name") or name
        used = (
            frappe.db.exists("Restaurant Order Item", {"item": actual})
            or frappe.db.exists("Sales Invoice Item", {"item_code": actual})
        )
        if used:
            frappe.db.set_value("Item", actual, {"disabled": 1, "available_today": 0})
            print(f"  • {name}: مستخدم → اتخفى")
        else:
            try:
                frappe.delete_doc("Item", actual, ignore_permissions=True, force=True)
                print(f"  • {name}: اتمسح")
            except Exception:
                frappe.db.rollback()
                frappe.db.set_value("Item", actual, {"disabled": 1, "available_today": 0})
                print(f"  • {name}: مرتبط → اتخفى")

    # مسح الترابيزات
    for _a, name, _c in TABLES:
        for t in frappe.get_all("Restaurant Table", filters={"table_name": name}, pluck="name"):
            try:
                frappe.delete_doc("Restaurant Table", t, ignore_permissions=True, force=True)
                print(f"  • ترابيزة {name}: اتمسحت")
            except Exception:
                frappe.db.rollback()
                print(f"  • ترابيزة {name}: مرتبطة بأوردرات → سيبتها")

    frappe.db.commit()
    frappe.clear_cache()
    print("\n✅ خلصنا المسح. الأقسام والمحطات والسواقين سيبتهم (امسحهم يدوي لو عايز).\n")
