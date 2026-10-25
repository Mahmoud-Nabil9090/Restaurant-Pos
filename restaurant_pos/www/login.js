
(function () {
    "use strict";

    const q = (selector) => document.querySelector(selector);
    const root = document.documentElement;

    const form = q("#login-form");
    const username = q("#username");
    const password = q("#password");
    const passwordToggle = q("#password-toggle");
    const themeToggle = q(".theme-toggle");
    const errorBox = q("#error-message");
    const errorText = q("#error-text");
    const submitButton = q("#submit-button");
    const submitLabel = q("#submit-label");

    let submitting = false;

    // Plain JavaScript: no Jinja syntax here.
    const LOGGED = false;

    // Theme settings
    function applyTheme(theme) {
        const value = theme === "dark" ? "dark" : "light";

        root.setAttribute("data-theme", value);
        q(".theme-symbol").textContent = value === "dark" ? "☀" : "☾";
        q(".theme-text").textContent =
            value === "dark" ? "Light mode" : "Dark mode";
    }

    try {
        const saved = localStorage.getItem("rp_theme");
        const prefersDark = window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches;

        applyTheme(saved || (prefersDark ? "dark" : "light"));
    } catch (_) {
        applyTheme("light");
    }

    themeToggle.addEventListener("click", function () {
        const next = root.getAttribute("data-theme") === "dark"
            ? "light"
            : "dark";

        applyTheme(next);

        try {
            localStorage.setItem("rp_theme", next);
        } catch (_) {}
    });

    // Show or hide password
    passwordToggle.addEventListener("click", function () {
        const show = password.type === "password";

        password.type = show ? "text" : "password";
        passwordToggle.textContent = show ? "◎" : "◉";

        passwordToggle.setAttribute(
            "aria-label",
            show ? "Hide password" : "Show password"
        );

        passwordToggle.setAttribute("aria-pressed", String(show));
    });

    // Get current Frappe user
    async function whoami() {
        const response = await fetch(
            "/api/method/restaurant_pos.auth.whoami",
            {
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            }
        );

        if (!response.ok) {
            throw new Error("whoami");
        }

        const payload = await response.json();
        const user = payload.message;

        if (!user || !user.full_name) {
            throw new Error("Invalid user response");
        }

        return user;
    }

    // Welcome animation
    function welcome(user) {
        q("#welcome-name").textContent = user.full_name || "there";
        q("#welcome-splash").classList.add("show");

        window.setTimeout(function () {
            window.location.replace(user.route || "/app");
        }, 1300);
    }

    function showError(message) {
        errorText.textContent = message;
        errorBox.hidden = false;
    }

    function setLoading(loading) {
        submitting = loading;
        submitButton.disabled = loading;

        submitLabel.textContent = loading
            ? "Signing in…"
            : "Sign in to workspace";
    }

    // This is false for standalone HTML.
    // Existing-session auto-redirect is intentionally disabled.
    if (LOGGED) {
        form.hidden = true;

        whoami()
            .then(welcome)
            .catch(function () {
                window.location.replace("/app");
            });
    }

    // Login through Frappe
    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        if (submitting) {
            return;
        }

        errorBox.hidden = true;

        if (!username.value.trim() || !password.value) {
            showError("Please enter your username and password.");
            return;
        }

        setLoading(true);

        try {
            const response = await fetch("/api/method/login", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type":
                        "application/x-www-form-urlencoded;charset=UTF-8",
                    "Accept": "application/json"
                },
                body: new URLSearchParams({
                    usr: username.value.trim(),
                    pwd: password.value
                })
            });

            let payload = {};

            try {
                payload = await response.json();
            } catch (_) {}

            if (!response.ok || payload.exc) {
                const message = String(payload.message || "");

                if (
                    response.status === 401 ||
                    /invalid login|incorrect password|disabled user/i.test(message)
                ) {
                    throw new Error("bad");
                }

                throw new Error("server");
            }

            const user = await whoami();
            welcome(user);

        } catch (error) {
            showError(
                error.message === "bad"
                    ? "Incorrect username or password, or the account is disabled."
                    : "Unable to sign in. Please try again or contact your administrator."
            );

            setLoading(false);
        }
    });
})();
