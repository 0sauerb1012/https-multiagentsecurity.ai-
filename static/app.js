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

function initFeed() {
  const results = document.getElementById("feed-results");
  if (!results) {
    return;
  }

  const defaultLimit = results.dataset.defaultLimit || "12";
  loadFeed(defaultLimit);

  const form = document.getElementById("feed-form");
  const limitInput = document.getElementById("limit");
  if (form && limitInput) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      loadFeed(limitInput.value || defaultLimit);
    });
  }
}

function initAreaExportSelection() {
  const selectAll = document.getElementById("select-all-papers");
  const clearAll = document.getElementById("clear-all-papers");
  const selectedCount = document.getElementById("selected-paper-count");
  const checkboxes = Array.from(document.querySelectorAll(".paper-select-input"));
  if (!selectAll || !clearAll || !selectedCount || checkboxes.length === 0) {
    return;
  }

  const syncState = () => {
    const checked = checkboxes.filter((input) => input.checked).length;
    selectedCount.textContent = String(checked);
  };

  selectAll.addEventListener("click", () => {
    checkboxes.forEach((input) => {
      input.checked = true;
    });
    syncState();
  });

  clearAll.addEventListener("click", () => {
    checkboxes.forEach((input) => {
      input.checked = false;
    });
    syncState();
  });

  checkboxes.forEach((input) => {
    input.addEventListener("change", syncState);
  });

  syncState();
}

document.addEventListener("DOMContentLoaded", () => {
  initFeed();
  initAreaExportSelection();
});
