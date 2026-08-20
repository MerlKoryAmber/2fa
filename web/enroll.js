const $ = (s) => document.querySelector(s);

function tokenFromPath() {
  const m = location.pathname.match(/\/enroll\/([^/]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function showLogin(token, data) {
  $("#enroll-sub").textContent = "Войдите учётной записью, для которой выдана ссылка.";
  $("#enroll-body").classList.remove("hidden");
  $("#enroll-body").innerHTML = `
    <p class="muted">Ссылка для: <strong>${data.username}</strong></p>
    <p class="muted">Действует до: ${(data.expires_at || "").replace("T", " ").slice(0, 19)}</p>
    <div class="field">
      <label for="enroll-user">Логин</label>
      <input id="enroll-user" autocomplete="username" value="${data.username}" />
      <p class="field-hint">Логин AD (sAMAccountName) или UPN вида user@domain.</p>
    </div>
    <div class="field">
      <label for="enroll-pass">Пароль</label>
      <input id="enroll-pass" type="password" autocomplete="current-password" />
    </div>
    <button type="button" id="auth-btn">Войти</button>`;
  $("#auth-btn").addEventListener("click", () => authAndShowQr(token));
  $("#enroll-pass").addEventListener("keydown", (e) => {
    if (e.key === "Enter") authAndShowQr(token);
  });
}

function showQr(token, data) {
  $("#enroll-sub").textContent = `Пользователь: ${data.username}. Сканируйте QR в приложении аутентификатора.`;
  $("#enroll-body").innerHTML = `
    <img class="qr" src="data:image/png;base64,${data.qr_png_base64}" alt="QR" />
    <p class="muted">Секрет (если QR не сканируется): <code>${data.secret}</code></p>
    <p class="muted">Ссылка действует до: ${(data.expires_at || "").replace("T", " ").slice(0, 19)}</p>
    <div class="field">
      <label for="totp-code">Код из приложения</label>
      <input id="totp-code" inputmode="numeric" autocomplete="one-time-code" placeholder="000000" />
    </div>
    <div class="field">
      <label for="ems-id">ID в ExpressMS (опционально)</label>
      <input id="ems-id" placeholder="логин или ID в ExpressMS" />
      <p class="field-hint">Если укажете — сохраним для OTP через ExpressMS. Активный канал выберет администратор.</p>
    </div>
    <div class="field">
      <label for="tg-id">Telegram chat_id (опционально)</label>
      <input id="tg-id" placeholder="числовой chat_id" />
      <p class="field-hint">Если укажете — сохраним для OTP через Telegram. Можно указать несколько каналов сразу.</p>
    </div>
    <button type="button" id="confirm-btn">Подтвердить</button>`;
  $("#confirm-btn").addEventListener("click", async () => {
    $("#enroll-err").textContent = "";
    const code = $("#totp-code").value.trim();
    const ems = $("#ems-id").value.trim();
    const tg = $("#tg-id").value.trim();
    const body = { code, enroll_proof: data.enroll_proof };
    if (ems) body.expressms_id = ems;
    if (tg) body.telegram_chat_id = tg;
    const r = await fetch("/api/public/enroll/" + encodeURIComponent(token), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      $("#enroll-err").textContent = t || "Ошибка подтверждения";
      return;
    }
    $("#enroll-body").innerHTML = "<p><strong>Готово.</strong> 2FA настроена. Можно закрыть страницу.</p>";
    $("#enroll-sub").textContent = "";
  });
}

async function authAndShowQr(token) {
  $("#enroll-err").textContent = "";
  const username = $("#enroll-user").value.trim();
  const password = $("#enroll-pass").value;
  if (!username || !password) {
    $("#enroll-err").textContent = "Введите логин и пароль";
    return;
  }
  try {
    const r = await fetch("/api/public/enroll/" + encodeURIComponent(token) + "/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) {
      const t = await r.text();
      let msg = t || r.statusText;
      try {
        const j = JSON.parse(t);
        if (j.detail) msg = j.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const data = await r.json();
    showQr(token, data);
  } catch (e) {
    $("#enroll-err").textContent = String(e.message || e);
  }
}

async function load() {
  const token = tokenFromPath();
  if (!token) {
    $("#enroll-err").textContent = "Неверная ссылка";
    return;
  }
  try {
    const res = await fetch("/api/public/enroll/" + encodeURIComponent(token));
    if (!res.ok) {
      const t = await res.text();
      throw new Error(t || res.statusText);
    }
    const data = await res.json();
    showLogin(token, data);
  } catch (e) {
    $("#enroll-err").textContent = String(e.message || e);
    $("#enroll-sub").textContent = "";
  }
}

load();
