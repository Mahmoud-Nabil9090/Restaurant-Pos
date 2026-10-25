
(function () {
	const roles = () => (frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];

	function who() {
		const real = frappe.session.user !== "Administrator";
		const is_admin = real && roles().includes("Restaurant Admin");
		const cashier = real && !is_admin && roles().includes("Restaurant Cashier");
		return { is_admin, cashier, kiosk: is_admin || cashier };
	}

	const full_name = () => frappe.session.user_fullname || frappe.session.user || "";

	function toggle_theme() {
		const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
		document.documentElement.setAttribute("data-theme-mode", next);
		document.documentElement.setAttribute("data-theme", next);
		try { localStorage.setItem("rp_theme", next); } catch (e) {}
		frappe
			.xcall("frappe.core.doctype.user.user.switch_theme", { theme: next === "dark" ? "Dark" : "Light" })
			.catch(() => {});
	}

	function logout() {
		frappe.confirm(__("Log out?"), () => {
			frappe.call({ method: "logout" }).always(() => (window.location.href = "/login"));
		});
	}

	// أول تحميل: أدمن -> لوحة الإدارة، كاشير -> الكاشير
	function land() {
		const w = who();
		if (!w.kiosk) return;
		const first = frappe.get_route()[0] || "";
		const bounce = !first || first === "Workspaces" || (w.is_admin && first === "cashier");
		if (bounce) frappe.set_route(w.is_admin ? "admin-panel" : "cashier");
	}

	// الكاشير ما يخرجش للـ Workspaces
	function guard() {
		if (!who().cashier) return;
		const first = frappe.get_route()[0] || "";
		if (!first || first === "Workspaces") frappe.set_route("cashier");
	}

	function topbar() {
		const w = who();
		const route = frappe.get_route()[0];
		if (!w.kiosk || route === "admin-panel") {
			$(".rp-top").remove();
			return;
		}
		let top = $(".rp-top");
		if (!top.length) {
			const nav = $("header.navbar").first();
			if (!nav.length) return;
			const c = nav.find(".container").first();
			const host = c.length ? c : nav;
			const name = frappe.utils.escape_html(full_name());
			top = $(`
				<div class="rp-top">
					<span class="rp-top-brand">🍽 Restaurant POS</span>
					<span class="rp-top-welcome">${__("Welcome")}, <b>${name}</b></span>
					<span class="rp-top-sp"></span>
					<button class="rp-top-btn rp-top-dash">📊 ${__("Dashboard")}</button>
					<button class="rp-top-btn rp-top-theme" title="${__("Dark / Light")}">🌓</button>
					<button class="rp-top-btn rp-top-out">⎋ ${__("Log out")}</button>
				</div>`).appendTo(host);
		}
		top.find(".rp-top-dash").toggle(w.is_admin);
	}

	$(document)
		.off(".rp")
		.on("click.rp", ".rp-top-theme", toggle_theme)
		.on("click.rp", ".rp-top-out", logout)
		.on("click.rp", ".rp-top-dash", () => frappe.set_route("admin-panel"));

	window.rp = { toggle_theme, logout, full_name };

	$(document).on("app_ready", () => {
		try {
			localStorage.setItem(
				"rp_theme",
				document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light"
			);
		} catch (e) {}
		const apply = () => {
			$("body").toggleClass("rp-kiosk", who().kiosk);
			topbar();
		};
		apply();
		setTimeout(land, 300);
		setTimeout(land, 1200);
		frappe.router.on("change", () => {
			apply();
			guard();
		});
	});
})();
