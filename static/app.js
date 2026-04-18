async function loadFeed(limit) {
  const results = document.getElementById("feed-results");
  const status = document.getElementById("feed-status");
  const statusText = document.getElementById("feed-status-text");
  const button = document.getElementById("refresh-button");
  if (!results || !status || !statusText) {
    return;
  }

  status.classList.remove("hidden");
  status.classList.remove("message-error");
  statusText.textContent = "Loading the current multi-agent security feed...";
  if (button) {
    button.disabled = true;
    button.textContent = "Refreshing...";
  }

  try {
    const endpoint = results.dataset.feedEndpoint || "/feed";
    const separator = endpoint.includes("?") ? "&" : "?";
    const response = await fetch(`${endpoint}${separator}limit=${encodeURIComponent(limit)}`, {
      headers: { "X-Requested-With": "fetch" },
    });
    if (!response.ok) {
      throw new Error(`Request failed with HTTP ${response.status}`);
    }
    results.innerHTML = await response.text();
    status.classList.add("hidden");
  } catch (error) {
    status.classList.remove("hidden");
    status.classList.add("message-error");
    statusText.textContent = `Unable to load the feed: ${error.message}`;
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh Latest Papers";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("feed-form");
  const limitInput = document.getElementById("limit");
  if (!form || !limitInput) {
    return;
  }

  loadFeed(limitInput.value || "12");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadFeed(limitInput.value || "12");
  });
});
