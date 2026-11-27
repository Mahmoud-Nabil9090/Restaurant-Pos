frappe.pages["admin-panel"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, title: __("Admin Panel"), single_column: true });
	wrapper.admin = new AdminPanel(wrapper);
};

frappe.pages["admin-panel"].on_page_show = function (wrapper) {
	if (wrapper.admin) wrapper.admin.refresh();
};

// صلاحيات إضافية تتدّي لكاشير (لازم تتطابق مع PERMISSIONS في api/auth.py). المفتاح : الاسم اللي يظهر
const AD_PERMS = { discount: "Can give discounts" };

class AdminPanel {
	constructor(wrapper) {
		this.page = wrapper.page;
		this.tab = "dashboard";
		this.preset = "today";
		this.users = [];
		this.menu_rows = [];
		const t = frappe.datetime.get_today();
		this.f = { from: t, to: t, status: "" };
		this.render_shell();
		this.bind_events();
	}

	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	money(v) {
		const cur = (frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "";
		return `${Number(v || 0).toFixed(2)} ${cur}`.trim();
	}

	api(method, args) {
		return frappe.xcall(`restaurant_pos.api.admin.${method}`, args || {});
	}

	tabs() {
		return [
			["dashboard", "📊", __("Dashboard")],
			["orders", "🧾", __("Orders")],
			["users", "👥", __("Users")],
			["menu", "🍔", __("Menu")],
			["manage", "⚙️", __("Management")],
		];
	}

	/* ---------- shell ---------- */

	
render_shell() {
	// Get the current logged-in user's display name.
	const name = frappe.session.user_fullname || frappe.session.user || "";
	const main = $(this.page.main);

	// Render the dashboard layout and its scoped styles.
	main.html(`

		<!-- Main application wrapper -->
		<div class="ad-app">

			<!-- Sidebar navigation -->
			<aside class="ad-side">

				<!-- Brand identity -->
				<div class="ad-brand">
					<span>🍽</span>
					<div>
						Restaurant POS
						<small>${__("ADMIN")}</small>
					</div>
				</div>

				<!-- Navigation links are rendered by render_nav() -->
				<div class="ad-nav"></div>

				<!-- Flexible spacer keeps user controls at the bottom -->
				<div class="ad-sp"></div>

				<!-- Logged-in user information -->
				<div class="ad-user">
					<div class="ad-avatar">${this.esc(name.charAt(0).toUpperCase())}</div>
					<div>
						<small>${__("Welcome")}</small>
						<b>${this.esc(name)}</b>
					</div>
				</div>

				<!-- Theme and session actions retain their existing classes -->
				<button class="ad-sidebtn ad-theme">🌓 ${__("Dark / Light")}</button>
				<button class="ad-sidebtn out ad-logout">⎋ ${__("Log out")}</button>
			</aside>

			<!-- Main dashboard area -->
			<section class="ad-main">
				<div class="ad-head"></div>
				<div class="ad-body"></div>
			</section>

		</div>
	`);

	// Keep the existing root reference used by all event handlers.
	this.$root = main;
}


	bind_events() {
		const r = this.$root;
		const today = () => frappe.datetime.get_today();

		r.on("click", ".ad-navbtn", (e) => {
			this.tab = $(e.currentTarget).attr("data-tab");
			this.refresh();
		});
		r.on("click", ".ad-preset", (e) => {
			this.set_preset($(e.currentTarget).attr("data-p"));
			this.refresh();
		});
		// ---- المنيو: إضافة / تعديل / حذف ----
		r.on("click", ".ad-add-item", () => this.item_dialog(null));
		r.on("click", ".ad-add-group", () => this.group_dialog(null));
		r.on("click", ".ad-edit-group", () => this.group_dialog(this.menu_cat));
		r.on("click", ".ad-m-edit", (e) => {
			const name = $(e.currentTarget).closest("tr").attr("data-name");
			this.item_dialog(this.menu_rows.find((x) => x.name === name));
		});
		r.on("click", ".ad-m-del", (e) => {
			const name = $(e.currentTarget).closest("tr").attr("data-name");
			frappe.confirm(__("Delete {0}? (items already sold are only hidden)", [name]), () =>
				frappe.xcall("restaurant_pos.api.menu_admin.delete_item", { name }).then((res) => {
					frappe.show_alert({ message: res === "hidden" ? __("Hidden from menu (used in orders)") : __("Deleted"), indicator: "orange" });
					this.load_menu();
				})
			);
		});
		r.on("click", ".ad-m-restore", (e) =>
			frappe.xcall("restaurant_pos.api.menu_admin.restore_item", { name: $(e.currentTarget).closest("tr").attr("data-name") }).then(() => this.load_menu())
		);
		r.on("change", ".ad-mprice, .ad-mavail", (e) => {
			const row = $(e.currentTarget).closest("tr");
			const name = row.attr("data-name");
			const rate = row.find(".ad-mprice").val();
			const avail = row.find(".ad-mavail").is(":checked") ? 1 : 0;
			frappe.xcall("restaurant_pos.api.menu_admin.quick_update", { name, standard_rate: rate, available_today: avail }).then(() => {
				const m = this.menu_rows.find((x) => x.name === name);
				if (m) {
					m.standard_rate = rate;
					m.available_today = avail;
				}
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
			});
		});
		// فلتر نوع الأوردر (All / Dine In / Takeaway / Delivery)
		r.on("click", ".ad-type", (e) => {
			this.f.type = $(e.currentTarget).attr("data-t") || "";
			this.render_orders_view();
		});
		r.on("click", ".ad-refresh", () => this.refresh());
		r.on("click", ".ad-endday", () => this.end_day());
		r.on("change", ".ad-from", (e) => {
			this.f.from = $(e.currentTarget).val() || today();
			this.preset = "";
			this.refresh();
		});
		r.on("change", ".ad-to", (e) => {
			this.f.to = $(e.currentTarget).val() || today();
			this.preset = "";
			this.refresh();
		});
		r.on("change", ".ad-status", (e) => {
			this.f.status = $(e.currentTarget).val();
			this.refresh();
		});
		r.on("click", ".ad-theme", () => window.rp && window.rp.toggle_theme());
		r.on("click", ".ad-logout", () => window.rp && window.rp.logout());

		// طباعة إيصال أوردر مدفوع (بيجيب رقم الفاتورة من الأوردر)
		r.on("click", ".ad-print", (e) => {
			const name = $(e.currentTarget).attr("data-name");
			frappe.db.get_value("Restaurant Order", name, "sales_invoice").then((res) => {
				const inv = res.message && res.message.sales_invoice;
				if (!inv) return frappe.show_alert({ message: __("No invoice for this order"), indicator: "orange" });
				window.open(`/printview?doctype=Sales%20Invoice&name=${encodeURIComponent(inv)}&format=POS%20Invoice&no_letterhead=1&trigger_print=1`);
			});
		});
		r.on("click", ".ad-detail", (e) => this.show_order($(e.currentTarget).attr("data-name")));
		r.on("click", ".ad-cancel", (e) => {
			const name = $(e.currentTarget).attr("data-name");
			frappe.prompt(
				{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
				(v) =>
					this.api("cancel_order", { name, reason: v.reason }).then(() => {
						frappe.show_alert({ message: __("{0} cancelled", [name]), indicator: "orange" });
						this.load_orders();
					}),
				__("Cancel {0}?", [name]),
				__("Cancel order")
			);
		});

		r.on("click", ".ad-u-edit", (e) => {
			const u = this.users.find((x) => x.username === $(e.currentTarget).attr("data-u"));
			if (!u) return;
			r.find(".ad-u-username").val(u.username);
			r.find(".ad-u-name").val(u.full_name);
			r.find(".ad-u-role").val(u.role);
			r.find(".ad-u-pass").val("");
				r.find(".ad-u-perm").each((_, el) => $(el).prop("checked", (u.perms || []).includes($(el).attr("data-p"))));
		});
		r.on("click", ".ad-u-save", () => {
			this.api("save_user", {
				username: r.find(".ad-u-username").val(),
				full_name: r.find(".ad-u-name").val(),
				password: r.find(".ad-u-pass").val(),
				role: r.find(".ad-u-role").val(),
					permissions: r.find(".ad-u-perm:checked").map((_, el) => $(el).attr("data-p")).get(),
			}).then(() => {
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
				this.load_users();
			});
		});
		r.on("click", ".ad-u-toggle", (e) => {
			const b = $(e.currentTarget);
			this.api("save_user", { username: b.attr("data-u"), enabled: b.attr("data-en") }).then(() => this.load_users());
		});

		r.on("click", ".ad-u-del", (e) => {
			const u = $(e.currentTarget).attr("data-u");
			frappe.confirm(__("Delete user {0}? (users with sales history are only disabled)", [u]), () =>
				this.api("delete_user", { username: u }).then((res) => {
					frappe.show_alert({ message: res === "disabled" ? __("Disabled (has sales history)") : __("Deleted"), indicator: "orange" });
					this.load_users();
				})
			);
		});

		r.on("input", ".ad-search", () => this.render_menu_table());
		r.on("change", ".ad-cat", () => this.render_menu_table());
		r.on("change", ".ad-price, .ad-avail", (e) => {
			const row = $(e.currentTarget).closest("tr");
			const name = row.attr("data-name");
			const rate = row.find(".ad-price").val();
			const avail = row.find(".ad-avail").is(":checked") ? 1 : 0;
			this.api("update_item", { name, standard_rate: rate, available_today: avail }).then(() => {
				const m = this.menu_rows.find((x) => x.name === name);
				if (m) {
					m.standard_rate = rate;
					m.available_today = avail;
				}
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
			});
		});

		r.on("click", ".ad-link", (e) => frappe.set_route(...String($(e.currentTarget).attr("data-route")).split("/")));
	}

	set_preset(p) {
		const t = frappe.datetime.get_today();
		this.preset = p;
		if (p === "today") this.f.from = this.f.to = t;
		else if (p === "yesterday") this.f.from = this.f.to = frappe.datetime.add_days(t, -1);
		else if (p === "week") {
			this.f.from = frappe.datetime.add_days(t, -6);
			this.f.to = t;
		} else if (p === "month") {
			this.f.from = frappe.datetime.add_days(t, -29);
			this.f.to = t;
		}
	}

	refresh() {
		this.render_nav();
		this.render_head();
		this["load_" + this.tab]();
	}

	render_nav() {
		this.$root.find(".ad-nav").html(
			this.tabs()
				.map(
					([k, ic, l]) =>
						`<button class="ad-navbtn ${this.tab === k ? "active" : ""}" data-tab="${k}"><span>${ic}</span>${l}</button>`
				)
				.join("")
		);
	}

	render_head() {
		const t = this.tabs().find((x) => x[0] === this.tab);
		const ranged = ["dashboard", "orders"].includes(this.tab);
		let ctl = "";
		let sub = "";
		if (ranged) {
			const chips = [
				["today", __("Today")],
				["yesterday", __("Yesterday")],
			]
				.map(
					([k, l]) =>
						`<button class="ad-chip ad-preset ${this.preset === k ? "active" : ""}" data-p="${k}">${l}</button>`
				)
				.join("");
			ctl = `${chips}
				<input type="date" class="ad-in ad-from" value="${this.esc(this.f.from)}">
				<span>→</span>
				<input type="date" class="ad-in ad-to" value="${this.esc(this.f.to)}">`;
			if (this.tab === "orders") {
				const opts = ["Open", "Sent to Kitchen", "Served", "Billed", "Cancelled"]
					.map((s) => `<option value="${s}" ${this.f.status === s ? "selected" : ""}>${__(s)}</option>`)
					.join("");
				ctl += `<select class="ad-in ad-status"><option value="">${__("All statuses")}</option>${opts}</select>`;
			}
			ctl += `<button class="ad-chip ad-refresh" title="${__("Refresh")}">↻</button>`;
			if (this.tab === "dashboard") ctl += `<button class="ad-btn primary ad-endday">🌙 ${__("End Day")}</button>`;
			const a = frappe.datetime.str_to_user(this.f.from);
			const b = frappe.datetime.str_to_user(this.f.to);
			sub = this.f.from === this.f.to ? a : `${a} → ${b}`;
		}
		if (this.tab === "dashboard") {
			const first = (frappe.session.user_fullname || "").split(" ")[0];
			sub = `${__("Welcome back")}, ${this.esc(first)} 👋 · ${sub}`;
		}
		this.$root.find(".ad-head").html(
			`<div><h2>${t[1]} ${t[2]}</h2><div class="ad-sub">${sub}</div></div><div class="ad-ctl">${ctl}</div>`
		);
	}

	body(html) {
		this.$root.find(".ad-body").html(html);
	}

	loading() {
		this.body(`<div class="ad-empty">${__("Loading...")}</div>`);
	}

	tbl(heads, rows) {
		if (!rows.length) return `<div class="ad-empty">${__("No data")}</div>`;
		return `<table class="ad-table"><thead><tr>${heads.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
			<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
	}

	hbars(rows, label, value, fmt) {
		if (!rows.length) return `<div class="ad-empty">${__("No data")}</div>`;
		const max = Math.max(...rows.map((r) => Number(r[value]) || 0), 1);
		return rows
			.map(
				(r) => `<div class="ad-hb">
					<div class="ad-hb-top"><span>${label(r)}</span><b>${fmt(r)}</b></div>
					<div class="ad-hb-track"><div class="ad-hb-fill" style="width:${(((Number(r[value]) || 0) / max) * 100).toFixed(1)}%"></div></div>
				</div>`
			)
			.join("");
	}

	vbars(rows) {
		if (!rows.length) return `<div class="ad-empty">${__("No data")}</div>`;
		const max = Math.max(...rows.map((r) => Number(r.total) || 0), 1);
		return `<div class="ad-vb">${rows
			.map(
				(r) => `<div class="ad-vb-col" title="${this.esc(r.day)} · ${this.esc(this.money(r.total))}">
					<span class="ad-vb-val">${Math.round(r.total)}</span>
					<div class="ad-vb-wrap"><div class="ad-vb-bar" style="height:${Math.max(((Number(r.total) || 0) / max) * 100, 2).toFixed(1)}%"></div></div>
					<span class="ad-vb-lbl">${this.esc(String(r.day).slice(5))}</span>
				</div>`
			)
			.join("")}</div>`;
	}

	/* ---------- end of day ---------- */

	// تقرير نهاية اليوم: يختار التاريخ، يعرض الملخص، ويقدر يطبعه أو يقفل الكاشيرز
	end_day() {
		const d = new frappe.ui.Dialog({
			title: __("End Day"),
			size: "large",
			fields: [
				{ fieldtype: "Date", fieldname: "date", label: __("Date"), default: frappe.datetime.get_today(),
					onchange: () => load() },
				{ fieldtype: "HTML", fieldname: "body" },
			],
			primary_action_label: __("Print report"),
			primary_action: () => this.print_end_day(this._eod),
			secondary_action_label: __("Close day (settle cashiers)"),
			secondary_action: () => {
				frappe.confirm(__("Settle all cashiers for this day?"), () => {
					this.api_eod(d.get_value("date"), 1).then((r) => {
						frappe.show_alert({ message: __("Day closed: {0} settlements", [r.settled_now.length]), indicator: "green" });
						this._eod = r;
						show(r);
					});
				});
			},
		});
		const show = (r) => {
			this._eod = r;
			const row = (a, b, c) => `<tr><td>${a}</td><td style="text-align:center">${b}</td><td style="text-align:end"><b>${c}</b></td></tr>`;
			const types = r.types.map((t) => row(this.esc(__(t.type)), t.orders, this.esc(this.money(t.total)))).join("");
			const modes = r.modes.map((m) => row(this.esc(m.mode), "", this.esc(this.money(m.total)))).join("");
			const cash = r.cashiers.map((c) => row(this.esc(c.user), c.orders, this.esc(this.money(c.total)) + (c.unsettled ? " ⏳" : " ✓"))).join("");
			d.fields_dict.body.$wrapper.html(`
				<table class="table table-bordered" style="margin-top:8px">
					<thead><tr><th>${__("Order type")}</th><th style="text-align:center">${__("Orders")}</th><th style="text-align:end">${__("Total")}</th></tr></thead>
					<tbody>${types}
					<tr style="background:var(--control-bg)"><td><b>${__("TOTAL")}</b></td><td style="text-align:center"><b>${r.orders}</b></td>
					<td style="text-align:end;font-size:16px"><b>${this.esc(this.money(r.total))}</b></td></tr></tbody>
				</table>
				<table class="table table-bordered"><thead><tr><th>${__("Payment")}</th><th></th><th style="text-align:end">${__("Total")}</th></tr></thead><tbody>${modes || row(__("No payments"), "", "")}</tbody></table>
				<table class="table table-bordered"><thead><tr><th>${__("Cashier")}</th><th style="text-align:center">${__("Orders")}</th><th style="text-align:end">${__("Total")} (⏳ ${__("not settled")})</th></tr></thead><tbody>${cash || row(__("No data"), "", "")}</tbody></table>
				<p>${__("Cancelled orders")}: <b>${r.cancelled}</b> (${this.esc(this.money(r.cancelled_total))}) · ${__("Still open")}: <b>${r.still_open}</b></p>`);
		};
		const load = () => this.api_eod(d.get_value("date"), 0).then(show);
		d.show();
		load();
	}

	// نداء السيرفر لتقرير نهاية اليوم (close=1 يقفل الكاشيرز)
	api_eod(date, close) {
		return frappe.xcall("restaurant_pos.api.dashboard.end_day", { date, close });
	}

	// طباعة التقرير المختصر بحجم إيصال 80mm
	print_end_day(r) {
		if (!r) return;
		const line = (a, b) => `<div style="display:flex;justify-content:space-between"><span>${this.esc(a)}</span><b>${this.esc(b)}</b></div>`;
		const html = `<html><head><meta charset="utf-8"><style>
			@page{margin:4mm} body{font-family:Arial,sans-serif;font-size:12px;width:72mm;margin:0 auto}
			h3,h4{text-align:center;margin:4px 0} hr{border:0;border-top:1px dashed #000;margin:6px 0}
		</style></head><body>
			<h3>Restaurant POS</h3><h4>${__("End of Day")} — ${this.esc(r.date)}</h4><hr>
			${r.types.map((t) => line(`${__(t.type)} (${t.orders})`, this.money(t.total))).join("")}<hr>
			<div style="font-size:15px">${line(`${__("TOTAL")} (${r.orders})`, this.money(r.total))}</div><hr>
			${r.modes.map((m) => line(m.mode, this.money(m.total))).join("")}<hr>
			${r.cashiers.map((c) => line(`${c.user} (${c.orders})`, this.money(c.total))).join("")}<hr>
			${line(__("Cancelled"), r.cancelled)}
			<p style="text-align:center">${frappe.datetime.now_datetime()}</p>
			<script>window.onload=function(){window.print();setTimeout(function(){window.close()},3000)}<\/script>
		</body></html>`;
		const w = window.open("", "_blank", "width=420,height=700");
		w.document.write(html);
		w.document.close();
	}

	// رسم المبيعات على مدار اليوم: عمود لكل ساعة (فلوس + عدد أوردرات) مع أعلى ساعة زحمة وأهدى ساعة
	hour_chart(rows) {
		if (!rows.length) return `<div class="ad-empty">${__("No data")}</div>`;
		const by = {};
		rows.forEach((r) => (by[r.hour] = r));
		const hours = rows.map((r) => Number(r.hour));
		const lo = Math.min(...hours);
		const hi = Math.max(...hours);
		const fmt = (h) => `${h % 12 || 12} ${h % 24 < 12 ? "AM" : "PM"}`;
		const cols = [];
		for (let h = lo; h <= hi; h++) cols.push({ h, orders: by[h] ? by[h].orders : 0, total: by[h] ? Number(by[h].total) : 0 });
		const max = Math.max(...cols.map((c) => c.total), 1);
		const peak = cols.reduce((a, c) => (c.total > a.total ? c : a), cols[0]);
		const slow = cols.reduce((a, c) => (c.total < a.total ? c : a), cols[0]);
		const span = (c) => `${fmt(c.h)} – ${fmt(c.h + 1)}`;
		const info = (c) => `${c.orders} ${__("orders")} · ${this.esc(this.money(c.total))}`;
		const bars = cols
			.map(
				(c) => `<div class="ad-vb-col ${c === peak ? "peak" : ""}" title="${span(c)} · ${info(c)}">
					<span class="ad-vb-val">${Math.round(c.total)}</span>
					<div class="ad-vb-wrap"><div class="ad-vb-bar" style="height:${Math.max((c.total / max) * 100, c.total ? 3 : 0).toFixed(1)}%"></div></div>
					<span class="ad-vb-lbl">${fmt(c.h)}</span>
					<span class="ad-vb-ord">${c.orders}</span>
				</div>`
			)
			.join("");
		return `<div class="ad-peak">
				<span>🔥 ${__("Busiest")}: <b>${span(peak)}</b> · ${info(peak)}</span>
				<span>🧊 ${__("Slowest")}: <b>${span(slow)}</b> · ${info(slow)}</span>
			</div>
			<div class="ad-vb" style="height:250px">${bars}</div>
			<div class="ad-sub" style="text-align:center">${__("Bars = sales per hour · number under hour = orders")}</div>`;
	}

	/* ---------- dashboard ---------- */

	load_dashboard() {
		this.loading();
		frappe.xcall("restaurant_pos.api.dashboard.report", { date_from: this.f.from, date_to: this.f.to }).then((d) => {
			if (this.tab !== "dashboard") return;
			const kpi = (ic, cls, l, v) =>
				`<div class="ad-kpi"><div class="ad-kpi-ic ${cls}">${ic}</div><div><span>${l}</span><b>${v}</b></div></div>`;
			const card = (t, b) => `<div class="ad-card"><h4>${t}</h4>${b}</div>`;
			const open = d.open_orders == null ? "–" : d.open_orders;
			this.body(`
				<div class="ad-kpis">
					${kpi("💰", "c-green", __("Total sales"), this.esc(this.money(d.sales)))}
					${kpi("🧾", "c-blue", __("Total orders"), d.orders)}
					${kpi("⛔", "c-red", __("Cancelled orders"), d.cancelled)}
				</div>
				<div class="ad-grid">
					${`<div class="ad-card" style="grid-column:1/-1"><h4>${__("Sales by hour")}</h4>${this.hour_chart(d.by_hour || [])}</div>`}
					${card(
						__("Order types"),
						this.hbars(
							d.by_type,
							(r) => this.esc(__(r.type)),
							"total",
							(r) => `${this.esc(this.money(r.total))} · ${r.orders}`
						)
					)}
					${card(
						__("Top items"),
						this.hbars(
							d.top_items,
							(r) => this.esc(r.item_name),
							"qty",
							(r) => `${r.qty} ×`
						)
					)}
					${card(
						__("Sales by user"),
						this.tbl(
							[__("User"), __("Orders"), __("Total")],
							d.by_user.map((u) => [this.esc(u.user), u.orders, `<b>${this.esc(this.money(u.total))}</b>`])
						)
					)}
				</div>`);
		});
	}

	/* ---------- orders ---------- */

	// تحميل الأوردرات حسب التاريخ والحالة (فلتر النوع بيتعمل على الشاشة)
	load_orders() {
		this.loading();
		this.api("orders", { status: this.f.status, date_from: this.f.from, date_to: this.f.to }).then((rows) => {
			if (this.tab !== "orders") return;
			this.order_rows = rows;
			this.render_orders_view();
		});
	}

	// رسم الجدول حسب نوع الأوردر المختار + أزرار الفلتر + شريط الإجماليات تحت
	render_orders_view() {
		const all = this.order_rows || [];
		const type = this.f.type || "";
		const rows = all.filter((o) => !type || o.order_type === type);
		const sum = (a) => a.reduce((t, o) => t + (Number(o.grand_total) || 0), 0);

		const types = [["", __("All")], ["Dine In", __("Dine In")], ["Takeaway", __("Takeaway")], ["Delivery", __("Delivery")]];
		const chips = types
			.map(([k, l]) => {
				const n = all.filter((o) => !k || o.order_type === k).length;
				return `<button class="ad-chip ad-type ${type === k ? "active" : ""}" data-t="${k}">${l} (${n})</button>`;
			})
			.join("");

		const data = rows.map((o) => [
			`<b>${this.esc(o.name)}</b>`,
			this.esc(__(o.order_type)) + (o.table ? " · " + this.esc(o.table) : ""),
			this.esc(o.user),
			`<span class="ad-badge b-${this.esc(String(o.status).replace(/ /g, ""))}">${this.esc(__(o.status))}</span>`,
			`<b>${this.esc(this.money(o.grand_total))}</b>`,
			this.esc(moment(o.creation).format("DD MMM HH:mm")),
			`<button class="ad-btn ad-detail" data-name="${this.esc(o.name)}">${__("Details")}</button> ` +
				(o.status === "Billed"
					? `<button class="ad-btn primary ad-print" data-name="${this.esc(o.name)}">🖨 ${__("Print")}</button> `
					: "") +
				(["Billed", "Cancelled"].includes(o.status)
					? ""
					: `<button class="ad-btn danger ad-cancel" data-name="${this.esc(o.name)}">${__("Cancel order")}</button>`),
		]);

		const paid = rows.filter((o) => o.status === "Billed");
		const unpaid = rows.filter((o) => !["Billed", "Cancelled"].includes(o.status));
		const cancelled = rows.filter((o) => o.status === "Cancelled");
		const stat = (l, v, sub) =>
			`<div style="min-width:150px"><div class="ad-sub" style="margin:0">${l}</div><b style="font-size:19px">${v}</b>${sub ? `<div class="ad-sub" style="margin:0">${sub}</div>` : ""}</div>`;

		this.body(`
			<div class="ad-form" style="margin-bottom:14px">${chips}</div>
			<div class="ad-card">${this.tbl([__("Order"), __("Type"), __("User"), __("Status"), __("Total"), __("Time"), ""], data)}</div>
			<div class="ad-card ad-sumbar" style="position:sticky;bottom:12px;z-index:5;display:flex;flex-wrap:wrap;gap:34px;align-items:flex-start;margin-bottom:0;box-shadow:0 -4px 22px rgba(0,0,0,.10)">
				${stat("🧾 " + __("Total orders"), paid.length + unpaid.length, cancelled.length ? `${cancelled.length} ${__("cancelled")}` : "")}
				${stat("💰 " + __("Revenue (paid)"), this.esc(this.money(sum(paid))), `${paid.length} ${__("orders")}`)}
				${stat(__("Not paid yet"), this.esc(this.money(sum(unpaid))), `${unpaid.length} ${__("orders")}`)}
			</div>`);
	}

	show_order(name) {
		frappe.xcall("restaurant_pos.api.orders.get_order", { name }).then((o) => {
			const items = (o.items || [])
				.map((i) => {
					const x = i.kitchen_status === "Cancelled";
					return `<tr class="${x ? "ad-x" : ""}"><td>${this.esc(i.item_name)}</td><td>${i.qty}</td>
						<td>${this.esc(this.money(i.amount))}</td><td>${this.esc(i.notes || "")}</td>
						<td>${this.esc(__(i.kitchen_status || ""))}</td></tr>`;
				})
				.join("");
			const c = o.customer_info;
			const cust = c
				? `<p><b>${this.esc(c.customer_name)}</b> · ${this.esc(c.phone)}<br>${this.esc(c.address)}</p>`
				: "";
			const d = new frappe.ui.Dialog({ title: o.name, fields: [{ fieldtype: "HTML", fieldname: "body" }] });
			d.fields_dict.body.$wrapper.html(`
				<p>${this.esc(__(o.order_type))}${o.table ? " · " + this.esc(o.table) : ""} · <b>${this.esc(__(o.status))}</b></p>
				${cust}
				<table class="table table-bordered">
					<thead><tr><th>${__("Item")}</th><th>${__("Qty")}</th><th>${__("Amount")}</th><th>${__("Notes")}</th><th>${__("Kitchen")}</th></tr></thead>
					<tbody>${items}</tbody>
				</table>
				<h4 style="text-align:end">${__("Total")}: ${this.esc(this.money(o.grand_total))}</h4>`);
			d.show();
		});
	}

	/* ---------- users ---------- */

	load_users() {
		this.loading();
		this.api("users").then((rows) => {
			if (this.tab !== "users") return;
			this.users = rows;
			const data = rows.map((u) => [
				`<b>${this.esc(u.username)}</b>`,
				this.esc(u.full_name),
				this.esc(u.role === "admin" ? __("Admin") : __("Cashier")),
					u.role === "admin"
						? `<span class="ad-sub">${__("All")}</span>`
						: (u.perms || []).map((p) => `<span class="ad-badge">${this.esc(AD_PERMS[p] ? __(AD_PERMS[p]) : p)}</span>`).join(" ") || "–",
				u.enabled ? "✓" : "✗",
				`<button class="ad-btn ad-u-edit" data-u="${this.esc(u.username)}">${__("Edit")}</button>
				 <button class="ad-btn ad-u-toggle" data-u="${this.esc(u.username)}" data-en="${u.enabled ? 0 : 1}">${u.enabled ? __("Disable") : __("Enable")}</button>
					 <button class="ad-btn danger ad-u-del" data-u="${this.esc(u.username)}">${__("Delete")}</button>`,
			]);
			this.body(`
				<div class="ad-card"><h4>${__("Add / update user")}</h4><div class="ad-form" style="margin:0">
					<input class="ad-in ad-u-username" placeholder="${__("Username")}">
					<input class="ad-in ad-u-name" placeholder="${__("Full name")}">
					<input class="ad-in ad-u-pass" type="password" placeholder="${__("Password (empty = keep)")}">
					<select class="ad-in ad-u-role"><option value="cashier">${__("Cashier")}</option><option value="admin">${__("Admin")}</option></select>
						${Object.entries(AD_PERMS)
							.map(([k, l]) => `<label class="ad-sub" style="display:flex;gap:5px;align-items:center;margin:0"><input type="checkbox" class="ad-u-perm" data-p="${k}"> ${__(l)}</label>`)
							.join("")}
					<button class="ad-btn primary ad-u-save">${__("Save")}</button>
				</div></div>
				<div class="ad-card">${this.tbl([__("Username"), __("Name"), __("Role"), __("Permissions"), __("Active"), ""], data)}</div>`);
		});
	}

	/* ---------- menu ---------- */

	// تحميل شاشة المنيو: أصناف + مجموعات + أزرار الإضافة
	load_menu() {
		this.loading();
		frappe.xcall("restaurant_pos.api.menu_admin.data").then((d) => {
			if (this.tab !== "menu") return;
			this.menu_rows = d.items;
			this.menu_groups = d.groups;
			this.menu_stations = d.stations;
			const opts = d.groups
				.map((g) => `<option value="${this.esc(g.name)}" ${g.name === this.menu_cat ? "selected" : ""}>${this.esc(g.name)}</option>`)
				.join("");
			this.body(`<div class="ad-card">
				<div class="ad-form">
					<input class="ad-in ad-search" placeholder="${__("Search item")}">
					<select class="ad-in ad-cat"><option value="">${__("All groups")}</option>${opts}</select>
					<button class="ad-btn primary ad-add-item">➕ ${__("New item")}</button>
					<button class="ad-btn ad-add-group">📁 ${__("New group")}</button>
					<button class="ad-btn ad-edit-group" style="display:none">✏️ ${__("Edit group")}</button>
				</div>
				<div class="ad-menu-table"></div>
			</div>`);
			this.render_menu_table();
		});
	}

	// رسم جدول الأصناف حسب البحث والمجموعة المختارة
	render_menu_table() {
		const q = (this.$root.find(".ad-search").val() || "").toLowerCase();
		const c = this.$root.find(".ad-cat").val() || "";
		this.menu_cat = c;
		this.$root.find(".ad-edit-group").toggle(!!c);
		const rows = this.menu_rows.filter(
			(r) => (!c || r.item_group === c) && (!q || String(r.item_name).toLowerCase().includes(q))
		);
		const html = rows.length
			? `<table class="ad-table"><thead><tr><th></th><th>${__("Group")}</th><th>${__("Item")}</th><th>${__("Price")}</th>
				<th>${__("Station")}</th><th>${__("Available today")}</th><th></th></tr></thead><tbody>${rows
					.map(
						(i) => `<tr data-name="${this.esc(i.name)}" class="${i.disabled ? "ad-x" : ""}">
						<td>${i.image ? `<img src="${this.esc(i.image)}" style="width:38px;height:38px;border-radius:8px;object-fit:cover">` : ""}</td>
						<td>${this.esc(i.item_group)}</td><td><b>${this.esc(i.item_name)}</b>${i.disabled ? ` <span class="ad-badge b-Cancelled">${__("Hidden")}</span>` : ""}</td>
						<td><input class="ad-in ad-mprice" type="number" step="0.01" min="0" style="width:100px" value="${this.esc(i.standard_rate)}"></td>
						<td>${this.esc(i.kitchen_station || "")}</td>
						<td><input type="checkbox" class="ad-mavail" ${i.available_today ? "checked" : ""}></td>
						<td><button class="ad-btn ad-m-edit">${__("Edit")}</button>
							${i.disabled
								? `<button class="ad-btn ad-m-restore">${__("Restore")}</button>`
								: `<button class="ad-btn danger ad-m-del">${__("Delete")}</button>`}</td></tr>`
					)
					.join("")}</tbody></table>`
			: `<div class="ad-empty">${__("No items")}</div>`;
		this.$root.find(".ad-menu-table").html(html);
	}

	// نافذة إضافة / تعديل صنف (الاسم، المجموعة، السعر، المحطة، وقت التحضير، التوفر، الصورة)
	item_dialog(row) {
		const groups = this.menu_groups.map((g) => g.name).join("\n");
		const stations = ["", ...this.menu_stations].join("\n");
		const d = new frappe.ui.Dialog({
			title: row ? __("Edit item") : __("New item"),
			fields: [
				{ fieldname: "item_name", fieldtype: "Data", label: __("Item name"), reqd: 1, default: row ? row.item_name : "" },
				{ fieldname: "item_group", fieldtype: "Select", label: __("Group"), options: groups, reqd: 1,
					default: row ? row.item_group : this.menu_cat || (this.menu_groups[0] || {}).name },
				{ fieldname: "standard_rate", fieldtype: "Currency", label: __("Price"), reqd: 1, default: row ? row.standard_rate : 0 },
				{ fieldname: "kitchen_station", fieldtype: "Select", label: __("Kitchen station"), options: stations, default: row ? row.kitchen_station || "" : "" },
				{ fieldname: "prep_time_min", fieldtype: "Int", label: __("Prep time (min)"), default: row ? row.prep_time_min : 10 },
				{ fieldname: "available_today", fieldtype: "Check", label: __("Available today"), default: row ? row.available_today : 1 },
				{ fieldname: "image", fieldtype: "Attach Image", label: __("Image"), default: row ? row.image : "" },
			],
			primary_action_label: __("Save"),
			primary_action: (v) =>
				frappe.xcall("restaurant_pos.api.menu_admin.save_item", { name: row ? row.name : null, data: v }).then(() => {
					d.hide();
					frappe.show_alert({ message: __("Saved"), indicator: "green" });
					this.load_menu();
				}),
		});
		d.show();
	}

	// نافذة إضافة / تعديل اسم مجموعة (تقدر تمسحها لو فاضية)
	group_dialog(old) {
		const d = new frappe.ui.Dialog({
			title: old ? __("Edit group") : __("New group"),
			fields: [
				{ fieldname: "group_name", fieldtype: "Data", label: __("Group name"), reqd: 1, default: old || "" },
				{ fieldname: "image", fieldtype: "Attach Image", label: __("Image") },
			],
			primary_action_label: __("Save"),
			primary_action: (v) =>
				frappe.xcall("restaurant_pos.api.menu_admin.save_group", { group_name: v.group_name, old: old || null, image: v.image || null }).then((n) => {
					d.hide();
					this.menu_cat = n;
					frappe.show_alert({ message: __("Saved"), indicator: "green" });
					this.load_menu();
				}),
			secondary_action_label: old ? __("Delete group") : null,
			secondary_action: old
				? () =>
						frappe.confirm(__("Delete group {0}?", [old]), () =>
							frappe.xcall("restaurant_pos.api.menu_admin.delete_group", { name: old }).then(() => {
								d.hide();
								this.menu_cat = "";
								this.load_menu();
							})
						)
				: null,
		});
		d.show();
	}

	/* ---------- management ---------- */

	load_manage() {
		const links = [
			["delivery-orders", "🛵", __("Delivery Orders")],
			["cashier", "🧾", __("Open Cashier")],
			["List/Delivery Driver", "🏍", __("Delivery Drivers")],
			["List/Restaurant Table", "🪑", __("Tables")],
			["List/Kitchen Station", "🔥", __("Kitchen Stations")],
			["List/Restaurant Customer", "📇", __("Customers")],
			["List/Restaurant Order", "📋", __("All Orders (system list)")],
			["List/Item", "📦", __("Items")],
			["List/User", "🔑", __("System Users")],
			["List/Sales Invoice", "🧾", __("Invoices")],
			["List/Cashier Settlement", "💵", __("Cashier Settlements")],
			["query-report/Sales Register", "📑", __("Sales Register (report)")],
			["query-report/General Ledger", "📒", __("General Ledger (report)")],
			["query-report/Item-wise Sales Register", "📊", __("Item-wise Sales (report)")],
		]
			.map(
				([r, ic, l]) =>
					`<button class="ad-link" data-route="${this.esc(r)}"><i>${ic}</i><span>${l}</span></button>`
			)
			.join("");
		this.body(`<div class="ad-links">${links}</div>`);
	}
}