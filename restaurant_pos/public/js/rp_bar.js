/* شريط علوي خاص بالمطعم: بيغطي شريط فرابي في صفحات الكاشير والدليفري (ويخفيه في لوحة الأدمن).
   شمال: لوجو + اسم المطعم | نص: روابط سريعة | يمين: Welcome + اسم اليوزر + ثيم + تسجيل خروج.

   للتعديل:  RP_BRAND = اسم المطعم ،  RP_LOGO_URL = رابط صورة اللوجو (فاضي = أيقونة افتراضية).
   التركيب:  hooks.py ->  app_include_js = ["/assets/restaurant_pos/js/rp_app.js", "/assets/restaurant_pos/js/rp_bar.js"]
*/
(function () {
	const RP_BRAND = "Burger House"; // اسم المطعم
	const RP_LOGO_URL = "/assets/restaurant_pos/images/logo.jpg"; // مثال: "/assets/restaurant_pos/images/logo.png"
	const BAR_ROUTES = ["cashier", "delivery-orders"]; // الصفحات اللي فيها الشريط
	const HIDE_ONLY_ROUTES = ["admin-panel"]; // الصفحات اللي بنخفي فيها شريط فرابي بس (عندها قايمتها)

	const css = `
	body.rp-has-bar .navbar { visibility: hidden; }
	body.rp-hide-navbar .navbar { display: none !important; }
	#rp-bar { --b-bg:#ffffff; --b-text:#1f2937; --b-muted:#6b7280; --b-line:#e5e7eb; --b-chip:#f3f4f6;
		display: none; position: fixed; top: 0; inset-inline: 0; height: var(--navbar-height, 48px); z-index: 1100;
		background: var(--b-bg); border-bottom: 1px solid var(--b-line); color: var(--b-text);
		align-items: center; justify-content: space-between; padding: 0 16px; gap: 12px; font-family: inherit; }
	html[data-theme="dark"] #rp-bar { --b-bg:#171b25; --b-text:#edf0f7; --b-muted:#9ba3b5; --b-line:#2b3140; --b-chip:#232938; }
	body.rp-has-bar #rp-bar { display: flex; }
	#rp-bar .rb-brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 16px; letter-spacing: -.3px; white-space: nowrap; }
	#rp-bar .rb-logo { width: 30px; height: 30px; border-radius: 9px; background: linear-gradient(135deg,#fb923c,#ea580c);
		display: flex; align-items: center; justify-content: center; font-size: 17px; overflow: hidden; }
	#rp-bar .rb-logo img { width: 100%; height: 100%; object-fit: cover; }
	#rp-bar .rb-nav { display: flex; gap: 6px; }
	#rp-bar button { font-family: inherit; cursor: pointer; }
	#rp-bar .rb-link { height: 30px; padding: 0 12px; border-radius: 15px; border: 1px solid transparent; background: transparent;
		color: var(--b-muted); font-weight: 600; font-size: 12px; }
	#rp-bar .rb-link:hover { background: var(--b-chip); color: var(--b-text); }
	#rp-bar .rb-link.active { background: #f97316; color: #fff; }
	#rp-bar .rb-right { display: flex; align-items: center; gap: 10px; white-space: nowrap; }
	#rp-bar .rb-hello { font-size: 12px; color: var(--b-muted); }
	#rp-bar .rb-hello b { color: var(--b-text); font-size: 13px; margin-inline-start: 4px; }
	#rp-bar .rb-role { font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 8px; background: var(--b-chip); color: var(--b-muted); }
	#rp-bar .rb-btn { height: 30px; padding: 0 12px; border-radius: 9px; border: 1px solid var(--b-line); background: transparent; color: var(--b-text); font-weight: 700; font-size: 12px; }
	#rp-bar .rb-btn:hover { border-color: #f97316; color: #ea580c; }
	#rp-bar .rb-out { color: #dc2626; border-color: rgba(220,38,38,.3); }
	#rp-bar .rb-out:hover { background: #dc2626; border-color: #dc2626; color: #fff; }
	@media (max-width: 760px) { #rp-bar .rb-nav, #rp-bar .rb-hello span { display: none; } }`;

	const esc = (v) => (window.frappe && frappe.utils ? frappe.utils.escape_html(String(v == null ? "" : v)) : String(v || ""));
	const route0 = () => ((window.frappe && frappe.get_route && frappe.get_route()[0]) || "").toLowerCase();
	const isAdmin = () => !!(frappe.user_roles || []).includes("Restaurant Admin") || frappe.session.user === "Administrator";

	// تسجيل الخروج: يسأل، يخرج، ويرجّعك لصفحة الدخول
	function logout() {
		frappe.confirm(__("Log out?"), () => {
			frappe.call({ method: "logout", callback: () => (window.location.href = "/pos-login") });
		});
	}

	// تبديل Dark / Light وحفظه على اليوزر
	function toggle_theme() {
		const root = document.documentElement;
		const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
		root.setAttribute("data-theme", next);
		root.setAttribute("data-theme-mode", next);
		frappe.xcall("frappe.core.doctype.user.user.switch_theme", { theme: next === "dark" ? "Dark" : "Light" }).catch(() => {});
	}

	window.rp = window.rp || {};
	window.rp.logout = window.rp.logout || logout;
	window.rp.toggle_theme = window.rp.toggle_theme || toggle_theme;

	// بناء الشريط مرة واحدة
	function build() {
		if (document.getElementById("rp-bar")) return;
		$("<style id='rp-bar-style'>").text(css).appendTo("head");
		const name = frappe.session.user_fullname || frappe.session.user || "";
		const logo = RP_LOGO_URL ? `<img src="${esc(RP_LOGO_URL)}" alt="">` : "🍽";
		const role = isAdmin() ? __("Admin") : __("Cashier");
		const links = [["cashier", __("Cashier")], ["delivery-orders", __("Delivery")]];
		if (isAdmin()) links.push(["admin-panel", __("Admin Panel")]);
		const nav = links.map(([r, l]) => `<button class="rb-link" data-r="${r}">${esc(l)}</button>`).join("");
		$(`<div id="rp-bar">
			<div class="rb-brand"><span class="rb-logo">${logo}</span>${esc(RP_BRAND)}</div>
			<div class="rb-nav">${nav}</div>
			<div class="rb-right">
				<span class="rb-hello"><span>${__("Welcome")}</span><b>${esc(name)}</b></span>
				<span class="rb-role">${esc(role)}</span>
				<button class="rb-btn rb-theme" title="${__("Dark / Light")}">🌓</button>
				<button class="rb-btn rb-out">⎋ ${__("Log out")}</button>
			</div>
		</div>`).appendTo("body");
		$("#rp-bar")
			.on("click", ".rb-link", (e) => frappe.set_route($(e.currentTarget).data("r")))
			.on("click", ".rb-theme", () => window.rp.toggle_theme())
			.on("click", ".rb-out", () => window.rp.logout());
	}

	// إظهار الشريط حسب الصفحة الحالية
	function update() {
		if (!window.frappe || !frappe.session || frappe.session.user === "Guest") return;
		const r = route0();
		const show = BAR_ROUTES.includes(r);
		if (show) build();
		$("body").toggleClass("rp-has-bar", show).toggleClass("rp-hide-navbar", HIDE_ONLY_ROUTES.includes(r));
		$("#rp-bar .rb-link").each(function () {
			$(this).toggleClass("active", $(this).data("r") === r);
		});
	}

	$(document).on("page-change startup", () => setTimeout(update, 50));
	$(function () {
		setTimeout(update, 300);
		if (window.frappe && frappe.router && frappe.router.on) frappe.router.on("change", () => setTimeout(update, 50));
	});
})();