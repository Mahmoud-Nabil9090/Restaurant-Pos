// Restaurant POS — Extensions: PWA meta-tags + Sound Notifications
// ══════════════════════════════════════════════════════════════════

// ── 1. PWA: Manifest link + iOS / Android meta tags ────────────
(function () {
	if (!document.querySelector('link[rel="manifest"]')) {
		var lnk = document.createElement("link");
		lnk.rel = "manifest";
		lnk.href = "/assets/restaurant_pos/manifest.json";
		document.head.appendChild(lnk);
	}
	var metas = {
		"apple-mobile-web-app-capable": "yes",
		"apple-mobile-web-app-status-bar-style": "default",
		"apple-mobile-web-app-title": "Restaurant POS",
		"mobile-web-app-capable": "yes",
		"theme-color": "#f97316",
	};
	Object.keys(metas).forEach(function (name) {
		if (!document.querySelector('meta[name="' + name + '"]')) {
			var m = document.createElement("meta");
			m.name = name;
			m.content = metas[name];
			document.head.appendChild(m);
		}
	});
})();

// ── 2. Sound Notifications (Web Audio API — no external files) ──
(function () {
	var ctx;
	try {
		ctx = new (window.AudioContext || window.webkitAudioContext)();
	} catch (e) {
		window.rpSound = null;
		return;
	}

	function beep(freq, dur, type, vol) {
		if (!ctx) return;
		try {
			if (ctx.state === "suspended") ctx.resume();
			var o = ctx.createOscillator();
			var g = ctx.createGain();
			o.connect(g);
			g.connect(ctx.destination);
			o.frequency.value = freq;
			o.type = type || "sine";
			g.gain.setValueAtTime(vol || 0.22, ctx.currentTime);
			g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
			o.start();
			o.stop(ctx.currentTime + dur);
		} catch (e) {
			/* audio unavailable */
		}
	}

	function seq(notes, gap) {
		notes.forEach(function (n, i) {
			setTimeout(function () {
				beep(n[0], n[1], n[2], n[3]);
			}, i * (gap || 180));
		});
	}

	/** @namespace rpSound — call these from anywhere: window.rpSound.newOrder() */
	window.rpSound = {
		/** Two ascending tones — new kitchen ticket or incoming order */
		newOrder: function () {
			seq([[880, 0.12], [1100, 0.18]]);
		},
		/** High ping — item ready / served */
		itemReady: function () {
			beep(1200, 0.2);
		},
		/** Low square wave — order or item cancelled */
		cancelled: function () {
			seq([[400, 0.25, "square"], [300, 0.35, "square"]], 300);
		},
		/** Quick high beep — generic success */
		success: function () {
			beep(1000, 0.12);
		},
		/** Low buzz — error or not found */
		error: function () {
			beep(300, 0.25, "sawtooth");
		},
		/** Ultra-short blip — barcode scanned */
		scan: function () {
			beep(1500, 0.06);
		},
	};
})();
