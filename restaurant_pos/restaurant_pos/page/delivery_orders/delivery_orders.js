frappe.pages["delivery-orders"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Delivery Orders"),
		single_column: true,
	});
	wrapper.board = new DeliveryBoard(wrapper);
};

frappe.pages["delivery-orders"].on_page_show = function (wrapper) {
	if (wrapper.board) wrapper.board.refresh();
};

class DeliveryBoard {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.tab = "orders";
		this.view = "active";
		this.orders = [];
		this.drivers = [];
		this.summary = [];
		this.selected_driver = null;
		this.date = frappe.datetime.get_today();
		this.render_shell();
		this.bind_events();
		frappe.realtime.on("rp_orders_changed", () => this.on_remote_change());
		this.page.set_primary_action(__("New Delivery Order"), () => frappe.set_route("cashier"));
		if (frappe.user.has_role("Restaurant Admin"))
		this.page.add_inner_button(__("New Driver"), () => frappe.new_doc("Delivery Driver"));
		// فلتر اليوم فوق جنب عنوان الصفحة: بيحدد أوردرات Delivered وحساب السواقين
		this.day_input = $(`<input type="date" class="dv-day" value="${this.date}" title="${__("Day")}"
			style="margin-inline-start:14px;height:32px;border-radius:8px;border:1px solid var(--border-color,#d1d5db);padding:0 8px;background:var(--control-bg,#fff);color:inherit">`)
			.appendTo(this.page.$title_area || $(this.page.wrapper).find(".title-area"))
			.on("change", (e) => {
				this.date = $(e.currentTarget).val() || frappe.datetime.get_today();
				this.selected_driver = null;
				this.refresh();
			});
	}

	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	money(v) {
		const cur = (frappe.boot.sysdefaults && frappe.boot.sysdefaults.currency) || "";
		return `${Number(v || 0).toFixed(2)} ${cur}`.trim();
	}

	render_shell() {
		const main = $(this.page.main);
		main.html(`
			<style>
				body[data-route="delivery-orders"],
				body[data-route="delivery-orders"] .page-container,
				#page-delivery-orders { background: #f3f4f7 !important; }
				body[data-route="delivery-orders"] .container { max-width: 100%; }
				#page-delivery-orders .page-head { background: #ffffff; border-bottom: 1px solid #e5e7eb; }
				#page-delivery-orders .layout-main-section { background: transparent; border: 0; box-shadow: none; padding: 0; }

				.dv { color: #1f2937; padding-top: 14px; min-height: calc(100vh - 160px); }
				.dv button, .dv select, .dv input { font-family: inherit; }
				.dv-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px; }
				.dv-tab, .dv-chip { height: 40px; padding: 0 18px; border-radius: 20px; font-weight: 600; font-size: 14px; cursor: pointer; border: 1px solid #e5e7eb; background: #ffffff; color: #374151; }
				.dv-tab.active, .dv-chip.active { background: #f97316; border-color: #f97316; color: #ffffff; }
				.dv-sep { width: 1px; height: 28px; background: #d9dce3; margin: 0 6px; }
				.dv-date { height: 40px; border-radius: 10px; border: 1px solid #d1d5db; background: #ffffff; color: #1f2937; padding: 0 10px; }
				.dv-btn { height: 34px; padding: 0 14px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; border: 1px solid #d1d5db; background: #ffffff; color: #374151; }
				.dv-btn.primary { background: #f97316; border-color: #f97316; color: #ffffff; }
				.dv-btn.ok { background: #16a34a; border-color: #16a34a; color: #ffffff; }
				.dv-btn.danger { color: #dc2626; background: transparent; }
				.dv-btn:disabled { opacity: .45; cursor: not-allowed; }
				.dv-muted { color: #6b7280; font-size: 12px; }
				.dv-badge { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 12px; background: #f3f4f6; color: #374151; white-space: nowrap; }
				.dv-badge.pending { background: #fef3c7; color: #b45309; }
				.dv-badge.out { background: #dbeafe; color: #1d4ed8; }
				.dv-badge.done { background: #dcfce7; color: #15803d; }
				.dv-driver { height: 34px; border-radius: 10px; border: 1px solid #d1d5db; background: #ffffff; color: #1f2937; padding: 0 8px; }
				.dv-empty { color: #6b7280; padding: 30px 4px; }

				.dv-list { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 6px 14px 10px; overflow-x: auto; box-shadow: 0 1px 3px rgba(16, 24, 40, .06); }
				.dv-list .dv-table td { padding: 12px 8px; }
				.dv-list .dv-table tbody tr:hover { background: #f9fafb; }
				.dv-addr { max-width: 260px; }
				.dv-acts { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
				.dv-acts .dv-driver { flex: none; min-width: 130px; }

				.dv-drivers { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; margin-bottom: 18px; }
				.dv-drv { background: #ffffff; border: 2px solid #e5e7eb; border-radius: 14px; padding: 14px; cursor: pointer; text-align: start; color: #1f2937; display: flex; flex-direction: column; gap: 6px; box-shadow: 0 1px 2px rgba(16, 24, 40, .05); }
				.dv-drv.active { border-color: #f97316; }
				.dv-drv b { font-size: 17px; }
				.dv-money { font-size: 22px; font-weight: 800; color: #ea580c; }
				.dv-panel { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 16px; box-shadow: 0 1px 3px rgba(16, 24, 40, .06); }
				.dv-table { width: 100%; border-collapse: collapse; font-size: 13px; }
				.dv-table th { text-align: start; color: #6b7280; font-weight: 600; padding: 8px 6px; border-bottom: 1px solid #e5e7eb; }
				.dv-table td { padding: 9px 6px; border-bottom: 1px dashed #e5e7eb; vertical-align: top; }
				.dv-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; gap: 10px; flex-wrap: wrap; }
			</style>
			<div class="dv">
				<div class="dv-bar dv-tabs"></div>
				<div class="dv-body"></div>
			</div>
		`);
		this.$root = main;
	}

	bind_events() {
		const r = this.$root;
		r.on("click", ".dv-tab", (e) => {
			this.tab = $(e.currentTarget).data("tab");
			this.refresh();
		});
		r.on("click", ".dv-chip", (e) => {
			this.view = $(e.currentTarget).data("view");
			this.refresh();
		});
		r.on("click", ".dv-print", (e) => this.print_receipt($(e.currentTarget).data("name")));
		r.on("click", ".dv-edit", (e) => {
			frappe.route_options = { order: $(e.currentTarget).data("name") };
			frappe.set_route("cashier");
		});
		r.on("click", ".dv-assign", (e) => {
			const name = $(e.currentTarget).data("name");
			const driver = $(e.currentTarget).closest("tr").find(".dv-driver").val();
			if (!driver) {
				frappe.show_alert({ message: __("Select a driver first"), indicator: "orange" });
				return;
			}
			this.call("assign_driver", { name, driver }, __("Assigned to {0}", [driver]));
		});
		r.on("click", ".dv-unassign", (e) => {
			this.call("unassign_driver", { name: $(e.currentTarget).data("name") }, __("Driver removed"));
		});
		r.on("click", ".dv-deliver", (e) => {
			const name = $(e.currentTarget).data("name");
			frappe.confirm(__("Mark {0} as delivered?", [name]), () =>
				this.call("mark_delivered", { name }, __("Delivered"))
			);
		});
		r.on("change", ".dv-date", (e) => {
			this.date = $(e.currentTarget).val() || frappe.datetime.get_today();
			this.selected_driver = null;
			this.load_summary();
		});
		r.on("click", ".dv-drv", (e) => {
			this.selected_driver = $(e.currentTarget).data("driver");
			this.render_drivers();
		});
		r.on("click", ".dv-settle", (e) => {
			const driver = $(e.currentTarget).data("driver");
			frappe.confirm(__("Settle {0} for {1}?", [driver, this.date]), () => {
				frappe.call({
					method: "restaurant_pos.api.delivery.settle_driver",
					args: { driver, date: this.date },
					freeze: true,
					callback: (res) => {
						this.summary = res.message || [];
						this.render_drivers();
						frappe.show_alert({ message: __("Account settled"), indicator: "green" });
					},
				});
			});
		});
	}

	call(method, args, done_msg) {
		frappe.call({
			method: `restaurant_pos.api.delivery.${method}`,
			args,
			freeze: true,
			callback: () => {
				frappe.show_alert({ message: done_msg, indicator: "green" });
				this.refresh();
			},
		});
	}

	// أى جهاز غيّر أوردر: نحدّث الشاشة (لو هى الظاهرة، ومن غير ما نبوّظ اختيار سواق لسه ما اتأكدش)
	on_remote_change() {
		if (!$(this.wrapper).is(":visible")) return;
		if (this.$root.find(".dv-driver").filter((_, el) => $(el).val()).length) return;
		clearTimeout(this._rt);
		this._rt = setTimeout(() => this.refresh(), 400);
	}

	// يطبع إيصال الأوردر على طول (iframe مخفي)
	print_receipt(name) {
		frappe.call({
			method: "restaurant_pos.api.receipt.render_html",
			args: { name, autoprint: 1 },
			callback: (r) => {
				$("#rp-print-frame").remove();
				$('<iframe id="rp-print-frame" style="position:fixed;right:0;bottom:0;width:0;height:0;border:0"></iframe>')
					.attr("srcdoc", r.message)
					.appendTo("body");
			},
		});
	}

	refresh() {
		this.render_tabs();
		frappe.call({
			method: "restaurant_pos.api.delivery.get_drivers",
			callback: (r) => {
				this.drivers = r.message || [];
				if (this.tab === "orders") this.load_orders();
				else this.load_summary();
			},
		});
	}

	render_tabs() {
		const tabs = [
			["orders", __("Orders")],
			["drivers", __("Drivers")],
		]
			.map(
				([k, label]) =>
					`<button class="dv-tab ${this.tab === k ? "active" : ""}" data-tab="${k}">${label}</button>`
			)
			.join("");

		let extra = "";
		if (this.tab === "orders") {
			const chips = [
				["active", __("Active")],
				["pending", __("Waiting for driver")],
				["out", __("Out for delivery")],
				["delivered", __("Delivered")],
			]
				.map(
					([k, label]) =>
						`<button class="dv-chip ${this.view === k ? "active" : ""}" data-view="${k}">${label}</button>`
				)
				.join("");
			extra = `<span class="dv-sep"></span>${chips}`;
		} else {
			extra = "";
		}
		this.$root.find(".dv-tabs").html(tabs + extra);
	}

	load_orders() {
		frappe.call({
			method: "restaurant_pos.api.delivery.get_delivery_orders",
			args: { view: this.view, date: this.date },
			callback: (r) => {
				this.orders = r.message || [];
				this.render_orders();
			},
		});
	}

	load_summary() {
		frappe.call({
			method: "restaurant_pos.api.delivery.driver_summary",
			args: { date: this.date },
			callback: (r) => {
				this.summary = r.message || [];
				this.render_drivers();
			},
		});
	}

	badge(status) {
		const cls = status === "Delivered" ? "done" : status === "Out for Delivery" ? "out" : "pending";
		return `<span class="dv-badge ${cls}">${this.esc(__(status))}</span>`;
	}

	render_orders() {
		if (!this.orders.length) {
			this.$root.find(".dv-body").html(`<div class="dv-empty">${__("No delivery orders here")}</div>`);
			return;
		}
		const options = this.drivers
			.map((d) => `<option value="${this.esc(d.name)}">${this.esc(d.driver_name)}</option>`)
			.join("");

		const rows = this.orders
			.map((o) => {
				const c = o.customer;
				const customer = c
					? `<b>${this.esc(c.customer_name)}</b><br><span class="dv-muted">${this.esc(c.phone)}${c.phone2 ? " / " + this.esc(c.phone2) : ""}</span>`
					: `<span class="dv-muted">${__("No customer data")}</span>`;
				const place = c
					? [c.address, c.building_details, c.floor ? `${__("Floor")} ${c.floor}` : ""].filter(Boolean).join(" · ")
					: "";
				const address = c
					? `${this.esc(place)}${c.notes ? "<br><span class='dv-muted'>📝 " + this.esc(c.notes) + "</span>" : ""}`
					: "";
				const items = o.items
					.filter((i) => i.kitchen_status !== "Cancelled")
					.map((i) => `${i.qty}× ${this.esc(i.item_name)}`)
					.join("<br>");

				let actions = "";
				if (o.delivery_status === "Pending") {
					actions = `<div class="dv-acts">
						<select class="dv-driver"><option value="">${__("Select driver")}</option>${options}</select>
						<button class="dv-btn primary dv-assign" data-name="${this.esc(o.name)}">${__("Assign")}</button>
						<button class="dv-btn dv-edit" data-name="${this.esc(o.name)}">${__("Edit")}</button>
					</div>`;
				} else if (o.delivery_status === "Out for Delivery") {
					actions = `<div class="dv-acts">
						<span class="dv-muted">🛵 ${this.esc(o.driver)}</span>
						<button class="dv-btn ok dv-deliver" data-name="${this.esc(o.name)}">${__("Delivered")}</button>
						<button class="dv-btn dv-edit" data-name="${this.esc(o.name)}">${__("Edit")}</button>
						<button class="dv-btn danger dv-unassign" data-name="${this.esc(o.name)}">${__("Unassign")}</button>
					</div>`;
				} else {
					actions = `<span class="dv-muted">🛵 ${this.esc(o.driver)}<br>${this.esc(moment(o.delivered_on).format("DD MMM HH:mm"))}</span>`;
				}

				return `<tr>
					<td><b>${this.esc(o.name)}</b><br><span class="dv-muted">${this.esc(moment(o.creation).format("DD MMM HH:mm"))}</span><br><button class="dv-btn dv-print" data-name="${this.esc(o.name)}" title="${__("Print")}">🖨</button></td>
					<td>${customer}</td>
					<td class="dv-addr">${address}</td>
					<td>${items}</td>
					<td><b>${this.esc(this.money(o.grand_total))}</b></td>
					<td>${this.badge(o.delivery_status)}</td>
					<td>${actions}</td>
				</tr>`;
			})
			.join("");

		this.$root.find(".dv-body").html(`<div class="dv-list">
			<table class="dv-table">
				<thead><tr>
					<th>${__("Order")}</th><th>${__("Customer")}</th><th>${__("Address")}</th>
					<th>${__("Items")}</th><th>${__("Total")}</th><th>${__("Status")}</th><th></th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>
		</div>`);
	}

	render_drivers() {
		if (!this.summary.length) {
			this.$root
				.find(".dv-body")
				.html(`<div class="dv-empty">${__("No orders were assigned to drivers on this day")}</div>`);
			return;
		}
		if (!this.selected_driver || !this.summary.find((d) => d.driver === this.selected_driver)) {
			this.selected_driver = this.summary[0].driver;
		}

		const cards = this.summary
			.map(
				(d) => `<button class="dv-drv ${d.driver === this.selected_driver ? "active" : ""}" data-driver="${this.esc(d.driver)}">
					<b>🛵 ${this.esc(d.driver_name)}</b>
					<span class="dv-muted">${this.esc(d.phone)}</span>
					<span class="dv-muted">${d.total_orders} ${__("orders")} · ${d.delivered_count} ${__("delivered")} · ${d.pending_count} ${__("out")}</span>
					<span class="dv-money">${this.esc(this.money(d.delivered_total))}</span>
				</button>`
			)
			.join("");

		const d = this.summary.find((x) => x.driver === this.selected_driver);
		const rows = d.orders
			.map((o) => {
				const c = o.customer;
				return `<tr>
					<td>${this.esc(o.name)}</td>
					<td>${c ? this.esc(c.customer_name) + "<br><span class='dv-muted'>" + this.esc(c.address) + "</span>" : ""}</td>
					<td>${this.badge(o.delivery_status)}</td>
					<td>${this.esc(this.money(o.grand_total))}</td>
					<td>${o.driver_settled ? "✓" : ""}</td>
				</tr>`;
			})
			.join("");

		const can_settle = d.pending_count === 0 && d.to_settle > 0;
		const detail = `<div class="dv-panel">
			<table class="dv-table">
				<thead><tr><th>${__("Order")}</th><th>${__("Customer")}</th><th>${__("Status")}</th><th>${__("Total")}</th><th>${__("Settled")}</th></tr></thead>
				<tbody>${rows}</tbody>
			</table>
			<div class="dv-foot">
				<div>
					<div class="dv-muted">${__("To collect from")} ${this.esc(d.driver_name)}</div>
					<div class="dv-money">${this.esc(this.money(d.to_settle))}</div>
					${d.pending_count ? `<div class="dv-muted">${d.pending_count} ${__("order(s) still out for delivery")}</div>` : ""}
				</div>
				<button class="dv-btn ok dv-settle" data-driver="${this.esc(d.driver)}" ${can_settle ? "" : "disabled"}>${__("Settle account")}</button>
			</div>
		</div>`;

		this.$root.find(".dv-body").html(`<div class="dv-drivers">${cards}</div>${detail}`);
	}
}