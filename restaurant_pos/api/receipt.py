"""إيصال الكاشير بمقاس برنتر المطاعم الحراري (80mm أو 58mm) لكل أنواع الأوردرات: صالة / تيك أواي / دليفري.

=====================================================================
خريطة التعديل: عايز تغيّر إيه؟ عدّل فين؟
=====================================================================
  1) اسم المطعم / التليفون / العنوان / التذييل / حجم الخط / المقاس / الكلمات (عربي أو إنجليزي) / عدد النسخ
       -> ملف receipt_settings.json (مش محتاج build ولا restart، بس شغّل write_previews)
  2) ترتيب أجزاء الإيصال، أو إخفاء/إظهار جزء لنوع أوردر معيّن (مثلًا تشيل الكاشير من الدليفري)
       -> الجدول LAYOUTS تحت (القسم 2)
  3) محتوى كل جزء (إيه اللي يتكتب جواه)
       -> دوال block_* (القسم 3): block_header, block_title, block_meta, block_customer, block_items, block_totals, block_status, block_footer
  4) الشكل (الحدود، سُمك الخط، المسافات، حجم عناوين...)
       -> الـ CSS (القسم 4)، وكل سطر عليه شرح
  5) بيانات المعاينة التجريبية
       -> دالة _sample (القسم 6)

=====================================================================
إزاي تشوف التعديل؟
=====================================================================
  بعد أي تعديل في الملف ده أو في receipt_settings.json شغّل:
      bench --site mahmoud.local execute restaurant_pos.api.receipt.write_previews
  وافتح (وريفرش):
      http://mahmoud.local:8000/assets/restaurant_pos/receipt_preview/dine_in.html
      http://mahmoud.local:8000/assets/restaurant_pos/receipt_preview/takeaway.html
      http://mahmoud.local:8000/assets/restaurant_pos/receipt_preview/delivery.html
  لو عدّلت في الملف ده (.py) نفسه: اعمل بعدها `bench restart` عشان الكاشير الحقيقي ياخد التعديل
  (المعاينة بتاخده فورًا بأمر write_previews، لكن الطباعة من الكاشير محتاجة restart).
  أما تعديل receipt_settings.json فمش محتاج restart خالص.

نصيحة: خد نسخة من الملف قبل ما تعدّل (cp receipt.py receipt.py.mybackup)، ولو حصل خطأ في الكتابة الإيصال مش هيطلع.
"""
import json
import os
from datetime import datetime
from html import escape

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, get_fullname

# =====================================================================
# القسم 1: الإعدادات الافتراضية
# =====================================================================
# دي القيم لو الإعداد مش موجود في receipt_settings.json.
# اللي في receipt_settings.json بيغلب على اللي هنا. فمتعدّلش هنا غير لو عايز تغيّر الافتراضي نفسه.
DEFAULTS = {
    # --- المقاس ---
    "paper_width_mm": 80,       # عرض الرول: 80 أو 58 (مللي)
    "print_width_mm": 72,       # العرض اللي بيتطبع فعلًا (أقل من الرول بسبب هوامش البرنتر): 72 لرول 80، و48 لرول 58

    # --- الخط ---
    "font_size_px": 13,         # حجم الخط الأساسي. كبّره لو الكتابة صغيرة على الورق
    "font_family": "Tahoma, Arial, sans-serif",   # نوع الخط (لازم يكون موجود على الجهاز اللي بيطبع)
    "direction": "rtl",         # "rtl" للعربي (من اليمين)، "ltr" للإنجليزي

    # --- بيانات المطعم (بتظهر فوق) ---
    "restaurant_name": "",      # لو فاضي بياخد اسم الشركة من ERPNext
    "subtitle": "",             # سطر تحت الاسم (مثلًا: مأكولات شرقية)
    "address": "",              # عنوان الفرع
    "phone": "",                # تليفون الفرع
    "footer": "شكرًا لزيارتكم",   # كلام آخر الإيصال. تقدر تكتب أكتر من سطر بـ \n

    # --- خيارات العرض ---
    "currency_label": "",       # بيتكتب جنب الإجمالي النهائي (مثلًا: ج.م)
    "show_cashier": True,       # يظهر اسم الكاشير؟
    "show_item_prices": True,   # يظهر سعر الوحدة × الكمية تحت كل صنف؟
    "show_logo": False,         # يظهر لوجو؟ (لازم logo_url)
    "logo_url": "",             # رابط اللوجو، مثلًا /files/logo.png
    "logo_height_px": 60,       # ارتفاع اللوجو
    "copies": 1,                # عدد النسخ اللي تتطبع مع بعض

    # --- عناوين الأنواع (الصندوق اللي تحت الاسم) ---
    "type_titles": {"Dine In": "صالة", "Takeaway": "تيك أواي", "Delivery": "دليفري"},

    # --- كل الكلمات اللي بتظهر في الإيصال. غيّر أي كلمة براحتك ---
    "labels": {
        "order": "أوردر",
        "date": "التاريخ",
        "table": "ترابيزة",
        "cashier": "الكاشير",
        "qty": "الكمية",
        "item": "الصنف",
        "amount": "الإجمالي",
        "subtotal": "المجموع",
        "discount": "خصم",
        "tax": "ضريبة",
        "total": "الإجمالي النهائي",
        "customer": "العميل",
        "phone": "تليفون",
        "address": "العنوان",
        "floor": "دور",
        "notes": "ملاحظات",
        "driver": "الدليفري مان",
        "paid": "مدفوع",
        "invoice": "فاتورة",
        "collect": "المطلوب تحصيله",
    },
}

# حقول العميل اللي بنجيبها من Restaurant Customer (لإيصال الدليفري)
CUSTOMER_FIELDS = ["customer_name", "phone", "phone2", "address", "building_details", "floor", "notes"]


# =====================================================================
# القسم 2: ترتيب أجزاء الإيصال لكل نوع أوردر   <-- من هنا تتحكم في الشكل العام
# =====================================================================
# كل نوع أوردر ليه قايمة بأسماء الأجزاء بالترتيب من فوق لتحت.
# تقدر: تشيل جزء (امسح اسمه)، تقدّمه أو تأخّره (غيّر مكانه)، أو تكرره.
#
# الأجزاء المتاحة:
#   "header"   اللوجو + اسم المطعم + العنوان + التليفون
#   "title"    الصندوق اللي فيه نوع الأوردر (صالة / تيك أواي / دليفري)
#   "meta"     رقم الأوردر + التاريخ + الترابيزة + الكاشير
#   "customer" بيانات العميل والدليفري مان (بتظهر بس لو أوردر دليفري وفيه عميل)
#   "items"    جدول الأصناف
#   "totals"   المجموع + الخصم + الضريبة + الإجمالي النهائي
#   "status"   "مدفوع" أو "المطلوب تحصيله" (للدليفري قبل التسوية)
#   "footer"   كلام الشكر آخر الإيصال
#   "hr"       خط متقطع فاصل
#   "spacer"   مسافة فاضية صغيرة
#
# مثال: عايز تشيل الكاشير من الدليفري؟ ده مش هنا، ده في receipt_settings.json: "show_cashier": false
# مثال: عايز تشيل الفاصل بين الأصناف والإجمالي في التيك أواي؟ امسح الـ "hr" التاني من قايمته.
LAYOUTS = {
    "Dine In": ["header", "title", "meta", "hr", "items", "hr", "totals", "status", "footer"],
    "Takeaway": ["header", "title", "meta", "hr", "items", "hr", "totals", "status", "footer"],
    "Delivery": ["header", "title", "meta", "hr", "customer", "items", "hr", "totals", "status", "footer"],
}


# =====================================================================
# القسم 3: أجزاء الإيصال (كل دالة بترجّع HTML لجزء واحد)
# =====================================================================
# كل دالة بتاخد:
#   d   = بيانات الأوردر (اسمه، نوعه، أصنافه، إجمالياته، العميل...)
#   cfg = الإعدادات (من receipt_settings.json + الافتراضي)
# والنتيجة نص HTML. الـ class بتاعة كل عنصر (زي "name" و"ttl") معمولها شكل في القسم 4 (CSS).
# escape(...) معناها "نضّف النص من أي كود HTML"، متشيلهاش من حاجة جاية من إدخال المستخدم (اسم عميل، ملاحظة...).

def block_header(d, cfg):
    """فوق خالص: لوجو (اختياري) + اسم المطعم + سطر فرعي + عنوان + تليفون."""
    html = ""
    # اللوجو: لازم show_logo = true و logo_url مكتوب في الإعدادات
    if cfg.get("show_logo") and cfg.get("logo_url"):
        html += f'<div class="c"><img src="{escape(cfg["logo_url"])}" style="height:{int(cfg["logo_height_px"])}px"></div>'
    # اسم المطعم: كلاس "name" (خط كبير وبولد)
    if cfg["restaurant_name"]:
        html += f'<div class="c name">{escape(cfg["restaurant_name"])}</div>'
    # الأسطر الصغيرة تحت الاسم، بالترتيب ده. لو عايز تشيل واحد امسحه من القايمة، أو غيّر الترتيب
    for key in ("subtitle", "address", "phone"):
        if cfg.get(key):
            html += f'<div class="c sub">{escape(cfg[key])}</div>'
    return html


def block_title(d, cfg):
    """الصندوق اللي فيه نوع الأوردر. الكلام نفسه من type_titles في الإعدادات."""
    otype = d["order_type"]
    return f'<div class="ttl">{escape(cfg["type_titles"].get(otype, otype))}</div>'


def block_meta(d, cfg):
    """رقم الأوردر والتاريخ، وبعدهم الترابيزة (للصالة بس) والكاشير."""
    L = cfg["labels"]
    # السطر الأول: رقم الأوردر على جنب، والتاريخ والوقت على الجنب التاني
    # صيغة التاريخ: %d/%m/%Y %H:%M يعني يوم/شهر/سنة ساعة:دقيقة. غيّرها لو عايز (مثلًا "%H:%M %d-%m-%Y")
    html = (
        f'<div><span>{escape(L["order"])}: <b>{escape(d["order"])}</b></span>'
        f'<span>{d["when"].strftime("%d/%m/%Y %H:%M")}</span></div>'
    )
    # الترابيزة: بتظهر بس في الصالة
    if d["order_type"] == "Dine In" and d["table"]:
        html += f'<div><span>{escape(L["table"])}: <b>{escape(d["table"])}</b></span></div>'
    # الكاشير: بيتحكم فيه show_cashier في الإعدادات. كلاس "small" = خط أصغر
    if cfg.get("show_cashier") and d.get("cashier"):
        html += f'<div class="small"><span>{escape(L["cashier"])}: {escape(d["cashier"])}</span></div>'
    return f'<div class="meta">{html}</div>'


def block_customer(d, cfg):
    """صندوق بيانات العميل (للدليفري بس): الاسم، التليفونات، العنوان، الدور، الملاحظات، الدليفري مان."""
    c = d.get("customer")
    if d["order_type"] != "Delivery" or not c:
        return ""   # مش دليفري أو مفيش بيانات عميل: مفيش حاجة تتعرض
    L = cfg["labels"]
    e = escape
    # التليفون التاني بيتكتب جنب الأول بعد "/"
    phones = e(c.get("phone") or "") + (f" / {e(c['phone2'])}" if c.get("phone2") else "")
    # تفاصيل العمارة + الدور في سطر واحد، متفصولين بنقطة
    place = " · ".join(
        x for x in [c.get("building_details"), f"{L['floor']} {c['floor']}" if c.get("floor") else ""] if x
    )
    # كل سطر هنا ممكن تشيله أو تغيّر مكانه. كلاس "box" = إطار حوالين البيانات
    html = '<div class="box">'
    html += f'<div><b>{e(L["customer"])}:</b> {e(c.get("customer_name") or "")}</div>'
    html += f'<div><b>{e(L["phone"])}:</b> <span dir="ltr">{phones}</span></div>'   # dir="ltr" عشان الأرقام تتقري صح
    html += f'<div><b>{e(L["address"])}:</b> {e(c.get("address") or "")}</div>'
    if place:
        html += f"<div>{e(place)}</div>"
    if c.get("notes"):
        html += f'<div class="small"><b>{e(L["notes"])}:</b> {e(c["notes"])}</div>'
    if d.get("driver"):
        html += f'<div><b>{e(L["driver"])}:</b> {e(d["driver"])}</div>'
    return html + "</div>"


def block_items(d, cfg):
    """جدول الأصناف: الكمية | اسم الصنف (وتحته السعر والملاحظة) | الإجمالي."""
    L = cfg["labels"]
    e = escape
    rows = ""
    for i in d["items"]:
        sub = ""
        # سطر السعر × الكمية تحت اسم الصنف، بيتحكم فيه show_item_prices
        if cfg.get("show_item_prices"):
            sub += f'<div class="note">{_m(i["rate"])} × {i["qty"]:g}</div>'
        # ملاحظة المطبخ على الصنف (مثلًا: من غير بصل)
        if i.get("notes"):
            sub += f'<div class="note">- {e(i["notes"])}</div>'
        # الصف: الكمية (qty) | الاسم + sub | إجمالي السطر (amt)
        rows += (
            f'<tr><td class="qty">{i["qty"]:g}×</td><td>{e(i["name"])}{sub}</td>'
            f'<td class="amt">{_m(i["qty"] * i["rate"])}</td></tr>'
        )
    # رأس الجدول (الكمية / الصنف / الإجمالي). لو عايز تشيله امسح الـ <thead>...</thead>
    return (
        f'<table><thead><tr><th>{e(L["qty"])}</th><th>{e(L["item"])}</th>'
        f'<th class="amt">{e(L["amount"])}</th></tr></thead><tbody>{rows}</tbody></table>'
    )


def block_totals(d, cfg):
    """المجموع، الخصم، الضريبة، والإجمالي النهائي. الخصم والضريبة بيظهروا بس لو موجودين."""
    L = cfg["labels"]
    e = escape
    t = d["totals"]
    # العملة بتتكتب جنب الإجمالي النهائي بس
    cur = f" {e(cfg['currency_label'])}" if cfg.get("currency_label") else ""
    html = ""
    # "المجموع" بيظهر بس لو فيه خصم أو ضريبة (غير كده هو نفس الإجمالي)
    if t["discount"] or t["tax"]:
        html += f'<div><span>{e(L["subtotal"])}</span><span>{_m(t["subtotal"])}</span></div>'
    if t["discount"]:
        pct = f' {t["discount_percent"]:g}%' if t["discount_percent"] else ""
        html += f'<div><span>{e(L["discount"])}{pct}</span><span>- {_m(t["discount"])}</span></div>'
    if t["tax"]:
        html += f'<div><span>{e(L["tax"])} {t["tax_percent"]:g}%</span><span>+ {_m(t["tax"])}</span></div>'
    # الإجمالي النهائي: كلاس "grand" (خط كبير وبين خطين)
    html += f'<div class="grand"><span>{e(L["total"])}</span><span>{_m(t["total"])}{cur}</span></div>'
    return f'<div class="tot">{html}</div>'


def block_status(d, cfg):
    """تحت الإجمالي: "✓ مدفوع" لو الأوردر اتدفع، أو "المطلوب تحصيله" للدليفري اللي لسه ما اتسواش."""
    L = cfg["labels"]
    cur = f" {escape(cfg['currency_label'])}" if cfg.get("currency_label") else ""
    if d["paid"]:
        inv = f' · {escape(d["invoice"])}' if d.get("invoice") else ""    # رقم الفاتورة جنب كلمة مدفوع
        return f'<div class="paid">✓ {escape(L["paid"])}{inv}</div>'
    if d["order_type"] == "Delivery":
        # كلاس "due" = إطار متقطع علشان الدليفري مان يشوف المبلغ بسهولة
        return f'<div class="due">{escape(L["collect"])}: {_m(d["totals"]["total"])}{cur}</div>'
    return ""


def block_footer(d, cfg):
    """آخر الإيصال: كلام الشكر. \\n في النص بتبقى سطر جديد."""
    if not cfg.get("footer"):
        return ""
    return '<div class="foot">' + escape(cfg["footer"]).replace("\n", "<br>") + "</div>"


def block_hr(d, cfg):
    """خط متقطع فاصل."""
    return '<div class="hr"></div>'


def block_spacer(d, cfg):
    """مسافة فاضية صغيرة (غيّر الارتفاع هنا لو عايز مسافة أكبر)."""
    return '<div style="height:8px"></div>'


# الاسم اللي بتكتبه في LAYOUTS -> الدالة اللي بتتنفذ. لو عملت جزء جديد ضيفه هنا وفي LAYOUTS.
BLOCKS = {
    "header": block_header,
    "title": block_title,
    "meta": block_meta,
    "customer": block_customer,
    "items": block_items,
    "totals": block_totals,
    "status": block_status,
    "footer": block_footer,
    "hr": block_hr,
    "spacer": block_spacer,
}


def _receipt_body(d, cfg):
    """بيجمّع أجزاء الإيصال حسب LAYOUTS لنوع الأوردر ده."""
    names = LAYOUTS.get(d["order_type"]) or LAYOUTS["Dine In"]
    parts = []
    for name in names:
        fn = BLOCKS.get(name)
        if not fn:
            # لو كتبت اسم جزء غلط في LAYOUTS هتظهر الرسالة دي
            frappe.throw(_("receipt.py: الجزء '{0}' مش موجود. الأجزاء المتاحة: {1}").format(name, ", ".join(BLOCKS)))
        parts.append(fn(d, cfg))
    return f'<div class="rc">{"".join(parts)}</div>'


# =====================================================================
# القسم 4: الشكل (CSS)
# =====================================================================
# الأرقام اللي شكلها %%XXX%% بتتبدل بقيم الإعدادات تلقائيًا (متمسحهاش).
# وحدة em معناها "نسبة من حجم الخط الأساسي": 1.4em = 1.4 ضعف الخط العادي.
CSS = """
/* حجم الورقة: العرض من الإعدادات، والطول تلقائي على حسب المحتوى، من غير هوامش */
@page { size: %%PAPER%%mm auto; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fff; }

/* الخط الأساسي لكل الإيصال (النوع والحجم والاتجاه من الإعدادات) */
body { font-family: %%FONT%%; font-size: %%FS%%px; color: #000; direction: %%DIR%%; }

/* الإيصال نفسه: العرض المطبوع، ومسافة فوق (2mm) وتحت (5mm) علشان القطع، وتباعد الأسطر 1.4 */
.rc { width: %%PW%%mm; margin: 0 auto; padding: 2mm 0 5mm; line-height: 1.4; page-break-after: always; }
.rc:last-of-type { page-break-after: auto; }

/* نص في النص */
.c { text-align: center; }

/* اسم المطعم: كبّر الرقم 1.55em لو عايزه أكبر */
.name { font-size: 1.55em; font-weight: 800; }

/* الأسطر الصغيرة (العنوان، التليفون، الكاشير، الملاحظات): .88 يعني أصغر 12% من الأساسي */
.sub, .small { font-size: .88em; }

/* صندوق نوع الأوردر (صالة/تيك أواي/دليفري): سُمك الإطار 2px، وحجم الخط 1.35em */
.ttl { border: 2px solid #000; font-size: 1.35em; font-weight: 800; text-align: center; margin: 6px 0; padding: 3px 0; }

/* سطور رقم الأوردر والإجماليات: كل سطر على الجانبين (الاسم يمين والقيمة شمال) */
.meta > div, .tot > div { display: flex; justify-content: space-between; gap: 8px; }

/* الخط المتقطع الفاصل. غيّر dashed لـ solid لو عايزه خط كامل */
.hr { border-top: 1px dashed #000; margin: 6px 0; }

/* صندوق بيانات عميل الدليفري */
.box { border: 1px solid #000; padding: 4px 6px; margin: 6px 0; }
.box b { font-weight: 700; }

/* جدول الأصناف */
table { width: 100%; border-collapse: collapse; }
th { border-bottom: 1px solid #000; font-weight: 700; text-align: start; padding: 2px 0; font-size: .92em; }
td { padding: 3px 0; vertical-align: top; }

/* عمود الكمية (عرضه 2.6em) واسم الصنف ياخد الباقي */
.qty { width: 2.6em; font-weight: 800; }

/* عمود المبلغ على الطرف التاني، من غير ما الرقم ينكسر لسطرين */
.amt { text-align: end; white-space: nowrap; font-weight: 700; }

/* السطر الصغير تحت الصنف (السعر × الكمية، والملاحظة) */
.note { font-size: .85em; }

/* الإجمالي النهائي: خط كبير 1.4em وبين خطين */
.grand { font-size: 1.4em; font-weight: 800; border-top: 2px solid #000; border-bottom: 2px solid #000; padding: 3px 0; margin-top: 5px; }

/* كلمة "مدفوع" */
.paid { text-align: center; font-weight: 800; margin-top: 6px; }

/* "المطلوب تحصيله" للدليفري: إطار متقطع */
.due { text-align: center; font-weight: 800; font-size: 1.15em; border: 2px dashed #000; padding: 4px; margin-top: 6px; }

/* كلام الشكر آخر الإيصال */
.foot { text-align: center; margin-top: 8px; font-size: .92em; }

/* ---- من هنا لتحت: شكل صفحة المعاينة بس، ما بيأثرش على الطباعة ---- */
.bar { display: none; }
.preview { background: #d1d5db; padding-bottom: 40px; }
.preview .bar { display: flex; gap: 12px; align-items: center; justify-content: center; padding: 10px; background: #111827; color: #fff; font: 13px Arial, sans-serif; direction: ltr; }
.preview .bar button { padding: 6px 16px; border-radius: 6px; border: 0; background: #f97316; color: #fff; font-weight: 700; cursor: pointer; }
.preview .rc { background: #fff; margin: 16px auto; padding: 4mm 3mm 6mm; box-shadow: 0 2px 12px rgba(0,0,0,.25); page-break-after: auto; }
@media print { .preview { background: #fff; padding: 0; } .preview .bar { display: none; } .preview .rc { margin: 0 auto; padding: 2mm 0 5mm; box-shadow: none; } }
"""


# =====================================================================
# القسم 5: أدوات مساعدة (مش محتاج تعدّل فيها غالبًا)
# =====================================================================

def _flag(v):
    """يحوّل 1 / "1" / "true" / "yes" إلى True."""
    return str(v or "").lower() in ("1", "true", "yes")


def _merge(base, user):
    """يدمج إعدادات المستخدم فوق الافتراضي. أي مفتاح بيبدأ بـ _ بيتتجاهل (ده مكان الشرح في ملف الإعدادات)."""
    for k, v in user.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v


def _cfg():
    """يقرا receipt_settings.json ويدمجه فوق DEFAULTS. بيتقري في كل طباعة، فتعديل الملف بيبان على طول."""
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(frappe.get_app_path("restaurant_pos", "receipt_settings.json"), encoding="utf-8") as f:
            user = json.load(f)
    except FileNotFoundError:
        user = {}
    except ValueError as e:
        # غالبًا نسيت فاصلة أو علامة تنصيص في الـ JSON
        frappe.throw(_("receipt_settings.json فيه خطأ في الكتابة: {0}").format(e))
    _merge(cfg, user)
    if not cfg["restaurant_name"]:
        cfg["restaurant_name"] = frappe.defaults.get_global_default("company") or ""
    return cfg


def _m(v):
    """تنسيق المبلغ: خانتين عشريتين وفاصل آلاف (1,234.50)."""
    return f"{flt(v, 2):,.2f}"


def _totals(items, discount_percent, discount_amount, tax_percent):
    """نفس معادلة الأوردر والفاتورة بالظبط: الخصم على المجموع الأول، وبعدين الضريبة على الباقي.
    متغيّرش المعادلة دي هنا لوحدها، لأنها لازم تتطابق مع billing.py."""
    subtotal = flt(sum(i["qty"] * i["rate"] for i in items), 2)
    pct = flt(discount_percent)
    discount = flt(subtotal * pct / 100, 2) if pct else flt(discount_amount, 2)
    tax = flt((subtotal - discount) * flt(tax_percent) / 100, 2)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "discount_percent": pct,
        "tax": tax,
        "tax_percent": flt(tax_percent),
        "total": flt(subtotal - discount + tax, 2),
    }


def _from_order(name):
    """يجمّع كل بيانات الأوردر الحقيقي اللي الإيصال محتاجها (الأصناف الملغية مش بتدخل)."""
    doc = frappe.get_doc("Restaurant Order", name)
    items = [
        {"name": r.item_name, "qty": flt(r.qty), "rate": flt(r.rate), "notes": r.notes or ""}
        for r in doc.items
        if r.kitchen_status != "Cancelled"
    ]
    customer = None
    if doc.order_type == "Delivery" and doc.get("delivery_customer"):
        customer = frappe.db.get_value(
            "Restaurant Customer", doc.delivery_customer, CUSTOMER_FIELDS, as_dict=True
        )
    driver = ""
    if doc.get("driver"):
        driver = frappe.db.get_value("Delivery Driver", doc.driver, "driver_name") or doc.driver
    table = ""
    if doc.get("table"):
        table = frappe.db.get_value("Restaurant Table", doc.table, "table_name") or doc.table

    invoice = doc.get("sales_invoice")
    # الكاشير = اللي استلم الفلوس (متسجّل على الفاتورة). لو مفيش فاتورة لسه، اليوزر الحالي
    cashier_user = (
        (frappe.db.get_value("Sales Invoice", invoice, "rp_cashier") if invoice else None) or frappe.session.user
    )
    return {
        "order": doc.name,
        "order_type": doc.order_type,
        "table": table,
        "when": get_datetime(doc.creation),
        "items": items,
        "totals": _totals(items, doc.get("discount_percent"), doc.get("discount_amount"), doc.get("tax_percent")),
        "customer": customer,
        "driver": driver,
        "paid": doc.status == "Billed",
        "invoice": invoice or "",
        "cashier": get_fullname(cashier_user),
    }


# =====================================================================
# القسم 6: بيانات المعاينة التجريبية
# =====================================================================
def _sample(order_type):
    """أوردر وهمي بيتعرض في صفحات المعاينة. غيّر الأصناف والأسماء كمان تجرّب شكل أسماء طويلة."""
    items = [
        {"name": "برجر لحم دبل", "qty": 2, "rate": 120, "notes": "من غير بصل"},
        {"name": "بطاطس كبيرة", "qty": 1, "rate": 45, "notes": ""},
        {"name": "بيبسي", "qty": 3, "rate": 20, "notes": ""},
    ]
    customer = None
    if order_type == "Delivery":
        customer = {
            "customer_name": "أحمد محمد",
            "phone": "01012345678",
            "phone2": "01198765432",
            "address": "شارع الجمهورية، أمام الصيدلية",
            "building_details": "عمارة 12 شقة 5",
            "floor": "3",
            "notes": "الجرس بايظ، اتصل",
        }
    return {
        "order": "RO-00123",
        "order_type": order_type,
        "table": "T5" if order_type == "Dine In" else "",
        "when": datetime.now(),
        "items": items,
        "totals": _totals(items, 10, 0, 14),     # (أصناف، خصم %، خصم مبلغ، ضريبة %): غيّر الأرقام تجرّب
        "customer": customer,
        "driver": "محمود" if order_type == "Delivery" else "",
        "paid": order_type != "Delivery",         # الدليفري بيبان "لسه مدفوعش" عشان تشوف "المطلوب تحصيله"
        "invoice": "ACC-PSINV-00045" if order_type != "Delivery" else "",
        "cashier": "كاشير 1",
    }


# =====================================================================
# القسم 7: تجميع الصفحة وأوامر الاستدعاء
# =====================================================================
def _page(d, cfg, preview, autoprint):
    """يبني صفحة HTML كاملة. preview=True بيضيف شريط فوق فيه زرار Print. autoprint=True بيطبع أول ما الصفحة تفتح."""
    css = (
        CSS.replace("%%PAPER%%", str(cfg["paper_width_mm"]))
        .replace("%%PW%%", str(cfg["print_width_mm"]))
        .replace("%%FS%%", str(cfg["font_size_px"]))
        .replace("%%FONT%%", cfg["font_family"])
        .replace("%%DIR%%", "ltr" if cfg["direction"] == "ltr" else "rtl")
    )
    # عدد النسخ: كل نسخة صفحة لوحدها على الرول
    body = "".join(_receipt_body(d, cfg) for _i in range(max(1, int(cfg.get("copies") or 1))))
    bar = ""
    if preview:
        bar = (
            f'<div class="bar"><span>Receipt preview · paper {cfg["paper_width_mm"]}mm · '
            f'printable {cfg["print_width_mm"]}mm</span>'
            '<button onclick="window.print()">Print</button></div>'
        )
    script = ""
    if autoprint:
        script = "<script>window.addEventListener('load',function(){setTimeout(function(){window.print()},200)});</script>"
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(d['order'])}</title><style>{css}</style></head>"
        f'<body class="{"preview" if preview else ""}">{bar}{body}{script}</body></html>'
    )


@frappe.whitelist()
def render_html(name, autoprint=1):
    """بيرجّع HTML الإيصال كنص (شاشة الكاشير والدليفري بتحطه في iframe مخفي وتطبعه)."""
    d = _from_order(name)
    return _page(d, _cfg(), False, _flag(autoprint))


def write_previews(name=None):
    """بيكتب ملفات معاينة (صالة/تيك أواي/دليفري) تتفتح من المتصفح بالمقاس الحقيقي. name = أوردر حقيقي (اختياري)."""
    cfg = _cfg()
    folder = frappe.get_app_path("restaurant_pos", "public", "receipt_preview")
    os.makedirs(folder, exist_ok=True)
    files = {"dine_in": "Dine In", "takeaway": "Takeaway", "delivery": "Delivery"}
    for fname, otype in files.items():
        path = os.path.join(folder, fname + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_page(_sample(otype), cfg, True, False))
        print("✓", path)
    if name:
        path = os.path.join(folder, "order.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(_page(_from_order(name), cfg, True, False))
        print("✓", path)
    print("افتح: http://mahmoud.local:8000/assets/restaurant_pos/receipt_preview/dine_in.html (أو takeaway / delivery / order)")
