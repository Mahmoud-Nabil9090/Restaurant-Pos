frappe.pages["cashier"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Restaurant Cashier"),
		single_column: true,
	});
	wrapper.cashier = new RestaurantCashier(wrapper);
};

frappe.pages["cashier"].on_page_show = function (wrapper) {
	if (!wrapper.cashier) return;
	wrapper.cashier.load_tables();
	wrapper.cashier.open_from_route();
};

const RP_TILE_COLORS = ["#ff8a3d", "#ffb703", "#e5484d", "#a8643a", "#5fa86b", "#e8693a", "#4c7bd9", "#d9619a", "#7bb661", "#8a5a3c"];

class RestaurantCashier {
	// المُنشئ: يجهّز الحالة (المنيو/الترابيزات/الأوردر)، يرسم الشاشة، ويسمع أحداث المطبخ realtime
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.menu = { groups: [], items: [] };
		this.menu_loaded = false;
		this.tables = [];
		this.tables_loaded = false;
		this.group = null;
		this.editing_customer = false;
		this.form_values = null;
		this.order = this.empty_order();
		this.render_shell();
		this.bind_events();
		this.render_all();
		this.load_menu();
		this.load_tables();
		frappe.realtime.on("kitchen_new_ticket", () => this.load_tables());
		frappe.realtime.on("kitchen_item_cancelled", () => this.load_tables());
	}

	/* ---------- state helpers ---------- */

	// يرجّع أوردر جديد فاضي بنوع الطلب (صالة/تيك أواى/دليفرى)
	empty_order(order_type = "Dine In", table = null, customer_info = null) {
		return { name: null, order_type, table, items: [], status: "Open", customer_info };
	}

	// يحط أوردر كأوردر حالي ويعيد رسم الشاشة كلها
	set_order(order) {
		this.order = order;
		this.group = null;
		this.editing_customer = false;
		this.form_values = null;
		this.render_all();
	}

	// يحدد المنطقة اللي في النص: tables / form / categories / items
	current_view() {
		const o = this.order;
		if (o.order_type === "Dine In" && !o.table) return "tables";
		if (o.order_type === "Delivery" && (!o.customer_info || this.editing_customer)) return "form";
		return this.group ? "items" : "categories";
	}

	// تنظيف النص من أكواد HTML قبل عرضه (حماية)
	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	// تنسيق المبلغ بخانتين عشريتين + العملة
	money(v) {
		const cur = (frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "";
		return `${Number(v || 0).toFixed(2)} ${cur}`.trim();
	}

	// لون ثابت للصنف/التصنيف لو مفيش صورة، حسب اسمه
	tile_color(text) {
		let h = 0;
		for (const ch of String(text)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
		return RP_TILE_COLORS[h % RP_TILE_COLORS.length];
	}

	// أول حرفين من الاسم لعرضهم لو مفيش صورة
	initials(name) {
		return String(name || "")
			.split(" ")
			.filter(Boolean)
			.map((w) => w[0])
			.join("")
			.slice(0, 2)
			.toUpperCase();
	}

	// فتح أوردر جاي من شاشة الدليفري (زرار Edit)
	open_from_route() {
		const name = frappe.route_options && frappe.route_options.order;
		if (!name) return;
		frappe.route_options = null;
		frappe.call({
			method: "restaurant_pos.api.get_order",
			args: { name },
			callback: (r) => this.set_order(this.from_doc(r.message)),
		});
	}

	// بعد حفظ/إرسال أوردر دليفري: يفضّي الشاشة ويبلّغ إنه راح لشاشة الدليفري
	finish_delivery(name) {
		this.set_order(this.empty_order("Dine In", null));
		this.load_tables();
		frappe.show_alert({
			message: __("{0} moved to Delivery Orders", [name]),
			indicator: "blue",
		});
	}

	/* ---------- shell ---------- */

	// يرسم الهيكل الثابت للصفحة (الستايل في ملف cashier.css)
	render_shell() {
		const main = $(this.page.main);
		main.html(`
			<div class="rp">
				<div class="rp-center"></div>
				<div class="rp-cartbox">
					<div class="rp-head"></div>
					<div class="rp-custbox"></div>
					<div class="rp-cart"></div>
					<div class="rp-totals">
						<div class="rp-total"><span>${__("Total")}</span><span class="rp-sum">0.00</span></div>
					</div>
					<div class="rp-actions">
						<button class="rp-save">${__("Save")}</button>
						<button class="rp-send">${__("Send to Kitchen")}</button>
						<button class="rp-pay">${__("Pay")}</button>
						<button class="rp-cancel">${__("Cancel Order")}</button>
					</div>
				</div>
				<div class="rp-rail">
					<div class="rp-label">${__("ORDER TYPE")}</div>
					<div class="rp-types"></div>
					<button class="rp-board">${__("Delivery Orders")}</button>
					<div class="rp-open"><span>${__("Open orders")}</span><b class="rp-open-count">0</b></div>
				</div>
			</div>
		`);
		this.$root = main;
	}

	// ربط كل الضغطات (كليك) بالدوال المناسبة
	bind_events() {
		const r = this.$root;
		r.on("click", ".rp-tcard", (e) => this.select_table($(e.currentTarget).data("table")));
		r.on("click", ".rp-cat", (e) => {
			this.group = $(e.currentTarget).data("group");
			this.render_center();
		});
		r.on("click", ".rp-back-cats", () => {
			this.group = null;
			this.render_center();
		});
		r.on("click", ".rp-change-table", () => this.change_table());
		r.on("click", ".rp-item", (e) => this.add_item($(e.currentTarget).data("item")));
		r.on("click", ".rp-type", (e) => this.set_type($(e.currentTarget).data("type")));
		r.on("click", ".rp-plus", (e) => this.change_qty($(e.currentTarget).data("i"), 1));
		r.on("click", ".rp-minus", (e) => this.change_qty($(e.currentTarget).data("i"), -1));
		r.on("click", ".rp-note", (e) => this.edit_note($(e.currentTarget).data("i")));
		r.on("click", ".rp-cancel-item", (e) => this.cancel_sent_item($(e.currentTarget).data("i")));
		r.on("click", ".rp-edit-cust", () => {
			this.editing_customer = true;
			this.form_values = null;
			this.render_center();
		});
		r.on("change", ".rp-f-phone", (e) => this.lookup_customer($(e.currentTarget).val()));
		r.on("click", ".rp-form-ok", () => this.submit_customer());
		r.on("click", ".rp-form-cancel", () => this.cancel_form());
		r.on("click", ".rp-board", () => frappe.set_route("delivery-orders"));
		r.on("click", ".rp-save", () => this.save());
		r.on("click", ".rp-send", () => this.send());
		r.on("click", ".rp-pay", () => this.pay());
		r.on("click", ".rp-cancel", () => this.cancel());
	}

	/* ---------- data ---------- */

	// تحميل المنيو (التصنيفات والأصناف والصور) من السيرفر
	load_menu() {
		frappe.call({
			method: "restaurant_pos.api.get_menu",
			callback: (r) => {
				this.menu = r.message;
				this.menu_loaded = true;
				const v = this.current_view();
				if (v === "categories" || v === "items") this.render_center();
			},
		});
	}

	// تحميل حالة الترابيزات وتحديث عداد الأوردرات المفتوحة
	load_tables() {
		frappe.call({
			method: "restaurant_pos.api.get_tables",
			callback: (r) => {
				this.tables = r.message || [];
				this.tables_loaded = true;
				this.$root.find(".rp-open-count").text(this.tables.filter((t) => t.current_order).length);
				if (this.current_view() === "tables") this.render_center();
			},
		});
	}

	/* ---------- rendering ---------- */

	// إعادة رسم أنواع الطلب + السلة + المنطقة الوسطى
	render_all() {
		this.render_types();
		this.render_cart();
		this.render_center();
	}

	// رسم أزرار نوع الطلب (Dine In / Takeaway / Delivery) على اليمين
	render_types() {
		const defs = [
			["Dine In", __("Dine In"), __("Tables")],
			["Takeaway", __("Takeaway"), __("Pick up")],
			["Delivery", __("Delivery"), __("Driver")],
		];
		const html = defs
			.map(
				([val, label, sub]) =>
					`<button class="rp-type ${this.order.order_type === val ? "active" : ""}" data-type="${val}">
						<b>${this.esc(label)}</b><small>${this.esc(sub)}</small>
					</button>`
			)
			.join("");
		this.$root.find(".rp-types").html(html);
	}

	// رسم المنطقة الوسطى حسب الحالة: ترابيزات / فورم دليفرى / تصنيفات / أصناف
	render_center() {
		const v = this.current_view();
		const box = this.$root.find(".rp-center");
		if (v === "tables") box.html(this.tables_html());
		else if (v === "form") box.html(this.form_html());
		else box.html(this.menu_html(v));
	}

	// HTML كروت الترابيزات (فاضية/مشغولة)
	tables_html() {
		const head = `<div class="rp-crumb"><b>${__("Select a table")}</b></div>`;
		if (!this.tables_loaded) return head + `<div class="rp-empty">${__("Loading...")}</div>`;
		if (!this.tables.length) return head + `<div class="rp-empty">${__("No tables defined")}</div>`;
		const cards = this.tables
			.map((t) => {
				const cls = t.status === "Occupied" ? "occupied" : t.status === "Reserved" ? "reserved" : "";
				return `<button class="rp-tcard ${cls}" data-table="${this.esc(t.name)}">
					<span class="rp-tname">${this.esc(t.table_name)}</span>
					<span class="rp-tmeta">${this.esc(t.area)} · ${this.esc(t.capacity)} ${__("seats")}</span>
					<span class="rp-tstatus">${this.esc(__(t.status))}</span>
				</button>`;
			})
			.join("");
		return head + `<div class="rp-cards">${cards}</div>`;
	}

	// تجهيز رابط الصورة ليصلح داخل background-image
	css_url(img) {
		return encodeURI(img).replace(/'/g, "%27");
	}

	// HTML كروت التصنيفات أو الأصناف + شريط التنقل (breadcrumb)
	menu_html(view) {
		const o = this.order;
		let crumb = "";
		if (o.order_type === "Dine In") {
			crumb += `<button class="rp-link rp-change-table">← ${__("Tables")}</button><b>${__("Table")} ${this.esc(o.table)}</b>`;
		} else {
			crumb += `<b>${this.esc(__(o.order_type))}</b>`;
		}
		if (view === "items") {
			crumb += `<span class="rp-sep">/</span><button class="rp-link rp-back-cats">← ${__("Categories")}</button><b>${this.esc(this.group)}</b>`;
		}
		const head = `<div class="rp-crumb">${crumb}</div>`;

		if (!this.menu_loaded) return head + `<div class="rp-empty">${__("Loading...")}</div>`;
		if (!this.menu.groups.length) return head + `<div class="rp-empty">${__("No menu items yet")}</div>`;

		if (view === "categories") {
			const cards = this.menu.groups
				.map((g) => {
					const items = this.menu.items.filter((i) => i.item_group === g);
					const img = (this.menu.group_images || {})[g] || (items.find((i) => i.image) || {}).image;
					const pic = img
						? `background-image:url('${this.css_url(img)}')`
						: `background:${this.tile_color(g)}`;
					const inner = img ? "" : this.esc(this.initials(g));
					return `<button class="rp-cat" data-group="${this.esc(g)}">
						<div class="rp-pic" style="${pic}">${inner}</div>
						<div class="rp-capt"><b>${this.esc(g)}</b><span>${items.length} ${__("items")}</span></div>
					</button>`;
				})
				.join("");
			return head + `<div class="rp-cards big">${cards}</div>`;
		}

		const cards = this.menu.items
			.filter((i) => i.item_group === this.group)
			.map((i) => {
				const pic = i.image
					? `background-image:url('${this.css_url(i.image)}')`
					: `background:${this.tile_color(i.item_name)}`;
				const inner = i.image ? "" : this.esc(this.initials(i.item_name));
				return `<button class="rp-item" data-item="${this.esc(i.name)}">
					<div class="rp-pic" style="${pic}">${inner}</div>
					<div class="rp-info"><b>${this.esc(i.item_name)}</b><span>${this.esc(this.money(i.standard_rate))}</span></div>
				</button>`;
			})
			.join("");
		return head + `<div class="rp-cards">${cards}</div>`;
	}

	// HTML فورم بيانات عميل الدليفرى (تليفون، اسم، عنوان...)
	form_html() {
		const v = this.form_values || this.order.customer_info || {};
		const val = (k) => this.esc(v[k] || "");
		const editing = !!this.order.customer_info && this.editing_customer;
		return `
			<div class="rp-formwrap">
				<div class="rp-form">
					<div class="rp-form-title">🛵 ${__("Delivery customer")}</div>
					<label class="s3">${__("Phone")} *
						<input class="rp-f rp-f-phone" data-f="phone" inputmode="tel" value="${val("phone")}" ${editing ? "readonly" : ""} autofocus>
					</label>
					<label class="s3">${__("Customer Name")} *
						<input class="rp-f" data-f="customer_name" value="${val("customer_name")}">
					</label>
					<label class="s2">${__("Second Phone")}
						<input class="rp-f" data-f="phone2" inputmode="tel" value="${val("phone2")}">
					</label>
					<label class="s3">${__("Building / Apartment")}
						<input class="rp-f" data-f="building_details" value="${val("building_details")}">
					</label>
					<label class="s1">${__("Floor")}
						<input class="rp-f" data-f="floor" value="${val("floor")}">
					</label>
					<label class="s6">${__("Address")} *
						<textarea class="rp-f" data-f="address">${val("address")}</textarea>
					</label>
					<label class="s6">${__("Notes")}
						<input class="rp-f" data-f="notes" value="${val("notes")}">
					</label>
					<div class="rp-form-foot">
						<span class="rp-form-msg"></span>
						<button class="rp-form-cancel">${__("Cancel")}</button>
						<button class="rp-form-ok">${__("OK")}</button>
					</div>
				</div>
			</div>`;
	}

	// عرض بيانات عميل الدليفرى أعلى السلة
	render_customer() {
		const o = this.order;
		const c = o.customer_info;
		if (o.order_type !== "Delivery" || !c) {
			this.$root.find(".rp-custbox").html("");
			return;
		}
		const place = [c.building_details, c.floor ? `${__("Floor")} ${c.floor}` : ""].filter(Boolean).join(" · ");
		const lines = [
			`<b>${this.esc(c.customer_name)}</b> <a class="rp-edit-cust">${__("Edit")}</a>`,
			`${this.esc(c.phone)}${c.phone2 ? " / " + this.esc(c.phone2) : ""}`,
			this.esc(c.address),
			place ? this.esc(place) : "",
			c.notes ? "📝 " + this.esc(c.notes) : "",
			o.driver ? "🛵 " + this.esc(o.driver) : "",
		].filter(Boolean);
		this.$root.find(".rp-custbox").html(`<div class="rp-cust">${lines.join("<br>")}</div>`);
	}

	// رسم السلة: الأصناف والكميات والملاحظات والإجمالي وحالة الأزرار
	render_cart() {
		const o = this.order;
		const title =
			o.order_type === "Dine In"
				? `${__("Dine In")}${o.table ? " · " + this.esc(o.table) : ""}`
				: this.esc(__(o.order_type));
		const meta = o.name ? `${this.esc(o.name)} · ${this.esc(o.status)}` : __("New");
		this.$root.find(".rp-head").html(`<b>${title}</b><small>${meta}</small>`);
		this.render_customer();

		let sum = 0;
		const lines = o.items
			.map((row, i) => {
				if (row.kitchen_status === "Cancelled") {
					return `<div class="rp-line rp-cancelled">
						<div class="row-top">
							<span class="rp-strike">${this.esc(row.item_name)} × ${row.qty}</span>
							<span class="rp-cancel-tag">✕ ${__("cancelled")}</span>
						</div>
					</div>`;
				}
				const amount = (row.qty || 0) * (row.rate || 0);
				sum += amount;
				return `<div class="rp-line">
					<div class="row-top">
						<span>${this.esc(row.item_name)}</span>
						<span class="rp-qty">
							<button class="rp-minus" data-i="${i}">−</button>
							<b>${row.qty}</b>
							<button class="rp-plus" data-i="${i}">+</button>
						</span>
						<b>${this.esc(this.money(amount))}</b>
					</div>
					<div>
						<a class="rp-note" data-i="${i}">${row.notes ? "📝 " + this.esc(row.notes) : __("Add note")}</a>
						${
							row.sent_to_kitchen
								? `<span class="rp-sent"> ✓ ${__("sent")}</span> <a class="rp-cancel-item" data-i="${i}">${__("Cancel item")}</a>`
								: ""
						}
					</div>
				</div>`;
			})
			.join("");
		this.$root.find(".rp-cart").html(lines || `<div class="rp-empty">${__("No items yet")}</div>`);
		this.$root.find(".rp-sum").text(this.money(sum));
	}

	/* ---------- order type / table / delivery form ---------- */

	// تغيير نوع الطلب (يبدأ أوردر جديد بالنوع ده)
	set_type(order_type) {
		if (this.order.order_type === order_type) return;
		this.set_order(this.empty_order(order_type, null));
	}

	// اختيار ترابيزة: يفتح أوردرها المفتوح أو يبدأ أوردر جديد عليها
	select_table(name) {
		const t = this.tables.find((x) => x.name === name);
		if (t && t.current_order) {
			frappe.call({
				method: "restaurant_pos.api.get_order",
				args: { name: t.current_order },
				callback: (r) => this.set_order(this.from_doc(r.message)),
			});
		} else {
			this.set_order(this.empty_order("Dine In", name));
		}
	}

	// الرجوع لشاشة الترابيزات لاختيار ترابيزة تانية
	change_table() {
		const go = () => this.set_order(this.empty_order("Dine In", null));
		if (!this.order.name && this.order.items.length) {
			frappe.confirm(__("Discard the current unsaved items?"), go);
		} else go();
	}

	// البحث عن عميل بالتليفون وتعبئة الفورم تلقائيًا لو موجود
	lookup_customer(raw) {
		const phone = (raw || "").replace(/\D/g, "");
		if (phone.length < 8) return;
		frappe.call({
			method: "restaurant_pos.api.get_customer",
			args: { phone },
			callback: (r) => {
				const msg = this.$root.find(".rp-form-msg");
				if (!r.message) {
					msg.removeClass("err").text("");
					return;
				}
				["customer_name", "phone2", "address", "building_details", "floor", "notes"].forEach((f) => {
					this.$root.find(`.rp-f[data-f="${f}"]`).val(r.message[f] || "");
				});
				msg.removeClass("err").text(__("Returning customer: {0}", [r.message.customer_name]));
			},
		});
	}

	// التحقق من الفورم وحفظ العميل ثم الانتقال للمنيو
	submit_customer() {
		const data = {};
		this.$root.find(".rp-f").each((_, el) => {
			data[$(el).data("f")] = $(el).val() || "";
		});
		const msg = this.$root.find(".rp-form-msg");
		const phone = data.phone.replace(/\D/g, "");
		if (phone.length < 8 || !data.customer_name.trim() || !data.address.trim()) {
			msg.addClass("err").text(__("Phone, name and address are required"));
			return;
		}
		frappe.call({
			method: "restaurant_pos.api.save_customer",
			args: { data: JSON.stringify(data) },
			freeze: true,
			callback: (r) => {
				this.order.customer_info = r.message;
				this.editing_customer = false;
				this.form_values = null;
				this.group = null;
				this.render_cart();
				this.render_center();
			},
		});
	}

	// إلغاء فورم العميل والرجوع
	cancel_form() {
		if (this.order.customer_info) {
			this.editing_customer = false;
			this.render_center();
		} else {
			this.set_order(this.empty_order("Dine In", null));
		}
	}

	/* ---------- order lines ---------- */

	// تحويل أوردر جاي من السيرفر لشكل الحالة في الشاشة
	from_doc(doc) {
		return {
			name: doc.name,
			order_type: doc.order_type,
			table: doc.table,
			status: doc.status,
			customer_info: doc.customer_info || null,
			driver: doc.driver || null,
			items: (doc.items || []).map((r) => ({
				name: r.name,
				item: r.item,
				item_name: r.item_name,
				qty: r.qty,
				rate: r.rate,
				notes: r.notes,
				sent_to_kitchen: r.sent_to_kitchen,
				kitchen_status: r.kitchen_status,
			})),
		};
	}

	// إضافة صنف للسلة (أو زيادة كميته)
	add_item(code) {
		const it = this.menu.items.find((x) => x.name === code);
		if (!it) return;
		// نجمّع فقط مع الأصناف اللي لسه ما اتبعتتش للمطبخ ومفيهاش ملاحظات
		const existing = this.order.items.find((r) => r.item === code && !r.sent_to_kitchen && !r.notes);
		if (existing) existing.qty += 1;
		else
			this.order.items.push({
				item: code,
				item_name: it.item_name,
				qty: 1,
				rate: it.standard_rate,
				notes: "",
				sent_to_kitchen: 0,
				kitchen_status: "New",
			});
		this.render_cart();
	}

	// زيادة/نقص كمية صنف (الصنف المبعوت للمطبخ بيتضاف له سطر جديد)
	change_qty(i, d) {
		const row = this.order.items[i];
		if (row.kitchen_status === "Cancelled") return;
		if (row.sent_to_kitchen) {
			if (d < 0) {
				frappe.show_alert({
					message: __("Already sent to kitchen. Use Cancel item."),
					indicator: "orange",
				});
				return;
			}
			// زيادة على صنف اتبعت: نضيف سطر جديد (أو نزوّد السطر الجديد الموجود لنفس الصنف)
			const pending = this.order.items.find(
				(r) => r.item === row.item && !r.sent_to_kitchen && !r.notes
			);
			if (pending) pending.qty += 1;
			else
				this.order.items.push({
					item: row.item,
					item_name: row.item_name,
					qty: 1,
					rate: row.rate,
					notes: "",
					sent_to_kitchen: 0,
					kitchen_status: "New",
				});
			this.render_cart();
			return;
		}
		row.qty += d;
		if (row.qty <= 0) this.order.items.splice(i, 1);
		this.render_cart();
	}

	// إلغاء صنف اتبعت للمطبخ مع سبب، وتنبيه المطبخ
	cancel_sent_item(i) {
		const row = this.order.items[i];
		if (!row || !row.name) return;
		frappe.prompt(
			{
				fieldname: "reason",
				fieldtype: "Data",
				label: __("Reason (optional)"),
			},
			(v) => {
				frappe.call({
					method: "restaurant_pos.api.cancel_item",
					args: { name: this.order.name, row_name: row.name, reason: v.reason || "" },
					freeze: true,
					callback: (r) => {
						this.order = this.from_doc(r.message);
						this.render_cart();
						this.load_tables();
						frappe.show_alert({
							message: __("{0} cancelled and kitchen notified", [row.item_name]),
							indicator: "orange",
						});
					},
				});
			},
			__("Cancel {0}?", [row.item_name]),
			__("Cancel item")
		);
	}

	// إضافة/تعديل ملاحظة على صنف
	edit_note(i) {
		const row = this.order.items[i];
		frappe.prompt(
			{ fieldname: "notes", fieldtype: "Small Text", label: __("Kitchen note"), default: row.notes },
			(v) => {
				row.notes = v.notes;
				this.render_cart();
			},
			__("Note for") + " " + row.item_name
		);
	}

	// تجهيز بيانات الأوردر لإرسالها للسيرفر
	payload() {
		const c = this.order.customer_info;
		return JSON.stringify({
			name: this.order.name,
			order_type: this.order.order_type,
			table: this.order.table,
			delivery_customer: c ? c.name || c.phone : null,
			items: this.order.items.map((r) => ({ name: r.name, item: r.item, qty: r.qty, notes: r.notes })),
		});
	}

	// حفظ الأوردر على السيرفر
	save(cb) {
		if (!this.order.items.length) {
			frappe.show_alert({ message: __("Add items first"), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "restaurant_pos.api.save_order",
			args: { order: this.payload() },
			freeze: true,
			callback: (r) => {
				this.order = this.from_doc(r.message);
				this.render_cart();
				this.load_tables();
				frappe.show_alert({ message: __("Saved {0}", [this.order.name]), indicator: "green" });
				if (cb) cb();
				else if (this.order.order_type === "Delivery") this.finish_delivery(this.order.name);
			},
		});
	}

	// إرسال الأصناف الجديدة للمطبخ
	send() {
		this.save(() => {
			frappe.call({
				method: "restaurant_pos.api.send_to_kitchen",
				args: { name: this.order.name },
				freeze: true,
				callback: (r) => {
					this.order = this.from_doc(r.message);
					this.render_cart();
					this.load_tables();
					frappe.show_alert({ message: __("Sent to kitchen"), indicator: "green" });
					if (this.order.order_type === "Delivery") this.finish_delivery(this.order.name);
				},
			});
		});
	}

	// الدفع المباشر (كاش): يحفظ الأوردر، يسجّل الفاتورة على الكاشير، ويطبع الإيصال فورًا
	pay() {
		if (!this.order.items.length) {
			frappe.show_alert({ message: __("Add items first"), indicator: "orange" });
			return;
		}
		if (this.order.order_type === "Delivery") {
			frappe.show_alert({ message: __("Delivery orders are paid when settling with the driver"), indicator: "orange" });
			return;
		}
		const type = this.order.order_type; // نفس نوع الطلب يفضل بعد الدفع (تيك أواى -> أوردر تيك أواى جديد)
		this.save(() => {
			frappe.call({
				method: "restaurant_pos.billing.pay_order",
				args: { name: this.order.name, mode_of_payment: "Cash" },
				freeze: true,
				callback: (r) => {
					const inv = r.message.invoice;
					this.set_order(this.empty_order(type, null));
					this.load_tables();
					frappe.show_alert({ message: __("Paid. Invoice {0}", [inv]), indicator: "green" }, 6);
					this.print_receipt(inv);
				},
			});
		});
	}

	// طباعة إيصال الفاتورة من غير ما نفتح صفحة جديدة (iframe مخفي بيشغّل الطباعة)
	print_receipt(inv) {
		const url =
			`/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(inv)}` +
			`&format=POS%20Invoice&no_letterhead=1&trigger_print=1`;
		$("#rp-print-frame").remove();
		$('<iframe id="rp-print-frame" style="position:fixed;right:0;bottom:0;width:0;height:0;border:0"></iframe>')
			.attr("src", url)
			.appendTo("body");
	}

	// إلغاء الأوردر الحالي
	cancel() {
		if (!this.order.name) {
			this.set_order(this.empty_order(this.order.order_type, null, this.order.customer_info));
			return;
		}
		frappe.confirm(__("Cancel order {0}?", [this.order.name]), () => {
			frappe.call({
				method: "restaurant_pos.api.cancel_order",
				args: { name: this.order.name },
				callback: () => {
					const t = this.order.order_type === "Delivery" ? "Dine In" : this.order.order_type;
					this.set_order(this.empty_order(t, null));
					this.load_tables();
				},
			});
		});
	}
}