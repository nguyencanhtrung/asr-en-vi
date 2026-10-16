"use strict";

const accessFragment = window.location.hash.startsWith("#")
  ? window.location.hash.slice(1)
  : "";
if (accessFragment) {
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname,
  );
}

const form = document.querySelector("#access-form");
const tokenInput = document.querySelector("#access-token");
const submitButton = document.querySelector("#access-submit");
const statusMessage = document.querySelector("#access-status");

async function exchangeToken(token) {
  submitButton.disabled = true;
  statusMessage.textContent = "Đang xác thực…";
  try {
    const response = await fetch("/api/access/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      cache: "no-store",
      credentials: "same-origin",
    });
    if (response.ok) {
      window.location.replace("/");
      return;
    }
    statusMessage.textContent =
      response.status === 401
        ? "Token không hợp lệ. Hãy dùng link mới nhất trong terminal."
        : "Không thể xác thực. Hãy thử lại từ link trong terminal.";
  } catch {
    statusMessage.textContent = "Không kết nối được với ứng dụng trên máy này.";
  } finally {
    submitButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const token = tokenInput.value.trim();
  tokenInput.value = "";
  if (!token) {
    statusMessage.textContent = "Nhập access token để tiếp tục.";
    tokenInput.focus();
    return;
  }
  void exchangeToken(token);
});

if (accessFragment) {
  void exchangeToken(accessFragment);
}
