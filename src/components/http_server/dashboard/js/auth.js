async function api(path, options = {}) {
    const response = await fetch(path, { credentials: "include", ...options });
    return response;
}

async function login(event) {
    event.preventDefault();
    const errorDiv = document.getElementById("login-error");
    errorDiv.textContent = "";

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    try {
        const response = await api("/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await response.json();
        if (!response.ok) {
            errorDiv.textContent = "Invalid username or password";
            return false;
        }
        if (data.require_change_password) {
            window.location.href = "/dashboard/change-password.html";
            return false;
        }
        window.location.href = "/dashboard/";
    } catch (error) {
        errorDiv.textContent = "Connection failed";
    }
    return false;
}

async function setPassword(event) {
    event.preventDefault();
    const errorDiv = document.getElementById("set-password-error");
    const successDiv = document.getElementById("set-password-success");
    errorDiv.textContent = "";
    successDiv.textContent = "";

    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") || "";
    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirm-password").value;

    if (password !== confirm) {
        errorDiv.textContent = "Passwords do not match";
        return false;
    }

    try {
        const response = await api("/auth/set-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token, password }),
        });
        const data = await response.json();
        if (!response.ok) {
            if (data.errors) {
                const list = document.createElement("ul");
                for (const message of data.errors) {
                    const item = document.createElement("li");
                    item.textContent = message;
                    list.appendChild(item);
                }
                errorDiv.appendChild(list);
            } else if (data.status === "expired_token") {
                errorDiv.textContent = "Invite link expired";
            } else {
                errorDiv.textContent = "Invalid invite link";
            }
            return false;
        }
        successDiv.textContent = "Password set, redirecting...";
        setTimeout(() => { window.location.href = "/dashboard/"; }, 800);
    } catch (error) {
        errorDiv.textContent = "Connection failed";
    }
    return false;
}

async function checkInviteToken() {

    const params = new URLSearchParams(window.location.search);
    const token = params.get("token") || "";
    const errorDiv = document.getElementById("set-password-error");
    if (!token) {
        errorDiv.textContent = "Missing invite token";
        return;
    }
    try {
        const response = await api(`/auth/invite/validate?token=${encodeURIComponent(token)}`);
        const data = await response.json();
        if (!response.ok) {
            errorDiv.textContent = data.status === "expired_token"
                ? "Invite link expired"
                : "Invalid invite link";
        }
    } catch (error) {
        errorDiv.textContent = "Connection failed";
    }
}

async function changePassword(event) {
    event.preventDefault();
    const errorDiv = document.getElementById("change-password-error");
    const successDiv = document.getElementById("change-password-success");
    errorDiv.textContent = "";
    successDiv.textContent = "";

    const currentPassword = document.getElementById("current-password").value;
    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirm-password").value;

    if (password !== confirm) {
        errorDiv.textContent = "Passwords do not match";
        return false;
    }

    try {
        const response = await api("/auth/change-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ current_password: currentPassword, new_password: password }),
        });
        const data = await response.json();
        if (!response.ok) {
            if (data.errors) {
                errorDiv.textContent = data.errors.join("; ");
            } else if (response.status === 401) {
                errorDiv.textContent = "Invalid current password";
            } else {
                errorDiv.textContent = "Failed to change password";
            }
            return false;
        }
        successDiv.textContent = "Password changed, redirecting...";
        setTimeout(() => { window.location.href = "/dashboard/"; }, 800);
    } catch (error) {
        errorDiv.textContent = "Connection failed";
    }
    return false;
}

async function logout() {
    await api("/auth/logout", { method: "POST" });
    window.location.href = "/dashboard/login.html";
}
