"""بيانات تجريبية لمطعم: أقسام + أصناف + ترابيز + محطات مطبخ + دليفري مان.

مكان الملف:  restaurant_pos/restaurant_pos/api/demo_data.py   (جنب orders.py)

التشغيل (على الموقع):
    bench --site SITE execute restaurant_pos.api.demo_data.seed
مسح البيانات التجريبية دي بس:
    bench --site SITE execute restaurant_pos.api.demo_data.remove

آمن تشغّله أكتر من مرة: اللي موجود بيتخطّاه. ومش بيلمس أي صنف أو ترابيزة من عندك.
لو شغّلته على موقع فيه بياناتك، هيضيف التجريبي جنبها بس.

للتعديل: غيّر القوائم اللي تحت (STATIONS / GROUPS / ITEMS / TABLES / DRIVERS) وشغّل seed تاني.
"""
import frappe

# ---------------------------------------------------------------- البيانات (عدّل هنا)

# محطات المطبخ (التذكرة بتروح لمحطة الصنف)
STATIONS = ["Grill", "Fryer", "Cold", "Bar"]

# أقسام المنيو
GROUPS = ["برجر", "جانبية", "مشروبات", "حلويات"]

# (القسم، اسم الصنف، السعر، المحطة، وقت التحضير بالدقيقة)
ITEMS = [
    ("برجر", "برجر كلاسيك", 85, "Grill", 12),
    ("برجر", "دبل تشيز برجر", 120, "Grill", 14),
    ("برجر", "تشيكن كرسبي", 95, "Fryer", 12),
    ("برجر", "مشروم سويس", 110, "Grill", 13),
    ("جانبية", "بطاطس مقلية", 35, "Fryer", 7),
    ("جانبية", "حلقات بصل", 40, "Fryer", 8),
    ("جانبية", "أصابع موتزاريلا", 55, "Fryer", 9),
    ("جانبية", "سلطة كول سلو", 25, "Cold", 3),
    ("مشروبات", "بيبسي", 20, "Bar", 1),
    ("مشروبات", "عصير برتقال", 40, "Bar", 4),
    ("مشروبات", "ليمون بالنعناع", 35, "Bar", 4),
    ("مشروبات", "قهوة", 30, "Bar", 4),
    ("حلويات", "براونيز", 55, "Cold", 3),
    ("حلويات", "تشيز كيك", 65, "Cold", 3),
    ("حلويات", "آيس كريم", 35, "Cold", 2),
]

# (المنطقة، اسم الترابيزة، السعة). المنطقة لو الحقل ليه اختيارات ثابتة بياخد أول اختيار.
TABLES = [("Hall", f"T{i}", 4 if i % 2 else 2) for i in range(1, 9)] + [
    ("Terrace", f"R{i}", 4) for i in range(1, 5)
]

# دليفري مان (الحقول اللي مش موجودة في الـ DocType بتتخطّى لوحدها)
DRIVERS = [("أحمد", "01000000001"), ("محمود", "01000000002")]

# ---------------------------------------------------------------- أدوات

skipped = []  # (DocType, field, السبب)


def _key_field(dt):
    """الحقل اللي بيحدد اسم السجل (للتأكد إنه مش مكرر)."""
    meta = frappe.get_meta(dt)
    ac = meta.autoname or ""
    if ac.startswith("field:"):
        return ac[6:]
    if meta.title_field:
        return meta.title_field
    for c in ("station_name", "table_name", "driver_name", "full_name", "title"):
        if meta.has_field(c):
            return c
    return None


def _ensure(dt, values, key=None, loose=()):
    """يعمل السجل لو مش موجود. بيحط بس الحقول الموجودة فعلًا، ويتخطّى القيم اللي مش من اختيارات الحقل."""
    meta = frappe.get_meta(dt)
    key = key or _key_field(dt)
    if key and values.get(key) and frappe.db.exists(dt, {key: values[key]}):
        return "exists"
    doc = frappe.new_doc(dt)
    for k, v in values.items():
        df = meta.get_field(k)
        if not df:
            skipped.append((dt, k, "الحقل مش موجود"))
            continue
        if df.fieldtype == "Select":
            opts = [o for o in (df.options or "").split("\n") if o]
            if opts and v not in opts:
                if k in loose:
                    v = opts[0]
                else:
                    skipped.append((dt, k, f"القيمة {v!r} مش من الاختيارات"))
                    continue
        if df.fieldtype == "Link" and df.options and not frappe.db.exists(df.options, v):
            skipped.append((dt, k, f"{v!r} مش موجود في {df.options}"))
            continue
        doc.set(k, v)
    try:
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return "created"
    except Exception as e:
        frappe.db.rollback()
        print(f"   ✗ {dt} {values.get(key or '', '')}: {str(e)[:160]}")
        return "failed"


def _run(label, rows, dt, build, key=None, loose=()):
    res = {"created": 0, "exists": 0, "failed": 0}
    for r in rows:
        res[_ensure(dt, build(r), key, loose)] += 1
    print(f"{label}: جديد {res['created']} | موجود {res['exists']} | فشل {res['failed']}")


# ---------------------------------------------------------------- التشغيل

def seed():
    """bench --site SITE execute restaurant_pos.api.demo_data.seed"""
    skipped.clear()
    _run("محطات المطبخ", STATIONS, "Kitchen Station", lambda s: {"station_name": s})
    _run(
        "الأقسام", GROUPS, "Item Group",
        lambda g: {"item_group_name": g, "parent_item_group": "All Item Groups", "is_group": 0},
        key="item_group_name",
    )
    _run(
        "الأصناف", ITEMS, "Item",
        lambda r: {
            "item_code": r[1], "item_name": r[1], "item_group": r[0],
            "stock_uom": "Nos", "is_stock_item": 0, "standard_rate": r[2],
            "kitchen_station": r[3], "prep_time_min": r[4],
            "is_restaurant_item": 1, "available_today": 1,
        },
        key="item_code",
    )
    _run(
        "الترابيز", TABLES, "Restaurant Table",
        lambda r: {"area": r[0], "table_name": r[1], "capacity": r[2]},
        loose=("area",),
    )
    _run(
        "الدليفري مان", DRIVERS, "Delivery Driver",
        lambda r: {"driver_name": r[0], "phone": r[1], "mobile": r[1], "mobile_no": r[1]},
    )
    frappe.clear_cache()
    if skipped:
        print("\nحقول اتخطّت (عادي، بس لو مهمة ابعتلي السطور دي):")
        for dt, k, why in sorted(set(skipped)):
            print(f"   - {dt}.{k}: {why}")
    print("\nخلصنا. افتح الكاشير واعمل Ctrl+Shift+R.")


def remove():
    """يمسح البيانات التجريبية بس (أي حاجة اسمها في القوائم اللي فوق). الصنف المستخدم في أوردرات بيتخفي بدل ما يتمسح."""
    for _g, name, *_ in ITEMS:
        if not frappe.db.exists("Item", name):
            continue
        try:
            frappe.delete_doc("Item", name, ignore_permissions=True, force=True)
        except Exception:
            frappe.db.rollback()
            frappe.db.set_value("Item", name, "disabled", 1)
            print(f"   • {name}: مستخدم في أوردرات، اتخفى بدل المسح")
    for _a, name, _c in TABLES:
        for t in frappe.get_all("Restaurant Table", filters={"table_name": name}, pluck="name"):
            try:
                frappe.delete_doc("Restaurant Table", t, ignore_permissions=True, force=True)
            except Exception:
                frappe.db.rollback()
                print(f"   • ترابيزة {name}: مستخدمة، سيبتها")
    frappe.db.commit()
    frappe.clear_cache()
    print("✓ اتمسحت الأصناف والترابيز التجريبية (الأقسام والمحطات والدليفري مان سيبتهم، امسحهم يدوي لو عايز)")