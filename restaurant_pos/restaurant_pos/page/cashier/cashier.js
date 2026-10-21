frappe.pages["cashier"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Restaurant Cashier"),
		single_column: true,
	});
	wrapper.cashier = new RestaurantCashier(wrapper);
};

frappe.pages["cashier"].refresh = function (wrapper) {
	if (wrapper.cashier) wrapper.cashier.load_tables();
};

class RestaurantCashier {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.menu = { groups: [], items: [] };
		this.tables = [];
		this.group = null;
		this.order = this.empty_order();
		this.render_shell();
		this.bind_events();
		this.load_menu();
		this.load_tables();
		this.render_cart();
		this.page.set_primary_action(__("New Takeaway"), () => this.new_order("Takeaway"));
		this.page.add_inner_button(__("Delivery"), () => this.new_order("Delivery"));
		frappe.realtime.on("kitchen_new_ticket", () => this.load_tables());
	}

	empty_order(order_type = "Dine In", table = null) {
		return { name: null, order_type, table, items: [], status: "Open" };
	}

	esc(v) {
		return frappe.utils.escape_html(v == null ? "" : String(v));
	}

	render_shell() {
		const main = $(this.page.main);
		main.html(`
			<style>
				.rp { display: grid; grid-template-columns: 220px 1fr 340px; gap: 12px; min-height: 70vh; }
				.rp-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; overflow: auto; max-height: 78vh; }
				.rp-title { font-weight: 600; margin-bottom: 8px; }
				.rp-table { display: block; width: 100%; text-align: start; padding: 8px 10px; margin-bottom: 6px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--control-bg); cursor: pointer; }
				.rp-table.occupied { background: #fde8e8; border-color: #f5a3a3; }
				.rp-table.reserved { background: #fff4d6; border-color: #f0cf7a; }
				.rp-table.active { outline: 2px solid var(--primary); }
				.rp-table small { display: block; color: var(--text-muted); }
				.rp-tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
				.rp-tab { padding: 4px 12px; border-radius: 16px; border: 1px solid var(--border-color); cursor: pointer; background: var(--control-bg); }
				.rp-tab.active { background: var(--primary); color: #fff; border-color: var(--primary); }
				.rp-items { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
				.rp-item { padding: 12px 8px; border: 1px solid var(--border-color); border-radius: 10px; text-align: center; cursor: pointer; background: var(--control-bg); }
				.rp-item:hover { border-color: var(--primary); }
				.rp-item b { display: block; margin-bottom: 4px; }
				.rp-line { border-bottom: 1px dashed var(--border-color); padding: 6px 0; }
				.rp-line .row-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
				.rp-qty button { width: 24px; height: 24px; line-height: 1; border-radius: 50%; border: 1px solid var(--border-color); background: var(--control-bg); cursor: pointer; }
				.rp-sent { color: var(--green-600); font-size: 11px; }
				.rp-total { font-size: 18px; font-weight: 700; margin: 10px 0; display: flex; justify-content: space-between; }
				.rp-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
				.rp-actions .full { grid-column: 1 / -1; }
				@media (max-width: 992px) { .rp { grid-template-columns: 1fr; } }
			</style>
			<div class="rp">
				<div class="rp-panel"><div class="rp-title">${__("Tables")}</div><div class="rp-tables"></div></div>
				<div class="rp-panel"><div class="rp-tabs"></div><div class="rp-items"></div></div>
				<div class="rp-panel">
					<div class="rp-title rp-head"></div>
					<div class="rp-cart"></div>
					<div class="rp-total"><span>${__("Total")}</span><span class="rp-sum">0.00</span></div>
					<div class="rp-actions">
						<button class="btn btn-default btn-sm rp-save">${__("Save")}</button>
						<button class="btn btn-primary btn-sm rp-send">${__("Send to Kitchen")}</button>
						<button class="btn btn-danger btn-sm rp-cancel full">${__("Cancel Order")}</button>
					</div>
				</div>
			</div>
		`);
		this.$root = main;
	}

	bind_events() {
		const r = this.$root;
		r.on("click", ".rp-table", (e) => this.select_table($(e.currentTarget).data("table")));
		r.on("click", ".rp-tab", (e) => {
			this.group = $(e.currentTarget).data("group");
			this.render_menu();
		});
		r.on("click", ".rp-item", (e) => this.add_item($(e.currentTarget).data("item")));
		r.on("click", ".rp-plus", (e) => this.change_qty($(e.currentTarget).data("i"), 1));
		r.on("click", ".rp-minus", (e) => this.change_qty($(e.currentTarget).data("i"), -1));
		r.on("click", ".rp-note", (e) => this.edit_note($(e.currentTarget).data("i")));
		r.on("click", ".rp-save", () => this.save());
		r.on("click", ".rp-send", () => this.send());
		r.on("click", ".rp-cancel", () => this.cancel());
	}

	load_menu() {
		frappe.call({
			method: "restaurant_pos.api.get_menu",
			callback: (r) => {
				this.menu = r.message;
				this.group = this.group || this.menu.groups[0] || null;
				this.render_menu();
			},
		});
	}

	load_tables() {
		frappe.call({
			method: "restaurant_pos.api.get_tables",
			callback: (r) => {
				this.tables = r.message || [];
				this.render_tables();
			},
		});
	}

	render_tables() {
		const html = this.tables
			.map((t) => {
				const cls = t.status === "Occupied" ? "occupied" : t.status === "Reserved" ? "reserved" : "";
				const active = this.order.table === t.name ? "active" : "";
				return `<button class="rp-table ${cls} ${active}" data-table="${this.esc(t.name)}">
					<b>${this.esc(t.table_name)}</b>
					<small>${this.esc(t.area)} · ${this.esc(t.capacity)} ${__("seats")} · ${this.esc(t.status)}</small>
				</button>`;
			})
			.join("");
		this.$root.find(".rp-tables").html(html);
	}

	render_menu() {
		const tabs = this.menu.groups
			.map(
				(g) =>
					`<span class="rp-tab ${g === this.group ? "active" : ""}" data-group="${this.esc(g)}">${this.esc(g)}</span>`
			)
			.join("");
		this.$root.find(".rp-tabs").html(tabs);

		const items = this.menu.items
			.filter((i) => i.item_group === this.group)
			.map(
				(i) => `<div class="rp-item" data-item="${this.esc(i.name)}">
					<b>${this.esc(i.item_name)}</b>
					<span>${format_currency(i.standard_rate)}</span>
				</div>`
			)
			.join("");
		this.$root.find(".rp-items").html(items);
	}

	render_cart() {
		const o = this.order;
		const head = o.name
			? `${this.esc(o.name)} · ${this.esc(o.table || o.order_type)} · ${this.esc(o.status)}`
			: o.table
			? `${__("New order")} · ${this.esc(o.table)}`
			: `${__("New")} ${this.esc(o.order_type)}`;
		this.$root.find(".rp-head").html(head);

		let sum = 0;
		const lines = o.items
			.map((row, i) => {
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
						<span>${format_currency(amount)}</span>
					</div>
					<div>
						<a class="rp-note text-muted small" data-i="${i}">${row.notes ? "📝 " + this.esc(row.notes) : __("Add note")}</a>
						${row.sent_to_kitchen ? `<span class="rp-sent"> ✓ ${__("sent")}</span>` : ""}
					</div>
				</div>`;
			})
			.join("");
		this.$root.find(".rp-cart").html(lines || `<div class="text-muted">${__("No items yet")}</div>`);
		this.$root.find(".rp-sum").text(format_currency(sum));
		this.render_tables();
	}

	new_order(order_type) {
		this.order = this.empty_order(order_type, null);
		this.render_cart();
	}

	select_table(name) {
		const t = this.tables.find((x) => x.name === name);
		if (t && t.current_order) {
			frappe.call({
				method: "restaurant_pos.api.get_order",
				args: { name: t.current_order },
				callback: (r) => {
					this.order = this.from_doc(r.message);
					this.render_cart();
				},
			});
		} else {
			this.order = this.empty_order("Dine In", name);
			this.render_cart();
		}
	}

	from_doc(doc) {
		return {
			name: doc.name,
			order_type: doc.order_type,
			table: doc.table,
			status: doc.status,
			items: (doc.items || []).map((r) => ({
				name: r.name,
				item: r.item,
				item_name: r.item_name,
				qty: r.qty,
				rate: r.rate,
				notes: r.notes,
				sent_to_kitchen: r.sent_to_kitchen,
			})),
		};
	}

	add_item(code) {
		const it = this.menu.items.find((x) => x.name === code);
		if (!it) return;
		if (this.order.order_type === "Dine In" && !this.order.table) {
			frappe.show_alert({ message: __("Select a table first"), indicator: "orange" });
			return;
		}
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
			});
		this.render_cart();
	}

	change_qty(i, d) {
		const row = this.order.items[i];
		if (row.sent_to_kitchen && d < 0) {
			frappe.show_alert({ message: __("Already sent to kitchen"), indicator: "orange" });
			return;
		}
		row.qty += d;
		if (row.qty <= 0) this.order.items.splice(i, 1);
		this.render_cart();
	}

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

	payload() {
		return JSON.stringify({
			name: this.order.name,
			order_type: this.order.order_type,
			table: this.order.table,
			items: this.order.items.map((r) => ({ name: r.name, item: r.item, qty: r.qty, notes: r.notes })),
		});
	}

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
			},
		});
	}

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
				},
			});
		});
	}

	cancel() {
		if (!this.order.name) {
			this.order = this.empty_order();
			this.render_cart();
			return;
		}
		frappe.confirm(__("Cancel order {0}?", [this.order.name]), () => {
			frappe.call({
				method: "restaurant_pos.api.cancel_order",
				args: { name: this.order.name },
				callback: () => {
					this.order = this.empty_order();
					this.render_cart();
					this.load_tables();
				},
			});
		});
	}
}