"""فهارس الداتابيز لسرعة الاستعلامات (آمن يتشغّل أكتر من مرة).

التشغيل:
    bench --site mahmoud.local execute restaurant_pos.setup.hardening.run
"""
import frappe

# (DocType, [الأعمدة])
INDEXES = [
    ("Restaurant Order", ["status"]),
    ("Restaurant Order", ["order_type", "creation"]),
    ("Restaurant Order", ["delivery_status"]),
    ("Restaurant Order", ["driver", "assigned_on"]),
    ("Restaurant Order", ["delivered_on"]),
    ("Restaurant Order", ["table"]),
    ("Sales Invoice", ["rp_cashier"]),
    ("Sales Invoice", ["rp_order"]),
    ("Sales Invoice", ["rp_settlement"]),
]


def run():
    done, skipped = [], []
    for doctype, fields in INDEXES:
        label = f"{doctype}({', '.join(fields)})"
        try:
            meta = frappe.get_meta(doctype)
            standard = {"creation", "modified", "name"}
            missing = [f for f in fields if f not in standard and not meta.has_field(f)]
            if missing:
                skipped.append(f"{label}: الحقل مش موجود {missing}")
                continue
            frappe.db.add_index(doctype, fields)
            done.append(label)
        except Exception as e:
            skipped.append(f"{label}: {e}")
    frappe.db.commit()

    print("اتعمل / موجود بالفعل:")
    for x in done:
        print("  +", x)
    if skipped:
        print("اتخطّى:")
        for x in skipped:
            print("  -", x)
