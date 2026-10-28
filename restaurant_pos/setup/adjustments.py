import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def run():
    """يضيف فيلدات الخصم والضريبة على Restaurant Order. تشغيل مرة واحدة: bench --site <site> execute restaurant_pos.setup.adjustments.run"""
    create_custom_fields({
        "Restaurant Order": [
            {"fieldname": "discount_percent", "label": "Discount %", "fieldtype": "Percent", "insert_after": "discount_amount", "default": "0"},
            {"fieldname": "tax_percent", "label": "Tax %", "fieldtype": "Percent", "insert_after": "discount_percent", "default": "0"},
            {"fieldname": "tax_amount", "label": "Tax Amount", "fieldtype": "Currency", "insert_after": "tax_percent", "read_only": 1},
        ]
    })
    frappe.db.commit()
    frappe.clear_cache(doctype="Restaurant Order")
    print("Discount/Tax fields ready")
