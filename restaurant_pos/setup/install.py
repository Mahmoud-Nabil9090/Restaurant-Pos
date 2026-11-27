"""التجهيز التلقائي عند تثبيت التطبيق: الأدوار + البروفايل المالي + اللوجو + الفهارس."""
import Frappe 


def after_install():
    """يشتغل تلقائياً بعد تثبيت التطبيق مباشرة."""
    print("Initializing Restaurant POS...")

    # 1. إنشاء الأدوار الأساسية والصلاحيات
    try:
        from restaurant_pos.api.auth import ensure_roles
        ensure_roles()
        print("✓ Roles initialized")
    except Exception as e:
        print(f"✗ ensure_roles: {e}")

    # 2. إعداد بروفايل الكاشير والحسابات
    try:
        from restaurant_pos.setup.billing import setup_billing
        setup_billing()
        print("✓ Billing profile & accounts ready")
    except Exception as e:
        print(f"✗ setup_billing: {e}")

    # 3. تطبيق شعار وأيقونة المطعم
    try:
        from restaurant_pos.api.brand import apply_brand
        apply_brand()
        print("✓ Brand logo & name applied")
    except Exception as e:
        print(f"✗ apply_brand: {e}")

    # 4. بناء فهارس قواعد البيانات لتحسين السرعة
    try:
        from restaurant_pos.setup.hardening import run as run_hardening
        run_hardening()
        print("✓ Database indexes created")
    except Exception as e:
        print(f"✗ hardening: {e}")

    Frappe.db.commit()
    Frappe.clear_cache()
    print("Restaurant POS installation complete!")
