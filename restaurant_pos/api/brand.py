"""اللوجو واسم البراند: بيتشغّل مرة واحدة على كل موقع (وتاني لو عملت موقع جديد)."""
import frappe

# الأيقونة المربعة: مناسبة للشريط العلوي (شغالة في الوضع الفاتح والليلي)
ICON = "/assets/restaurant_pos/images/daghta-icon.svg"
# اللوجو الكامل بالاسم: لصفحة تسجيل الدخول (splash_image)
LOGO = "/assets/restaurant_pos/images/daghta-logo.svg"
APP_NAME = "Daghta"


def apply_brand():
    """bench --site SITE execute restaurant_pos.api.brand.apply_brand"""
    frappe.db.set_single_value("Navbar Settings", "app_logo", ICON)
    # الشريط العلوي بيقرا من app_logo بتاع Website Settings (مش Navbar Settings) فبنحط فيه الأيقونة
    frappe.db.set_single_value("Website Settings", "app_logo", ICON)
    # صفحة تسجيل الدخول بتاخد splash_image: هنا اللوجو الكامل
    frappe.db.set_single_value("Website Settings", "splash_image", LOGO)
    frappe.db.set_single_value("Website Settings", "favicon", ICON)
    frappe.db.set_single_value("Website Settings", "app_name", APP_NAME)
    frappe.db.commit()
    frappe.clear_cache()
    print("✓ تم تطبيق اللوجو")
