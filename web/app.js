const $ = (s) => document.querySelector(s);
let token = localStorage.getItem("mfa_token") || "";
let meRole = localStorage.getItem("mfa_role") || "";
let meUser = localStorage.getItem("mfa_user") || "";
let meAuthSource = localStorage.getItem("mfa_auth_source") || "local";

function isAdmin() {
  return meRole === "admin";
}
function isOperator() {
  return meRole === "operator";
}
function isAuditor() {
  return meRole === "auditor";
}

function applyRoleNav() {
  const show = {
    dash: true,
    tokens: isAdmin() || isOperator() || isAuditor(),
    users: isAdmin() || isOperator(),
    policy: isAdmin(),
    audit: isAdmin() || isAuditor(),
    settings: isAdmin(),
  };
  document.querySelectorAll(".nav-item").forEach((b) => {
    const tab = b.dataset.tab;
    b.classList.toggle("hidden", !show[tab]);
  });
  const syncBtn = $("#sync-ldap-btn");
  if (syncBtn) syncBtn.classList.toggle("hidden", !isAdmin());
  const pwdBtn = $("#change-password-btn");
  if (pwdBtn) pwdBtn.classList.toggle("hidden", meAuthSource === "ldap");
  const usersHint = $("#users-hint");
  if (usersHint && isOperator()) {
    usersHint.textContent =
      "Оператор: можно копировать ссылку и отправлять приглашение. Полная настройка 2FA — у администратора.";
  }
}

function confirmDialog({ title, message, confirmLabel = "Подтвердить", danger = false }) {
  return new Promise((resolve) => {
    const overlay = $("#confirm-overlay");
    const okBtn = $("#confirm-ok");
    const cancelBtn = $("#confirm-cancel");
    $("#confirm-title").textContent = title;
    $("#confirm-message").textContent = message;
    okBtn.textContent = confirmLabel;
    okBtn.className = "btn-sm" + (danger ? " danger-solid" : "");
    overlay.classList.remove("hidden");
    okBtn.focus();

    const finish = (value) => {
      overlay.classList.add("hidden");
      okBtn.removeEventListener("click", onOk);
      cancelBtn.removeEventListener("click", onCancel);
      overlay.removeEventListener("click", onBackdrop);
      document.removeEventListener("keydown", onKey);
      resolve(value);
    };

    const onOk = () => finish(true);
    const onCancel = () => finish(false);
    const onBackdrop = (e) => {
      if (e.target === overlay) finish(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") finish(false);
      if (e.key === "Enter") finish(true);
    };

    okBtn.addEventListener("click", onOk);
    cancelBtn.addEventListener("click", onCancel);
    overlay.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKey);
  });
}

async function api(path, opts = {}) {
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  if (res.status === 401) {
    token = "";
    localStorage.removeItem("mfa_token");
    location.reload();
    throw new Error("auth");
  }
  if (!res.ok) {
    const t = await res.text();
    const err = new Error(t || res.statusText);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function defaultTabForRole() {
  if (isAdmin()) return "dash";
  if (isOperator()) return "users";
  if (isAuditor()) return "audit";
  return "dash";
}

function tabAllowed(tab) {
  const btn = document.querySelector(`.nav-item[data-tab="${tab}"]`);
  return Boolean(btn && !btn.classList.contains("hidden"));
}

function readStoredTab() {
  let raw = (location.hash || "").replace(/^#/, "");
  if (!raw) {
    try {
      raw = sessionStorage.getItem("mfa_tab") || "";
    } catch (_) {}
  }
  const tab = (raw.split("/")[0] || "").toLowerCase();
  if (TABS.includes(tab) && tabAllowed(tab)) return tab;
  return defaultTabForRole();
}

function readStoredSettingsTab() {
  const raw = (location.hash || "").replace(/^#/, "");
  if (raw.startsWith("settings/")) {
    const st = raw.split("/")[1];
    if (st) return st;
  }
  try {
    return sessionStorage.getItem("mfa_settings_tab") || "ldap";
  } catch (_) {
    return "ldap";
  }
}

function showApp({ restore = true } = {}) {
  document.documentElement.classList.add("session");
  $("#login").classList.add("hidden");
  $("#app").classList.remove("hidden");
  applyRoleNav();
  const tab = restore ? readStoredTab() : defaultTabForRole();
  if (tab === "settings") {
    activeSettingsTab = readStoredSettingsTab();
  }
  switchTab(tab);
  document.documentElement.setAttribute("data-tab", tab);
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-err").textContent = "";
  const fd = new FormData(e.target);
  try {
    const out = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ username: fd.get("username"), password: fd.get("password") }),
    });
    token = out.token;
    meRole = out.role || "admin";
    meUser = out.username;
    meAuthSource = out.auth_source || "local";
    localStorage.setItem("mfa_token", token);
    localStorage.setItem("mfa_role", meRole);
    localStorage.setItem("mfa_user", meUser);
    localStorage.setItem("mfa_auth_source", meAuthSource);
    $("#who").textContent = `${out.username} · ${out.role_label || meRole}`;
    showApp({ restore: false });
  } catch (err) {
    const status = err.status || 0;
    const raw = String(err.message || err);
    if (status === 502 || status === 503 || status === 504 || /bad gateway|host is unreachable|failed to fetch/i.test(raw)) {
      $("#login-err").textContent = "API недоступен (502). Обновите страницу через минуту или сообщите админу.";
    } else if (status === 401 || raw.includes("Invalid username")) {
      $("#login-err").textContent = "Неверный логин или пароль";
    } else {
      $("#login-err").textContent = "Ошибка входа. Попробуйте снова.";
    }
  }
});

$("#logout").addEventListener("click", () => {
  token = "";
  meRole = "";
  meUser = "";
  localStorage.removeItem("mfa_token");
  localStorage.removeItem("mfa_role");
  localStorage.removeItem("mfa_user");
  localStorage.removeItem("mfa_auth_source");
  document.documentElement.classList.remove("session");
  location.reload();
});

function closeUserMenu() {
  const dd = $("#user-menu-dropdown");
  const btn = $("#user-menu-btn");
  if (!dd || !btn) return;
  dd.classList.add("hidden");
  btn.setAttribute("aria-expanded", "false");
}

function toggleUserMenu() {
  const dd = $("#user-menu-dropdown");
  const btn = $("#user-menu-btn");
  if (!dd || !btn) return;
  const open = dd.classList.contains("hidden");
  dd.classList.toggle("hidden", !open);
  btn.setAttribute("aria-expanded", open ? "true" : "false");
}

$("#user-menu-btn")?.addEventListener("click", (e) => {
  e.stopPropagation();
  toggleUserMenu();
});
$("#user-menu-dropdown")?.addEventListener("click", (e) => e.stopPropagation());
document.addEventListener("click", () => closeUserMenu());
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeUserMenu();
});
$("#change-password-btn")?.addEventListener("click", () => {
  closeUserMenu();
  $("#pwd-overlay").classList.remove("hidden");
  $("#pwd-err").textContent = "";
  $("#pwd-form").reset();
});
$("#logout")?.addEventListener("click", () => closeUserMenu());

const PAGE_TITLES = {
  dash: "Сводка",
  tokens: "Токены",
  users: "Пользователи",
  policy: "Политика",
  audit: "Аудит",
  settings: "Настройки",
};

const TABS = Object.keys(PAGE_TITLES);

function switchTab(tab) {
  if (!TABS.includes(tab)) tab = defaultTabForRole();
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tab);
  });
  TABS.forEach((id) => $("#" + id).classList.toggle("hidden", id !== tab));
  $("#page-title").textContent = PAGE_TITLES[tab] || tab;
  document.documentElement.setAttribute("data-tab", tab);
  try {
    sessionStorage.setItem("mfa_tab", tab);
  } catch (_) {}
  let hash = tab;
  if (tab === "settings") {
    hash = `settings/${activeSettingsTab || "ldap"}`;
  }
  const next = `#${hash}`;
  if (location.hash !== next) {
    history.replaceState(null, "", next);
  }
  if (tab === "dash") loadDash();
  if (tab === "tokens") loadTokens();
  if (tab === "users") loadUsers();
  if (tab === "policy") loadPolicy();
  if (tab === "audit") loadAudit();
  if (tab === "settings") {
    switchSettingsTab(activeSettingsTab || readStoredSettingsTab());
    loadSettings();
  }
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

window.addEventListener("hashchange", () => {
  if (!token) return;
  const tab = readStoredTab();
  if (tab === "settings") activeSettingsTab = readStoredSettingsTab();
  switchTab(tab);
});

function fmtTs(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").slice(0, 19);
}

function badgeClass(status) {
  if (status === "active") return "badge-active";
  if (status === "pending") return "badge-pending";
  return "badge-disabled";
}

async function loadTokens() {
  const q = new URLSearchParams();
  const serial = $("#token-filter-serial").value.trim();
  const type = $("#token-filter-type").value;
  const user = $("#token-filter-user").value.trim();
  const status = $("#token-filter-status").value;
  if (serial) q.set("serial", serial);
  if (type) q.set("type", type);
  if (user) q.set("user", user);
  if (status) q.set("status", status);
  const rows = await api("/api/tokens?" + q.toString());
  $("#token-empty").classList.toggle("hidden", rows.length > 0);
  const canManage = isAdmin();
  $("#token-rows").innerHTML = rows
    .map(
      (t) => `<tr>
      <td><code>${esc(t.serial)}</code></td>
      <td>${esc(t.type)}</td>
      <td>${esc(t.user)}</td>
      <td><span class="badge ${badgeClass(t.status)}">${esc(t.status)}</span></td>
      <td>${fmtTs(t.enrolled_at)}</td>
      <td>${fmtTs(t.last_used_at)}</td>
      <td class="row-actions">
        ${
          canManage
            ? `${t.status !== "disabled" ? `<button type="button" class="ghost btn-sm token-disable" data-serial="${esc(t.serial)}">Disable</button>` : `<button type="button" class="ghost btn-sm token-enable" data-serial="${esc(t.serial)}">Enable</button>`}
        <button type="button" class="ghost btn-sm danger token-revoke" data-serial="${esc(t.serial)}">Revoke</button>`
            : `<span class="muted">—</span>`
        }
      </td>
    </tr>`
    )
    .join("");
  if (!canManage) return;
  $("#token-rows").querySelectorAll(".token-disable").forEach((b) =>
    b.addEventListener("click", () => patchToken(b.dataset.serial, { active: false }))
  );
  $("#token-rows").querySelectorAll(".token-enable").forEach((b) =>
    b.addEventListener("click", () => patchToken(b.dataset.serial, { active: true }))
  );
  $("#token-rows").querySelectorAll(".token-revoke").forEach((b) =>
    b.addEventListener("click", async () => {
      const serial = b.dataset.serial;
      const ok = await confirmDialog({
        title: "Отозвать токен",
        message: `Токен ${serial} будет отозван. Восстановить его нельзя.`,
        confirmLabel: "Отозвать",
        danger: true,
      });
      if (!ok) return;
      await patchToken(serial, { revoke: true });
    })
  );
}

async function patchToken(serial, body) {
  await api("/api/tokens/" + encodeURIComponent(serial), { method: "PATCH", body: JSON.stringify(body) });
  loadTokens();
}

$("#token-filter-btn").addEventListener("click", () => loadTokens());

async function loadDash() {
  const s = await api("/api/stats");
  $("#stats").innerHTML = `
    <div class="card"><b>${s.users}</b>пользователи</div>
    <div class="card"><b>${s.enrolled}</b>с 2FA</div>
    <div class="card"><b>${s.ldap_configured ? "AD" : "нет DC"}</b>LDAP</div>`;
}

function chk(v) {
  return v ? "checked" : "";
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

const USER_OTP_METHODS = [
  { value: "NONE", label: "Не настроен" },
  { value: "TOTP", label: "TOTP (приложение)" },
  { value: "EXPRESSMS", label: "ExpressMS" },
  { value: "TELEGRAM", label: "Telegram" },
];

function userMethodLabel(code) {
  return USER_OTP_METHODS.find((m) => m.value === code)?.label || code;
}

function userChannelsCell(u) {
  const items = [];
  if (u.has_totp) {
    const active = u.otp_method === "TOTP" ? " channel-active" : "";
    const st = u.totp_confirmed ? "подтверждён" : "ожидает confirm";
    items.push(`<span class="channel-tag${active}">TOTP: ${esc(st)}</span>`);
  }
  if (u.expressms_id) {
    const active = u.otp_method === "EXPRESSMS" ? " channel-active" : "";
    items.push(`<span class="channel-tag${active}">ExpressMS: ${esc(u.expressms_id)}</span>`);
  }
  if (u.telegram_chat_id) {
    const active = u.otp_method === "TELEGRAM" ? " channel-active" : "";
    items.push(`<span class="channel-tag${active}">Telegram: ${esc(u.telegram_chat_id)}</span>`);
  }
  return items.length ? items.join("") : "—";
}

function totpStatusText(u) {
  if (!u.has_totp) {
    return "TOTP: не настроен — через «Отправить приглашение» / «Выпустить код».";
  }
  return u.totp_confirmed
    ? "TOTP: подтверждён (настроен по ссылке или администратором)."
    : "TOTP: ожидает confirm — пользователь ещё не ввёл код из приложения.";
}

let userEditId = null;

function openUserEdit(user) {
  userEditId = user.id;
  const overlay = $("#user-edit-overlay");
  $("#user-edit-title").textContent = "2FA: " + user.ad_username;
  $("#user-edit-sub").textContent = user.ldap_email ? "Email: " + user.ldap_email : "";
  $("#user-edit-err").textContent = "";
  const sel = $("#ue-method");
  sel.innerHTML = USER_OTP_METHODS.map(
    (m) => `<option value="${m.value}" ${user.otp_method === m.value ? "selected" : ""}>${m.label}</option>`
  ).join("");
  $("#ue-totp-status").textContent = totpStatusText(user);
  $("#ue-expressms").value = user.expressms_id || "";
  $("#ue-telegram").value = user.telegram_chat_id || "";
  overlay.classList.remove("hidden");
  sel.focus();
}

function closeUserEdit() {
  userEditId = null;
  $("#user-edit-overlay").classList.add("hidden");
}

function field(label, name, value = "", type = "text", hint = "") {
  const hintHtml = hint ? `<p class="field-hint">${hint}</p>` : "";
  return `<div class="field">
    <label for="${name}">${label}</label>
    <input id="${name}" name="${name}" type="${type}" value="${esc(value)}" />
    ${hintHtml}
  </div>`;
}

function fieldTextarea(label, name, value = "", hint = "", rows = 10) {
  const hintHtml = hint ? `<p class="field-hint">${hint}</p>` : "";
  return `<div class="field">
    <label for="${name}">${label}</label>
    <textarea id="${name}" name="${name}" rows="${rows}">${esc(value)}</textarea>
    ${hintHtml}
  </div>`;
}

const SECRET_MASK = "••••••••";
const SECRET_FIELDS = [
  "ldap_bind_password",
  "radius_shared_secret",
  "expressms_token",
  "smtp_password",
  "telegram_bot_token",
];

function secretField(label, name, set, placeholder = "оставить пустым — не менять", hint = "") {
  const hintHtml = hint ? `<p class="field-hint">${hint}</p>` : "";
  const valueAttr = set ? ` value="${SECRET_MASK}"` : "";
  const ph = set ? "введите новый, чтобы заменить" : placeholder;
  const setTag = set ? ' <span class="muted">(задан)</span>' : "";
  return `<div class="field">
    <label for="${name}">${label}${setTag}</label>
    <input id="${name}" name="${name}" type="password"${valueAttr} placeholder="${esc(ph)}" autocomplete="new-password" />
    ${hintHtml}
  </div>`;
}

function stripUnchangedSecrets(body) {
  for (const key of SECRET_FIELDS) {
    if (body[key] === SECRET_MASK || body[key] === "") delete body[key];
  }
  return body;
}

function showSettingsFlash(msg) {
  const el = $("#settings-flash");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(showSettingsFlash._t);
  showSettingsFlash._t = setTimeout(() => el.classList.add("hidden"), 5000);
}

let activeSettingsTab = "ldap";

function switchSettingsTab(tab) {
  activeSettingsTab = tab || "ldap";
  document.documentElement.setAttribute("data-settings-tab", activeSettingsTab);
  try {
    sessionStorage.setItem("mfa_settings_tab", activeSettingsTab);
  } catch (_) {}
  if ((location.hash || "").replace(/^#/, "").startsWith("settings")) {
    const next = `#settings/${activeSettingsTab}`;
    if (location.hash !== next) history.replaceState(null, "", next);
  }
  document.querySelectorAll(".settings-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.settingsTab === activeSettingsTab);
  });
  document.querySelectorAll(".settings-pane").forEach((p) => {
    p.classList.toggle("hidden", p.dataset.settingsPane !== activeSettingsTab);
  });
  const save = $("#settings-save-actions");
  if (save) save.classList.toggle("hidden", activeSettingsTab === "access");
}

document.querySelectorAll(".settings-tab").forEach((btn) => {
  btn.addEventListener("click", () => switchSettingsTab(btn.dataset.settingsTab));
});

function collectLdapTestBody(form) {
  const body = {
    ldap_use_ssl: form.elements.ldap_use_ssl?.checked ?? false,
    ldap_base_dn: form.elements.ldap_base_dn?.value ?? "",
    ldap_user_attr: form.elements.ldap_user_attr?.value ?? "",
    ldap_bind_user: form.elements.ldap_bind_user?.value ?? "",
    ldap_servers: collectDcList(form),
  };
  const testPwd = form.elements.test_ldap_bind_password?.value?.trim();
  const bindPwd = form.elements.ldap_bind_password?.value;
  if (testPwd) {
    body.ldap_bind_password = testPwd;
  } else if (bindPwd && bindPwd !== SECRET_MASK) {
    body.ldap_bind_password = bindPwd;
  } else if (bindPwd === SECRET_MASK) {
    body.ldap_bind_use_stored = true;
  }
  const u = form.elements.test_ldap_user?.value?.trim();
  const p = form.elements.test_ldap_pass?.value;
  if (u) body.username = u;
  if (p) body.password = p;
  return body;
}

function formatLdapTestLog(out) {
  const lines = [...(out.log || [])];
  lines.push("");
  lines.push(out.ok ? "── Итог: успех ──" : "── Итог: ошибка ──");
  if (out.message) lines.push(out.message);
  return lines.join("\n");
}

function checkField(label, name, checked, hint = "") {
  const hintHtml = hint ? `<p class="field-hint">${hint}</p>` : "";
  return `<div class="field field-check">
    <label class="check-row" for="${name}">
      <input type="checkbox" name="${name}" id="${name}" ${chk(checked)} />
      <span>${label}</span>
    </label>
    ${hintHtml}
  </div>`;
}

function parseAllowedFactors(raw) {
  return new Set(
    String(raw || "")
      .split(",")
      .map((m) => m.trim().toUpperCase())
      .filter(Boolean)
  );
}

function collectAllowedFactors(form) {
  const map = [
    ["factor_totp", "TOTP"],
    ["factor_expressms", "EXPRESSMS"],
    ["factor_telegram", "TELEGRAM"],
  ];
  return map
    .filter(([name]) => form.elements[name]?.checked)
    .map(([, code]) => code)
    .join(",");
}

function allowedFactorsFields(allowedSet) {
  const factors = [
    {
      name: "factor_totp",
      key: "TOTP",
      label: "TOTP (приложение-аутентификатор)",
      hint: "Google Authenticator, Microsoft Authenticator и аналоги. Код из 6 цифр по QR при enroll.",
    },
    {
      name: "factor_expressms",
      key: "EXPRESSMS",
      label: "ExpressMS",
      hint: "Одноразовый код в корпоративный мессенджер ExpressMS. Нужны настройки ExpressMS в разделе «Настройки».",
    },
    {
      name: "factor_telegram",
      key: "TELEGRAM",
      label: "Telegram",
      hint: "Одноразовый код в Telegram-бот. У пользователя должен быть привязан chat_id.",
    },
  ];
  return `<div class="field">
    <span class="field-group-label">Разрешённые методы 2FA</span>
    <div class="choice-stack">
      ${factors
        .map((f) => {
          const hintHtml = f.hint ? `<p class="field-hint">${f.hint}</p>` : "";
          return `<div class="field field-check">
            <label class="check-row" for="${f.name}">
              <input type="checkbox" name="${f.name}" id="${f.name}" ${chk(allowedSet.has(f.key))} />
              <span>${f.label}</span>
            </label>
            ${hintHtml}
          </div>`;
        })
        .join("")}
    </div>
    <p class="field-hint">Отметьте методы, которые можно назначать пользователям и использовать при RADIUS-входе.</p>
  </div>`;
}

function radioField(groupLabel, name, options, current, hint = "") {
  const hintHtml = hint ? `<p class="field-hint">${hint}</p>` : "";
  const opts = options
    .map(
      (o) => `<label class="check-row" for="${name}_${o.value}">
      <input type="radio" name="${name}" id="${name}_${o.value}" value="${o.value}" ${String(current) === String(o.value) ? "checked" : ""} />
      <span>${o.label}</span>
    </label>`
    )
    .join("");
  return `<div class="field field-check-stack">
    <span class="field-group-label">${groupLabel}</span>
    <div class="choice-stack">${opts}</div>
    ${hintHtml}
  </div>`;
}

function collectForm(form) {
  const body = {};
  for (const el of form.elements) {
    if (!el.name || el.type === "submit") continue;
    if (el.type === "checkbox") body[el.name] = el.checked;
    else body[el.name] = el.value;
  }
  return body;
}

function defaultLdapPort(useSsl) {
  return useSsl ? 636 : 389;
}

function dcRowsHtml(servers, useSsl) {
  const rows = servers && servers.length ? servers : [{ host: "", port: defaultLdapPort(useSsl) }];
  return rows
    .map(
      (s) => `<div class="dc-row">
      <input class="dc-host" type="text" placeholder="dc1.corp.local" value="${esc(s.host || "")}" />
      <input class="dc-port" type="number" min="1" max="65535" value="${s.port || defaultLdapPort(useSsl)}" />
      <button type="button" class="ghost dc-remove" title="Удалить">×</button>
    </div>`
    )
    .join("");
}

function wireDcList(form) {
  const list = form.querySelector("#ldap-dc-list");
  form.querySelector("#add-dc")?.addEventListener("click", () => {
    const useSsl = form.querySelector("#ldap_use_ssl")?.checked;
    const row = document.createElement("div");
    row.className = "dc-row";
    row.innerHTML = `<input class="dc-host" type="text" placeholder="dc2.corp.local" />
      <input class="dc-port" type="number" min="1" max="65535" value="${defaultLdapPort(useSsl)}" />
      <button type="button" class="ghost dc-remove" title="Удалить">×</button>`;
    list.appendChild(row);
    row.querySelector(".dc-remove").addEventListener("click", () => {
      if (list.querySelectorAll(".dc-row").length > 1) row.remove();
    });
  });
  list.querySelectorAll(".dc-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (list.querySelectorAll(".dc-row").length > 1) btn.closest(".dc-row").remove();
    });
  });
}

function collectDcList(form) {
  return [...form.querySelectorAll(".dc-row")]
    .map((row) => ({
      host: row.querySelector(".dc-host").value.trim(),
      port: Number(row.querySelector(".dc-port").value) || null,
    }))
    .filter((s) => s.host);
}

function readFileText(input) {
  return new Promise((resolve, reject) => {
    const file = input.files && input.files[0];
    if (!file) {
      reject(new Error("Выберите файл"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Не удалось прочитать файл"));
    reader.readAsText(file);
  });
}

function wireTlsUploads() {
  $("#tls-web-upload")?.addEventListener("click", async () => {
    const out = $("#tls-web-out");
    out.textContent = "";
    try {
      const cert_pem = await readFileText($("#tls-cert-file"));
      const key_pem = await readFileText($("#tls-key-file"));
      await api("/api/settings/tls/web", { method: "POST", body: JSON.stringify({ cert_pem, key_pem }) });
      out.textContent = "Сертификат панели загружен, nginx перезагружается.";
      showSettingsFlash("Сертификат панели загружен");
      await loadSettings();
    } catch (e) {
      out.textContent = String(e.message || e);
    }
  });
  $("#tls-ca-upload")?.addEventListener("click", async () => {
    const out = $("#tls-ca-out");
    out.textContent = "";
    try {
      const ca_pem = await readFileText($("#tls-ca-file"));
      await api("/api/settings/tls/root-ca", { method: "POST", body: JSON.stringify({ ca_pem }) });
      out.textContent = "Корневой CA добавлен в доверенные на сервере.";
      showSettingsFlash("Корневой CA загружен");
      await loadSettings();
    } catch (e) {
      out.textContent = String(e.message || e);
    }
  });
}

async function loadSettings() {
  const s = await api("/api/settings");
  const dcHtml = dcRowsHtml(s.ldap.servers, s.ldap.use_ssl);
  $("#settings-form").innerHTML = `
    <div class="settings-pane" data-settings-pane="ldap">
      <fieldset class="settings-section">
        <legend>LDAP</legend>
        <p class="field-hint">Импорт пользователей из AD — автоматически каждые 30 минут (Celery Beat). Кнопка «Загрузить из LDAP» на вкладке «Пользователи» — в любой момент.</p>
        <div class="field">
          <span class="field-group-label">Контроллеры домена (DC)</span>
          <div id="ldap-dc-list" class="dc-list">${dcHtml}</div>
          <button type="button" id="add-dc" class="ghost dc-add">+ Добавить DC</button>
          <p class="field-hint">Имя хоста и порт для каждого DC. При сбое — перебор по списку сверху вниз.</p>
        </div>
        ${checkField("SSL (LDAPS)", "ldap_use_ssl", s.ldap.use_ssl, "Включено — порт по умолчанию 636, выключено — 389.")}
        ${field("Base DN", "ldap_base_dn", s.ldap.base_dn || "", "text", "Пример: DC=Merl,DC=loc — обязателен для короткого логина bind и поиска пользователей.")}
        ${field("Атрибут логина", "ldap_user_attr", s.ldap.user_attr || "sAMAccountName", "text", "Обычно sAMAccountName для Active Directory.")}
        ${field("OU для загрузки", "ldap_sync_ou", s.ldap.sync_ou || "", "text", "DN подразделения, напр. OU=Сотрудники,DC=Merl,DC=loc — только пользователи из этой OU и вложенных. Пусто — весь Base DN.")}
        ${field("Группа AD для загрузки", "ldap_sync_group", s.ldap.sync_group || "", "text", "DN группы (CN=…) или короткое имя (sAMAccountName). Только члены группы; вложенные группы учитываются. Пусто — без фильтра. Можно вместе с OU.")}
        ${field("Учётная запись bind", "ldap_bind_user", s.ldap.bind_user || "", "text", "Работает: короткий логин (ldap) при заполненном Base DN; UPN user@Домен — имя из первого DC= (для DC=Merl,DC=loc → ldap@Merl). Не работает: domain\\user и UPN с .loc (ldap@merl.loc).")}
        ${secretField("Пароль bind", "ldap_bind_password", s.ldap.bind_password_set, "оставить пустым — не менять", "Пароль служебной учётки для поиска в AD.")}
        <div class="ldap-test-block">
          <h3 class="section-heading">Проверка подключения</h3>
          <p class="field-hint">Проверяет значения из формы выше. Сохранять перед проверкой не обязательно.</p>
          ${field("Пароль для проверки", "test_ldap_bind_password", "", "password", "Введите пароль bind здесь — удобнее, чем менять сохранённый «Пароль bind».")}
          ${field("Пользователь (опционально)", "test_ldap_user", "", "text", "Если указать с паролем — проверка входа пользователя, иначе только service bind.")}
          ${field("Пароль пользователя (опционально)", "test_ldap_pass", "", "password")}
          <button type="button" id="test-ldap-btn" class="ghost">Проверить LDAP</button>
          <pre id="test-ldap-out" class="test-log muted">Нажмите «Проверить LDAP» для вывода лога.</pre>
        </div>
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="radius">
      <fieldset class="settings-section">
        <legend>RADIUS</legend>
        ${secretField("Общий секрет", "radius_shared_secret", s.radius.shared_secret_set, "не менять", "Должен буква в букву совпасть с secret на VPN/NAS. Иначе NAS пишет «сервер не ответил».")}
        ${field("Порт", "radius_port", String(s.radius.port), "number", "Информационно; UDP-порт задаётся в compose.")}
        <div class="field">
          <label for="radius_allowed_clients">Разрешённые NAS (IP/CIDR)</label>
          <textarea id="radius_allowed_clients" name="radius_allowed_clients" placeholder="192.168.1.10&#10;10.0.0.0/8">${esc(s.radius.allowed_clients || "")}</textarea>
          <p class="field-hint">По одному адресу или подсети на строку. <strong>Пусто — любой NAS</strong>. Если список не пуст, IP VPN (кто шлёт RADIUS) обязан быть в списке, иначе отказ.</p>
        </div>
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="expressms">
      <fieldset class="settings-section">
        <legend>ExpressMS</legend>
        ${checkField("Dry-run", "expressms_dry_run", s.expressms.dry_run, "Код только в лог worker, без отправки в API.")}
        ${field("API URL", "expressms_api_url", s.expressms.api_url || "")}
        ${secretField("Token", "expressms_token", s.expressms.token_set, "не менять")}
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="smtp">
      <fieldset class="settings-section">
        <legend>SMTP (приглашения)</legend>
        ${checkField("Dry-run", "smtp_dry_run", s.smtp.dry_run, "Письмо только в лог worker/API, без отправки.")}
        ${field("Host", "smtp_host", s.smtp.host || "")}
        ${field("Port", "smtp_port", String(s.smtp.port), "number")}
        ${checkField("SSL/TLS", "smtp_use_ssl", s.smtp.use_ssl)}
        ${field("From", "smtp_from", s.smtp.from_addr || "")}
        ${field("Username", "smtp_username", s.smtp.username || "")}
        ${secretField("Password", "smtp_password", s.smtp.password_set)}
        ${field("Тема письма приглашения", "smtp_invite_subject", s.smtp.invite_subject || "", "text", "Пусто — «Приглашение на настройку 2FA». Подстановки: {username}, {invite_url}, {expires_at}.")}
        ${fieldTextarea(
          "Текст письма приглашения",
          "smtp_invite_body_template",
          s.smtp.invite_body_template || "",
          "Пусто — шаблон по умолчанию. Подстановки: {username}, {invite_url}, {expires_at}.",
          12
        )}
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="app">
      <fieldset class="settings-section">
        <legend>Приложение</legend>
        ${field("Public base URL", "public_base_url", s.app.public_base_url || "", "text", "Базовый URL для ссылок приглашения, напр. https://2fa.example.local")}
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="telegram">
      <fieldset class="settings-section">
        <legend>Telegram</legend>
        ${checkField("Dry-run", "telegram_dry_run", s.telegram.dry_run, "Код только в лог worker, без Bot API.")}
        ${secretField("Bot token", "telegram_bot_token", s.telegram.bot_token_set, "не менять")}
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="certificates">
      <fieldset class="settings-section">
        <legend>HTTPS веб-панели</legend>
        <p class="field-hint">Сертификат (цепочка) и закрытый ключ для nginx. После загрузки HTTPS перезагружается автоматически.</p>
        <p class="muted tls-status">Сертификат: ${s.tls.web_cert_set ? "загружен" : "не задан"} · Ключ: ${s.tls.web_key_set ? "загружен" : "не задан"}${s.tls.using_custom_web_tls ? " · активен" : " · self-signed по умолчанию"}</p>
        <div class="field">
          <label for="tls-cert-file">Цепочка сертификатов (PEM)</label>
          <input id="tls-cert-file" type="file" accept=".pem,.crt,.cer,.txt" />
          <p class="field-hint">Файл PEM: серверный сертификат и промежуточные CA (можно несколько блоков -----BEGIN CERTIFICATE-----).</p>
        </div>
        <div class="field">
          <label for="tls-key-file">Закрытый ключ (PEM)</label>
          <input id="tls-key-file" type="file" accept=".pem,.key,.txt" />
          <p class="field-hint">Файл PEM с -----BEGIN PRIVATE KEY----- или -----BEGIN RSA PRIVATE KEY-----.</p>
        </div>
        <button type="button" id="tls-web-upload" class="ghost">Загрузить сертификат панели</button>
        <p id="tls-web-out" class="field-hint"></p>
      </fieldset>
      <fieldset class="settings-section">
        <legend>Корневой CA</legend>
        <p class="field-hint">Корневой сертификат вашего CA добавляется в доверенные на сервере веб-панели (trusted root). Раздайте его клиентам для доверия HTTPS панели.</p>
        <p class="muted tls-status">Корневой CA: ${s.tls.root_ca_set ? "загружен" : "не задан"}</p>
        <div class="field">
          <label for="tls-ca-file">Корневой CA (PEM)</label>
          <input id="tls-ca-file" type="file" accept=".pem,.crt,.cer,.txt" />
        </div>
        <button type="button" id="tls-ca-upload" class="ghost">Загрузить корневой CA</button>
        <p id="tls-ca-out" class="field-hint"></p>
      </fieldset>
    </div>

    <div class="settings-pane hidden" data-settings-pane="access">
      <fieldset class="settings-section">
        <legend>Учётные записи панели</legend>
        <p class="field-hint">Кто уже входил (AD) или создан локально. Отключить — запрет входа без удаления.</p>
        <div id="panel-users-list" class="panel-users-wrap">Загрузка…</div>
      </fieldset>

      <fieldset class="settings-section">
        <legend>Группы AD</legend>
        <p class="field-hint">Локальный <b>администратор</b> — логин/пароль панели. <b>Оператор</b> и <b>аудитор</b> входят логином/паролем AD, если состоят в группах ниже (вложенные учитываются). Обе группы → роль оператор.</p>
        ${field("Группа AD операторов", "panel_operator_group", s.app.operator_group || "", "text", "DN (CN=…) или короткое имя. Приглашения + просмотр токенов.")}
        ${field("Группа AD аудиторов", "panel_auditor_group", s.app.auditor_group || "", "text", "DN или короткое имя. Токены + аудит.")}
        <div class="form-actions access-inline-actions">
          <button type="button" id="panel-groups-save" class="btn-sm">Сохранить группы AD</button>
          <span id="panel-groups-out" class="muted"></span>
        </div>
      </fieldset>

      <fieldset class="settings-section">
        <legend>Локальная учётка (break-glass)</legend>
        <p class="field-hint">Дополнительный локальный вход без AD. Для оператора/аудитора предпочтительнее группы AD.</p>
        <div class="field">
          <label for="pu-username">Логин</label>
          <input id="pu-username" autocomplete="off" />
        </div>
        <div class="field">
          <label for="pu-password">Пароль</label>
          <input id="pu-password" type="password" autocomplete="new-password" />
          <p class="field-hint">Минимум 8 символов.</p>
        </div>
        <div class="field">
          <label for="pu-role">Роль</label>
          <select id="pu-role">
            <option value="admin">Администратор</option>
            <option value="operator">Оператор</option>
            <option value="auditor">Аудитор</option>
          </select>
        </div>
        <button type="button" id="pu-create" class="btn-sm">Создать локально</button>
        <p id="pu-err" class="err"></p>
      </fieldset>
    </div>

    <div class="form-actions" id="settings-save-actions">
      <button type="submit">Сохранить настройки</button>
    </div>`;

  $("#settings-form").onsubmit = async (e) => {
    e.preventDefault();
    const body = stripUnchangedSecrets(collectForm(e.target));
    body.ldap_servers = collectDcList(e.target);
    await api("/api/settings", { method: "PATCH", body: JSON.stringify(body) });
    showSettingsFlash("Настройки сохранены");
    await loadSettings();
  };

  $("#test-ldap-btn").addEventListener("click", async () => {
    const form = $("#settings-form");
    const outEl = $("#test-ldap-out");
    outEl.textContent = "Проверка…";
    try {
      const out = await api("/api/settings/test-ldap", {
        method: "POST",
        body: JSON.stringify(collectLdapTestBody(form)),
      });
      outEl.textContent = formatLdapTestLog(out);
      outEl.classList.toggle("muted", out.ok);
    } catch (e) {
      outEl.textContent = String(e.message || e);
      outEl.classList.remove("muted");
    }
  });

  wireDcList($("#settings-form"));
  wireTlsUploads();
  wirePanelUsers();
  switchSettingsTab(activeSettingsTab);
}

async function wirePanelUsers() {
  const listEl = $("#panel-users-list");
  if (!listEl) return;
  $("#panel-groups-save")?.addEventListener("click", async () => {
    const out = $("#panel-groups-out");
    try {
      await api("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({
          panel_operator_group: $("#panel_operator_group")?.value ?? "",
          panel_auditor_group: $("#panel_auditor_group")?.value ?? "",
        }),
      });
      if (out) out.textContent = "Сохранено";
      showSettingsFlash("Группы доступа сохранены");
    } catch (e) {
      if (out) out.textContent = String(e.message || e);
    }
  });
  const srcLabel = (s) => (s === "ldap" ? "AD" : "локальный");
  const render = async () => {
    try {
      const rows = await api("/api/panel-users");
      if (!rows.length) {
        listEl.innerHTML = `<p class="muted">Пока никого нет — войдите локальным admin или задайте группы AD.</p>`;
        return;
      }
      listEl.innerHTML = `
        <div class="panel-users-scroll">
        <table class="data-table panel-users-table">
          <colgroup>
            <col class="col-login" />
            <col class="col-role" />
            <col class="col-src" />
            <col class="col-status" />
            <col class="col-actions" />
          </colgroup>
          <thead><tr>
            <th>Логин</th>
            <th>Роль</th>
            <th>Источник</th>
            <th>Статус</th>
            <th></th>
          </tr></thead>
          <tbody>
            ${rows
              .map(
                (u) => `<tr>
              <td>${esc(u.username)}</td>
              <td>${esc(u.role_label || u.role)}</td>
              <td>${esc(srcLabel(u.auth_source))}</td>
              <td>${u.is_active ? "активен" : "отключён"}</td>
              <td class="row-actions">
                <button type="button" class="ghost btn-sm pu-toggle" data-id="${u.id}" data-active="${u.is_active ? "1" : "0"}">${u.is_active ? "Отключить" : "Включить"}</button>
                ${
                  u.auth_source !== "ldap"
                    ? `<button type="button" class="ghost btn-sm pu-reset" data-id="${u.id}">Сбросить пароль</button>`
                    : `<span class="muted">пароль в AD</span>`
                }
              </td>
            </tr>`
              )
              .join("")}
          </tbody>
        </table>
        </div>`;
      listEl.querySelectorAll(".pu-toggle").forEach((b) =>
        b.addEventListener("click", async () => {
          const active = b.dataset.active !== "1";
          await api("/api/panel-users/" + b.dataset.id, {
            method: "PATCH",
            body: JSON.stringify({ is_active: active }),
          });
          await render();
        })
      );
      listEl.querySelectorAll(".pu-reset").forEach((b) =>
        b.addEventListener("click", async () => {
          const pwd = prompt("Новый пароль (мин. 8 символов):");
          if (!pwd || pwd.length < 8) return;
          await api("/api/panel-users/" + b.dataset.id, {
            method: "PATCH",
            body: JSON.stringify({ password: pwd }),
          });
          alert("Пароль обновлён");
        })
      );
    } catch (e) {
      listEl.textContent = String(e.message || e);
    }
  };
  await render();
  $("#pu-create")?.addEventListener("click", async () => {
    $("#pu-err").textContent = "";
    try {
      await api("/api/panel-users", {
        method: "POST",
        body: JSON.stringify({
          username: $("#pu-username").value.trim(),
          password: $("#pu-password").value,
          role: $("#pu-role").value,
        }),
      });
      $("#pu-username").value = "";
      $("#pu-password").value = "";
      await render();
    } catch (e) {
      $("#pu-err").textContent = String(e.message || e);
    }
  });
}

async function loadUsers() {
  const q = new URLSearchParams();
  const ad = $("#user-filter-ad").value.trim();
  const email = $("#user-filter-email").value.trim();
  const method = $("#user-filter-method").value;
  const totp = $("#user-filter-totp").value;
  if (ad) q.set("ad", ad);
  if (email) q.set("email", email);
  if (method) q.set("method", method);
  if (totp) q.set("totp", totp);
  const rows = await api("/api/users?" + q.toString());
  $("#users-empty").classList.toggle("hidden", rows.length > 0);
  $("#user-rows").innerHTML = rows
    .map(
      (u) => `<tr>
      <td class="col-ad">${esc(u.ad_username)}</td>
      <td class="col-name" title="${esc(u.display_name || "")}">${esc(u.display_name || "—")}</td>
      <td class="col-email muted">${esc(u.ldap_email || "—")}</td>
      <td class="col-method">${esc(userMethodLabel(u.otp_method))}</td>
      <td class="user-channels muted">${userChannelsCell(u)}</td>
      <td class="row-actions">
        ${
          isAdmin()
            ? `<button type="button" data-id="${u.id}" class="ghost btn-sm edit-user">Настроить 2FA</button>
        <button type="button" data-id="${u.id}" class="ghost btn-sm issue-code">Выпустить код</button>`
            : ""
        }
        <button type="button" data-id="${u.id}" class="ghost btn-sm copy-invite">Копировать ссылку</button>
        <button type="button" data-id="${u.id}" class="btn-sm send-invite" ${u.ldap_email ? "" : "disabled title=\"Нет email\""}>Отправить приглашение</button>
      </td>
    </tr>`
    )
    .join("");
  const byId = Object.fromEntries(rows.map((u) => [String(u.id), u]));
  if (isAdmin()) {
    $("#user-rows").querySelectorAll(".edit-user").forEach((b) =>
      b.addEventListener("click", () => openUserEdit(byId[b.dataset.id]))
    );
    $("#user-rows").querySelectorAll(".issue-code").forEach((b) =>
      b.addEventListener("click", async () => {
        const out = await api("/api/users/" + b.dataset.id + "/totp/issue", { method: "POST", body: "{}" });
        $("#issue-modal").classList.remove("hidden");
        $("#issue-modal").innerHTML = `
        <h3 class="section-heading">TOTP для пересылки пользователю</h3>
        <p class="muted">Confirm не требуется — передайте QR/секрет вручную. Токен в статусе pending до confirm пользователем или RADIUS.</p>
        <img class="qr" src="data:image/png;base64,${out.qr_png_base64}" alt="QR" />
        <p><code>${esc(out.secret)}</code></p>
        <button type="button" class="ghost" id="close-issue">Закрыть</button>`;
        $("#close-issue").addEventListener("click", () => $("#issue-modal").classList.add("hidden"));
        loadTokens();
      })
    );
  }
  $("#user-rows").querySelectorAll(".copy-invite").forEach((b) =>
    b.addEventListener("click", async () => {
      try {
        const out = await api("/api/users/" + b.dataset.id + "/invite-link", { method: "POST", body: "{}" });
        await navigator.clipboard.writeText(out.invite_url);
        const prev = b.textContent;
        b.textContent = "Скопировано";
        setTimeout(() => {
          b.textContent = prev;
        }, 2000);
      } catch (e) {
        alert(String(e.message || e));
      }
    })
  );
  $("#user-rows").querySelectorAll(".send-invite").forEach((b) =>
    b.addEventListener("click", async () => {
      const ok = await confirmDialog({
        title: "Отправить приглашение",
        message: "На email пользователя уйдёт письмо со ссылкой на настройку 2FA.",
        confirmLabel: "Отправить",
      });
      if (!ok) return;
      const out = await api("/api/users/" + b.dataset.id + "/invite", { method: "POST", body: "{}" });
      alert(
        (out.mail && out.mail.dry_run ? "Письмо (dry-run, см. лог API/worker)" : "Приглашение отправлено на email") +
          "\n" +
          out.invite_url
      );
    })
  );
}

$("#user-filter-btn").addEventListener("click", () => loadUsers());

$("#user-edit-cancel").addEventListener("click", closeUserEdit);
$("#user-edit-overlay").addEventListener("click", (e) => {
  if (e.target === $("#user-edit-overlay")) closeUserEdit();
});
$("#user-edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!userEditId) return;
  $("#user-edit-err").textContent = "";
  const method = $("#ue-method").value;
  const body = {
    otp_method: method,
    expressms_id: $("#ue-expressms").value.trim() || null,
    telegram_chat_id: $("#ue-telegram").value.trim() || null,
  };
  try {
    await api("/api/users/" + userEditId, { method: "PATCH", body: JSON.stringify(body) });
    closeUserEdit();
    loadUsers();
    loadTokens();
  } catch (err) {
    let msg = String(err.message || err);
    try {
      const j = JSON.parse(msg);
      if (j.detail) msg = j.detail;
    } catch (_) {}
    $("#user-edit-err").textContent = msg;
  }
});

$("#sync-ldap-btn").addEventListener("click", async () => {
  $("#sync-ldap-out").textContent = "…";
  try {
    const out = await api("/api/users/sync-ldap", { method: "POST", body: "{}" });
    if (out.total === 0) {
      $("#sync-ldap-out").textContent = "LDAP ответил, но пользователей 0 — проверьте Base DN и права bind.";
    } else {
      $("#sync-ldap-out").textContent = `Загружено: ${out.total}, новых: ${out.created}`;
    }
    loadUsers();
  } catch (e) {
    let msg = String(e.message || e);
    try {
      const j = JSON.parse(msg);
      if (j.detail) msg = j.detail;
    } catch (_) {}
    $("#sync-ldap-out").textContent = msg;
  }
});

async function loadPolicy() {
  const p = await api("/api/policies");
  const allowed = parseAllowedFactors(p.allowed_second_factors);
  $("#policy-form").innerHTML = `
    <input type="hidden" name="id" value="${p.id}" />
    <fieldset class="settings-section">
      <legend>Общее</legend>
      ${radioField(
        "Требовать 2FA",
        "require_2fa",
        [
          { value: "true", label: "Да — без второго фактора вход запрещён" },
          { value: "false", label: "Нет — достаточно пароля LDAP" },
        ],
        p.require_2fa ? "true" : "false",
        "Если «Нет» — после успешного LDAP RADIUS сразу выдаёт Access-Accept без второго фактора."
      )}
      ${allowedFactorsFields(allowed)}
    </fieldset>
    <fieldset class="settings-section">
      <legend>TOTP</legend>
      <div class="field">
        <label for="totp_window_steps">Окно проверки TOTP (шаги)</label>
        <input name="totp_window_steps" id="totp_window_steps" type="number" min="0" max="5" value="${p.totp_window_steps}" />
        <p class="field-hint">Сколько соседних 30‑секундных интервалов принимается. 1 ≈ ±30 сек от текущего кода.</p>
      </div>
    </fieldset>
    <fieldset class="settings-section">
      <legend>OTP по сообщению (ExpressMS / Telegram)</legend>
      <div class="field">
        <label for="otp_ttl_seconds">Срок жизни OTP, сек</label>
        <input name="otp_ttl_seconds" id="otp_ttl_seconds" type="number" min="30" value="${p.otp_ttl_seconds}" />
        <p class="field-hint">После отправки кода в мессенджер — сколько секунд он действителен для ввода в RADIUS.</p>
      </div>
      <div class="field">
        <label for="max_otp_attempts_per_challenge">Макс. попыток ввода OTP</label>
        <input name="max_otp_attempts_per_challenge" id="max_otp_attempts_per_challenge" type="number" min="1" value="${p.max_otp_attempts_per_challenge}" />
        <p class="field-hint">На один RADIUS Access-Challenge (один State). Превышение — отказ.</p>
      </div>
    </fieldset>
    <fieldset class="settings-section">
      <legend>RADIUS и приглашения</legend>
      <div class="field">
        <label for="challenge_ttl_seconds">Срок challenge (State), сек</label>
        <input name="challenge_ttl_seconds" id="challenge_ttl_seconds" type="number" min="30" value="${p.challenge_ttl_seconds}" />
        <p class="field-hint">Как долго NAS может прислать OTP с тем же State после Access-Challenge.</p>
      </div>
      <div class="field">
        <label for="enroll_invite_ttl_seconds">Срок ссылки приглашения, сек</label>
        <input name="enroll_invite_ttl_seconds" id="enroll_invite_ttl_seconds" type="number" min="300" value="${p.enroll_invite_ttl_seconds ?? 86400}" />
        <p class="field-hint">Email-ссылка на страницу enroll. 86400 = 24 часа.</p>
      </div>
    </fieldset>
    <div class="form-actions">
      <button type="submit">Сохранить политику</button>
    </div>`;
  $("#policy-form").onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);
    const allowedFactors = collectAllowedFactors(form);
    if (!allowedFactors) {
      alert("Выберите хотя бы один метод 2FA.");
      return;
    }
    await api("/api/policies/" + fd.get("id"), {
      method: "PATCH",
      body: JSON.stringify({
        require_2fa: fd.get("require_2fa") === "true",
        allowed_second_factors: allowedFactors,
        totp_window_steps: Number(fd.get("totp_window_steps")),
        otp_ttl_seconds: Number(fd.get("otp_ttl_seconds")),
        max_otp_attempts_per_challenge: Number(fd.get("max_otp_attempts_per_challenge")),
        challenge_ttl_seconds: Number(fd.get("challenge_ttl_seconds")),
        enroll_invite_ttl_seconds: Number(fd.get("enroll_invite_ttl_seconds")),
      }),
    });
  };
}

const AUDIT_EVENT_LABELS = {
  USER_PATCH: "Изменение пользователя",
  TOTP_ISSUE: "Выпуск TOTP",
  TOTP_ENROLL_OK: "TOTP подтверждён",
  TOKEN_REVOKE: "Отзыв токена",
  TOKEN_PATCH: "Изменение токена",
  SETTINGS_PATCH: "Изменение настроек",
  TLS_WEB_UPLOAD: "Загрузка HTTPS-сертификата",
  TLS_ROOT_CA_UPLOAD: "Загрузка корневого CA",
  LDAP_SYNC: "Синхронизация LDAP",
  LDAP_SYNC_AUTO: "Авто-синхронизация LDAP",
  ENROLL_INVITE_LINK: "Ссылка приглашения",
  ENROLL_INVITE: "Отправка приглашения",
  ENROLL_AUTH_FAIL: "Ошибка входа по приглашению",
  ENROLL_AUTH_OK: "Вход по приглашению",
  ENROLL_INVITE_OK: "2FA настроена по приглашению",
  LDAP_FAIL: "Ошибка LDAP",
  LDAP_OK: "Успешный LDAP",
  RADIUS_ACCEPT: "RADIUS: доступ разрешён",
  RADIUS_REJECT: "RADIUS: доступ запрещён",
  RADIUS_CHALLENGE: "RADIUS: запрос 2FA",
  SEND_EXPRESSMS: "OTP отправлен в ExpressMS",
  SEND_TELEGRAM: "OTP отправлен в Telegram",
  OTP_OK: "OTP принят",
  OTP_FAIL: "OTP отклонён",
};

const AUDIT_META_LABELS = {
  by: "Администратор",
  reason: "Причина",
  method: "Метод 2FA",
  serial: "Serial токена",
  created: "Создано пользователей",
  total: "Всего в LDAP",
  email: "Email",
  dry_run: "Dry-run",
  active: "Токен активен",
  keys: "Изменённые поля",
};

const AUDIT_REASON_LABELS = {
  username_mismatch: "логин не совпадает с приглашением",
  ldap_fail: "неверный пароль LDAP",
  "2fa_disabled": "2FA отключена в политике",
  not_enrolled: "2FA не настроена",
  unknown_state: "неизвестный state",
  replay: "повтор state",
  expired: "истёк срок",
  user_mismatch: "другой пользователь",
  attempts: "исчерпаны попытки",
  otp_ttl: "истёк OTP",
};

const AUDIT_SETTINGS_LABELS = {
  ldap_use_ssl: "LDAPS",
  ldap_base_dn: "Base DN",
  ldap_user_attr: "Атрибут логина",
  ldap_bind_user: "Учётная запись bind",
  ldap_bind_password: "Пароль bind",
  ldap_sync_ou: "OU для загрузки",
  ldap_sync_group: "Группа AD",
  radius_shared_secret: "RADIUS secret",
  radius_port: "RADIUS порт",
  radius_allowed_clients: "Разрешённые NAS",
  expressms_dry_run: "ExpressMS dry-run",
  expressms_api_url: "ExpressMS URL",
  expressms_token: "ExpressMS token",
  telegram_dry_run: "Telegram dry-run",
  telegram_bot_token: "Telegram bot token",
  public_base_url: "Public base URL",
  smtp_dry_run: "SMTP dry-run",
  smtp_host: "SMTP хост",
  smtp_port: "SMTP порт",
  smtp_use_ssl: "SMTP SSL",
  smtp_from: "SMTP from",
  smtp_username: "SMTP логин",
  smtp_password: "SMTP пароль",
  smtp_invite_subject: "Тема приглашения",
  smtp_invite_body_template: "Шаблон приглашения",
};

function auditEventLabel(eventType, fromApi) {
  if (fromApi && fromApi !== eventType) return fromApi;
  return AUDIT_EVENT_LABELS[eventType] || eventType;
}

function formatAuditMetaValue(key, value) {
  if (value == null) return "—";
  if (key === "reason") return AUDIT_REASON_LABELS[value] || String(value);
  if (key === "method") return value;
  if (key === "dry_run" || key === "active") return value ? "да" : "нет";
  if (key === "keys" && Array.isArray(value)) {
    const labels = value.map((k) => AUDIT_SETTINGS_LABELS[k] || k);
    return labels.length ? labels.join(", ") : "—";
  }
  if (typeof value === "boolean") return value ? "да" : "нет";
  return String(value);
}

function formatAuditMeta(meta) {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) return "—";
  const parts = Object.entries(meta).map(([key, value]) => {
    const label = AUDIT_META_LABELS[key] || key;
    return `${label}: ${formatAuditMetaValue(key, value)}`;
  });
  return parts.length ? parts.join("; ") : "—";
}

async function loadAudit() {
  const rows = await api("/api/audit");
  $("#audit-rows").innerHTML = rows
    .map((e) => {
      const label = auditEventLabel(e.event_type, e.event_label);
      const details = e.meta_text && e.meta_text !== "—" ? e.meta_text : formatAuditMeta(e.meta);
      return `<tr>
      <td class="audit-ts">${fmtTs(e.timestamp)}</td>
      <td class="audit-event">${esc(label)}</td>
      <td class="audit-user">${esc(e.username || "—")}</td>
      <td class="audit-meta muted">${esc(details)}</td>
    </tr>`;
    })
    .join("");
}

if (token) {
  api("/api/me")
    .then((m) => {
      meUser = m.username;
      meRole = m.role || "admin";
      meAuthSource = m.auth_source || "local";
      localStorage.setItem("mfa_role", meRole);
      localStorage.setItem("mfa_user", meUser);
      localStorage.setItem("mfa_auth_source", meAuthSource);
      $("#who").textContent = `${m.username} · ${m.role_label || meRole}`;
      showApp();
    })
    .catch(() => {
      document.documentElement.classList.remove("session");
      $("#login").classList.remove("hidden");
      $("#app").classList.add("hidden");
    });
}

$("#pwd-cancel")?.addEventListener("click", () => $("#pwd-overlay").classList.add("hidden"));
$("#pwd-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#pwd-err").textContent = "";
  const fd = new FormData(e.target);
  try {
    await api("/api/me/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: fd.get("current_password"),
        new_password: fd.get("new_password"),
      }),
    });
    $("#pwd-overlay").classList.add("hidden");
    alert("Пароль изменён");
  } catch (err) {
    $("#pwd-err").textContent = String(err.message || err);
  }
});
