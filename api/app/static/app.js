const form = document.getElementById("search-form");
const submitButton = document.getElementById("submit-button");
const statusPanel = document.getElementById("status-panel");
const summaryPanel = document.getElementById("summary-panel");
const resultsPanel = document.getElementById("results-panel");
const outlinePanel = document.getElementById("outline-panel");
const categorySelect = document.getElementById("category");
const queryUsed = document.getElementById("query-used");
const candidateCount = document.getElementById("candidate-count");
const acceptedCount = document.getElementById("accepted-count");
const workflowSteps = document.getElementById("workflow-steps");
const sanityReport = document.getElementById("sanity-report");
const agentCards = Array.from(document.querySelectorAll(".agent-card"));
const selectAllPapers = document.getElementById("select-all-papers");
const selectedCount = document.getElementById("selected-count");
const exportRisButton = document.getElementById("export-ris-button");
const exportXlsxButton = document.getElementById("export-xlsx-button");
const exportBar = document.querySelector(".export-bar");
let currentOutline = null;
const loadingPanel = document.getElementById("loading-panel");
const loadingLabel = document.getElementById("loading-label");
const loadingCaption = document.getElementById("loading-caption");
const loadingBar = document.getElementById("loading-bar");
const pdfFilesInput = document.getElementById("pdf-files");
const pdfFilesOrganizeInput = document.getElementById("pdf-files-organize");
const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));
const modePanels = Array.from(document.querySelectorAll("[data-mode-panel]"));
const modeDescriptions = Array.from(document.querySelectorAll("[data-mode-description]"));
const modeNote = document.getElementById("mode-note");
const topicInput = document.getElementById("topic");
const topicSection = document.getElementById("topic-section");
const organizeHeader = document.getElementById("organize-header");
const saveToZoteroSearch = document.getElementById("save-to-zotero-search");
const searchZoteroApiKeyWrapper = document.getElementById("search-zotero-api-key-wrapper");
const searchZoteroUsernameWrapper = document.getElementById("search-zotero-username-wrapper");
const searchZoteroApiKeyInput = document.getElementById("search-zotero-api-key");
const searchZoteroUsernameInput = document.getElementById("search-zotero-username");

let activeMode = "search";
let loadingTimer = null;

let currentPapers = [];
const selectedPaperIds = new Set();

function showStatus(message, isError = false) {
  statusPanel.textContent = message;
  statusPanel.classList.remove("hidden");
  statusPanel.classList.toggle("muted", !isError);
}

function startLoading(label, caption) {
  loadingLabel.textContent = label;
  loadingCaption.textContent = caption;
  loadingPanel.classList.remove("hidden");
  loadingBar.style.width = "14%";

  if (activeMode !== "zotero") {
    let progress = 14;
    window.clearInterval(loadingTimer);
    loadingTimer = window.setInterval(() => {
      progress = Math.min(progress + Math.random() * 10, 92);
      loadingBar.style.width = `${progress}%`;
    }, 420);
  }
}

function stopLoading() {
  window.clearInterval(loadingTimer);
  loadingTimer = null;
  loadingBar.style.width = "100%";
  window.setTimeout(() => {
    loadingPanel.classList.add("hidden");
    loadingBar.style.width = "0%";
  }, 220);
}

function csvToList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function populateCategorySelect() {
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All categories";
  categorySelect.appendChild(allOption);

  ARXIV_CATEGORIES.forEach((group) => {
    const optgroup = document.createElement("optgroup");
    optgroup.label = group.group;

    group.options.forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      optgroup.appendChild(option);
    });

    categorySelect.appendChild(optgroup);
  });
}

function setActiveMode(mode) {
  activeMode = mode;
  modeTabs.forEach((tab) => {
    const isActive = tab.dataset.mode === mode;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });

  modePanels.forEach((panel) => {
    const isActive = panel.dataset.modePanel === mode;
    panel.classList.toggle("hidden", !isActive);
    panel.classList.toggle("active", isActive);
  });
  modeDescriptions.forEach((description) => {
    description.classList.toggle("hidden", description.dataset.modeDescription !== mode);
  });

  topicInput.required = mode !== "organize";
  topicSection.classList.toggle("hidden", mode === "organize");
  organizeHeader.classList.toggle("hidden", mode !== "organize");
  if (mode === "upload") {
    submitButton.textContent = "Analyze PDFs";
    modeNote.textContent = "Upload + Analyze ignores arXiv filters and scores uploaded PDFs or Zotero RDF entries against the topic above.";
  } else if (mode === "organize") {
    submitButton.textContent = "Organize PDFs";
    modeNote.textContent = "Upload + Organize skips topic scoring, summarizes every uploaded PDF or Zotero RDF entry, and prepares everything for export.";
  } else if (mode === "zotero") {
    submitButton.textContent = "Fetch Zotero Library";
    modeNote.textContent = "Zotero API mode reads a personal library with your Zotero username and API key, then scores and summarizes those items against the topic above.";
  } else if (mode === "literature") {
    submitButton.textContent = "Build Outline";
    modeNote.textContent = "Literature Outline mode reads your Zotero library and asks the outline agent to synthesize a literature review structure with APA citations.";
  } else {
    submitButton.textContent = "Search";
    modeNote.textContent = "Search mode builds an arXiv query. You can optionally save accepted papers directly to Zotero.";
  }
}

function syncSearchZoteroFields() {
  const enabled = Boolean(saveToZoteroSearch?.checked);
  searchZoteroApiKeyWrapper.classList.toggle("hidden", !enabled);
  searchZoteroUsernameWrapper.classList.toggle("hidden", !enabled);
}

function buildApaCitation(paper) {
  const authors = formatApaAuthors(paper.authors || []);
  const year = paper.published ? paper.published.slice(0, 4) : "n.d.";
  const title = (paper.title || "").replace(/\.+$/, "");
  const source = (paper.paper_url || "").toLowerCase().includes("arxiv") || String(paper.id || "").toLowerCase().includes("arxiv")
    ? "arXiv"
    : "Zotero Library Source";
  const url = paper.paper_url || paper.pdf_url || "";
  return `${authors} (${year}). ${title}. ${source}.${url ? ` ${url}` : ""}`;
}

function formatPublishedDate(value) {
  if (!value) {
    return "Unknown date";
  }
  return /^\d{4}$/.test(value) ? `${value} (date unknown)` : value.slice(0, 10);
}

function formatApaAuthors(authors) {
  if (!authors.length) {
    return "Unknown author";
  }

  const formatted = authors.map(formatSingleAuthor);
  if (formatted.length === 1) {
    return formatted[0];
  }
  if (formatted.length <= 20) {
    return `${formatted.slice(0, -1).join(", ")}, & ${formatted.at(-1)}`;
  }
  return `${formatted.slice(0, 19).join(", ")}, ... ${formatted.at(-1)}`;
}

function formatSingleAuthor(author) {
  const parts = author.split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return author;
  }
  const lastName = parts.at(-1).replace(/,$/, "");
  const initials = parts.slice(0, -1).map((part) => `${part[0]}.`).join(" ");
  return `${lastName}, ${initials}`.trim();
}

function renderResults(data) {
  currentOutline = null;
  currentPapers = data.papers;
  selectedPaperIds.clear();
  queryUsed.textContent = data.query_used;
  candidateCount.textContent = String(data.total_candidates);
  acceptedCount.textContent = String(data.accepted_papers);
  workflowSteps.innerHTML = "";
  sanityReport.innerHTML = "";
  updateAgentCards(data.workflow_steps);

  data.workflow_steps.forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    workflowSteps.appendChild(item);
  });
  (data.sanity_report || []).forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    sanityReport.appendChild(item);
  });

  resultsPanel.innerHTML = "";
  if (!data.papers.length) {
    resultsPanel.innerHTML = '<section class="paper-card"><p>No papers passed the reviewer. Lower the fit score or include rejected papers.</p></section>';
  } else {
    data.papers.forEach((paper) => {
      const apaCitation = buildApaCitation(paper);
      const isOrganizedOnly = paper.is_fit && paper.fit_score === 0 && paper.relevance_score === 0;
      const scoreLabel = isOrganizedOnly
        ? "organized"
        : `${paper.is_fit ? "accepted" : "rejected"} · fit ${paper.fit_score.toFixed(1)}`;
      const baselineText = isOrganizedOnly
        ? "Topic scoring skipped for organization-only mode."
        : `Lexical baseline: ${paper.relevance_score.toFixed(3)} · ${paper.rationale}`;
      const article = document.createElement("article");
      article.className = `paper-card ${paper.is_fit ? "accepted" : "rejected"}`;
      article.innerHTML = `
        <label class="paper-select">
          <input type="checkbox" class="paper-checkbox" data-paper-id="${paper.id}" />
          <span>Select for export</span>
        </label>
        <div class="paper-top">
          <div>
            <h2>${paper.title}</h2>
            <p class="meta">
              <span>${paper.primary_category || "Unknown category"}</span>
              <span>${formatPublishedDate(paper.published)}</span>
              <span>${paper.authors.length ? paper.authors.join(", ") : "Unknown authors"}</span>
            </p>
          </div>
          <div class="score-panel">
            <div class="score-pill">${scoreLabel}</div>
            <details class="review-notes">
              <summary>View notes</summary>
              <p>${paper.reviewer_notes}</p>
            </details>
          </div>
        </div>
        <p>${paper.summary}</p>
        ${paper.key_points_summary ? `
          <div class="summary-box">
            <strong>Key points</strong>
            <ul>${paper.key_points_summary.map((point) => `<li>${point}</li>`).join("")}</ul>
          </div>
        ` : ""}
        <div class="citation-box">
          <strong>APA citation</strong>
          <p>${apaCitation}</p>
        </div>
        <p class="meta">${baselineText}</p>
        <p class="paper-links">
          ${paper.paper_url ? `<a href="${paper.paper_url}" target="_blank" rel="noreferrer">Abstract</a>` : ""}
          ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" rel="noreferrer">PDF</a>` : ""}
          ${!paper.paper_url && !paper.pdf_url ? `<span>Uploaded PDF source</span>` : ""}
        </p>
      `;
      resultsPanel.appendChild(article);
    });
  }

  wirePaperSelection();
  updateExportControls();
  exportBar.classList.remove("hidden");
  summaryPanel.classList.remove("hidden");
  resultsPanel.classList.remove("hidden");
  outlinePanel.classList.add("hidden");
}

function renderOutline(outline) {
  currentOutline = outline;
  currentPapers = [];
  selectedPaperIds.clear();
  queryUsed.textContent = outline.query_used;
  candidateCount.textContent = String(outline.total_candidates);
  acceptedCount.textContent = String(outline.accepted_papers);
  workflowSteps.innerHTML = "";
  sanityReport.innerHTML = "";
  updateAgentCards([...outline.workflow_steps, "outline_agent running"]);

  outline.workflow_steps.forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    workflowSteps.appendChild(item);
  });
  (outline.sanity_report || []).forEach((step) => {
    const item = document.createElement("li");
    item.textContent = step;
    sanityReport.appendChild(item);
  });

  resultsPanel.classList.add("hidden");
  exportBar.classList.add("hidden");
  outlinePanel.innerHTML = "";
  const wrapper = document.createElement("section");
  wrapper.className = "paper-card accepted";
  wrapper.innerHTML = `
    <div class="paper-top">
      <div>
        <h2>${outline.outline_title}</h2>
        <p class="meta">
          <span>${outline.accepted_papers} accepted sources</span>
          <span>${outline.total_candidates} candidates reviewed</span>
        </p>
      </div>
      <div class="score-panel">
        <button id="export-outline-docx-button" type="button" class="secondary-button">Export Word Outline</button>
      </div>
    </div>
    <div class="summary-box">
      <strong>Outline Sections</strong>
      ${outline.sections.map((section) => `
        <div class="outline-section">
          <h3>${section.title}</h3>
          <p>${section.overview}</p>
          <ul>${section.bullet_points.map((point) => `<li>${point}</li>`).join("")}</ul>
        </div>
      `).join("")}
    </div>
    <div class="citation-box">
      <strong>References</strong>
      <ul class="outline-bibliography">${outline.bibliography.map((citation) => `<li>${citation}</li>`).join("")}</ul>
    </div>
  `;
  outlinePanel.appendChild(wrapper);
  summaryPanel.classList.remove("hidden");
  outlinePanel.classList.remove("hidden");
  document.getElementById("export-outline-docx-button").addEventListener("click", async () => {
    try {
      await exportOutlineDocx(outline);
      showStatus("Exported literature review outline as Word.");
    } catch (error) {
      showStatus(error.message, true);
    }
  });
}

function buildCompletionMessage(data) {
  const base = `Finished. Accepted ${data.accepted_papers} of ${data.total_candidates} candidates.`;
  const parts = [base];
  if (data.zotero_saved_items > 0) {
    parts.push(`Saved ${data.zotero_saved_items} accepted paper(s) to Zotero.`);
  }
  if (data.zotero_deleted_items > 0) {
    parts.push(`Deleted ${data.zotero_deleted_items} Zotero item(s).`);
  }
  return parts.join(" ");
}

function updateAgentCards(steps = []) {
  const stepText = steps.join(" ").toLowerCase();
  agentCards.forEach((card) => {
    const agent = card.dataset.agent;
    const matched =
      (agent === "search" && stepText.includes("search_agent")) ||
      (agent === "review" && stepText.includes("review_agent")) ||
      (agent === "summary" && stepText.includes("summary_agent")) ||
      (agent === "sanity" && stepText.includes("sanity_agent")) ||
      (agent === "outline" && stepText.includes("outline_agent"));
    card.classList.toggle("active", matched);
  });
}

function wirePaperSelection() {
  const checkboxes = Array.from(document.querySelectorAll(".paper-checkbox"));
  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        selectedPaperIds.add(checkbox.dataset.paperId);
      } else {
        selectedPaperIds.delete(checkbox.dataset.paperId);
      }
      updateExportControls();
    });
  });

  selectAllPapers.checked = false;
}

function updateExportControls() {
  const visibleCount = currentPapers.length;
  const selected = currentPapers.filter((paper) => selectedPaperIds.has(paper.id));
  const allSelected = visibleCount > 0 && selected.length === visibleCount;
  selectAllPapers.checked = allSelected;
  selectedCount.textContent = `${selected.length} selected`;
  exportRisButton.disabled = selected.length === 0;
  exportXlsxButton.disabled = selected.length === 0;
}

async function fetchUploadedPapers(payload, uploadedFiles) {
  const formData = new FormData();
  formData.append("topic", payload.topic);
  formData.append("min_fit_score", String(payload.min_fit_score));
  formData.append("include_rejected", String(payload.include_rejected));
  uploadedFiles.forEach((file) => formData.append("files", file));

  return fetch("/papers/upload", {
    method: "POST",
    body: formData,
  });
}

async function fetchOrganizedPapers(uploadedFiles) {
  const formData = new FormData();
  uploadedFiles.forEach((file) => formData.append("files", file));

  return fetch("/papers/upload/organize", {
    method: "POST",
    body: formData,
  });
}

async function fetchZoteroPapers(payload) {
  const formData = new FormData();
  formData.append("topic", payload.topic);
  formData.append("username", payload.username);
  formData.append("api_key", payload.api_key);
  formData.append("min_fit_score", String(payload.min_fit_score));
  formData.append("include_rejected", String(payload.include_rejected));
  formData.append("max_items", String(payload.max_items));
  formData.append("delete_below_score", String(payload.delete_below_score));
  formData.append("delete_duplicates", String(payload.delete_duplicates));

  return fetch("/papers/zotero", {
    method: "POST",
    body: formData,
  });
}

async function startZoteroJob(payload) {
  const formData = new FormData();
  formData.append("topic", payload.topic);
  formData.append("username", payload.username);
  formData.append("api_key", payload.api_key);
  formData.append("min_fit_score", String(payload.min_fit_score));
  formData.append("include_rejected", String(payload.include_rejected));
  formData.append("max_items", String(payload.max_items));
  formData.append("delete_below_score", String(payload.delete_below_score));
  formData.append("delete_duplicates", String(payload.delete_duplicates));

  return fetch("/papers/zotero/jobs", {
    method: "POST",
    body: formData,
  });
}

async function pollZoteroJob(jobId) {
  while (true) {
    const response = await fetch(`/papers/zotero/jobs/${jobId}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Zotero job failed");
    }

    loadingBar.style.width = `${Math.max(0, Math.min(100, data.progress || 0))}%`;
    loadingCaption.textContent = data.message || "Working...";

    if (data.status === "completed") {
      loadingBar.style.width = "100%";
      return data.result;
    }
    if (data.status === "failed") {
      throw new Error(data.error || data.message || "Zotero job failed");
    }

    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}

async function exportSelected(format) {
  const papers = currentPapers.filter((paper) => selectedPaperIds.has(paper.id));
  if (!papers.length) {
    showStatus("Select at least one paper to export.", true);
    return;
  }

  const endpoint = format === "ris" ? "/exports/ris" : "/exports/xlsx";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ papers }),
  });

  if (!response.ok) {
    let message = "Export failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // ignore JSON parsing failure
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const match = contentDisposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `papers.${format === "ris" ? "ris" : "xlsx"}`;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function exportOutlineDocx(outline) {
  const response = await fetch("/exports/literature-review/docx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outline }),
  });
  if (!response.ok) {
    let message = "Outline export failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // ignore JSON parsing failure
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const contentDisposition = response.headers.get("Content-Disposition") || "";
  const match = contentDisposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "literature-review-outline.docx";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  let payload;
  if (activeMode === "upload") {
    payload = {
      topic: topicInput.value.trim(),
      min_fit_score: Number(document.getElementById("min-fit-score-upload").value || 2),
      include_rejected: document.getElementById("include-rejected-upload").checked,
    };
  } else if (activeMode === "organize") {
    payload = {
      topic: "",
    };
  } else if (activeMode === "zotero") {
    payload = {
      topic: topicInput.value.trim(),
      username: document.getElementById("zotero-username").value.trim(),
      api_key: document.getElementById("zotero-api-key").value.trim(),
      min_fit_score: Number(document.getElementById("min-fit-score-zotero").value || 2),
      include_rejected: document.getElementById("include-rejected-zotero").checked,
      max_items: Number(document.getElementById("zotero-max-items").value || 100),
      delete_below_score: document.getElementById("delete-below-score-zotero").checked,
      delete_duplicates: document.getElementById("delete-duplicates-zotero").checked,
    };
  } else if (activeMode === "literature") {
    payload = {
      topic: topicInput.value.trim(),
      username: document.getElementById("literature-zotero-username").value.trim(),
      api_key: document.getElementById("literature-zotero-api-key").value.trim(),
      min_fit_score: Number(document.getElementById("literature-min-fit-score").value || 2),
      include_rejected: document.getElementById("literature-include-rejected").checked,
      max_items: Number(document.getElementById("literature-zotero-max-items").value || 100),
    };
  } else {
    payload = {
      topic: topicInput.value.trim(),
      categories: categorySelect.value ? [categorySelect.value] : [],
      include_terms: csvToList(document.getElementById("include-terms").value),
      exclude_terms: csvToList(document.getElementById("exclude-terms").value),
      max_results: Number(document.getElementById("max-results").value || 5),
      min_fit_score: Number(document.getElementById("min-fit-score-search").value || 2),
      include_rejected: document.getElementById("include-rejected-search").checked,
      save_to_zotero: saveToZoteroSearch.checked,
      zotero_api_key: searchZoteroApiKeyInput.value.trim(),
      zotero_username: searchZoteroUsernameInput.value.trim(),
    };
  }
  const uploadedFiles = activeMode === "organize"
    ? Array.from(pdfFilesOrganizeInput.files || [])
    : Array.from(pdfFilesInput.files || []);

  if (!payload.topic) {
    if (activeMode === "search" || activeMode === "upload") {
      showStatus("Enter a topic before searching.", true);
      return;
    }
  }
  if (activeMode === "organize" && uploadedFiles.length === 0) {
    showStatus("Select at least one PDF or Zotero RDF file before organizing uploads.", true);
    return;
  }
  if (activeMode === "upload" && uploadedFiles.length === 0) {
    showStatus("Select at least one PDF or Zotero RDF file before analyzing uploads.", true);
    return;
  }
  if (activeMode === "zotero" && (!payload.username || !payload.api_key)) {
    showStatus("Enter both a Zotero username and API key before fetching the library.", true);
    return;
  }
  if (activeMode === "literature" && (!payload.username || !payload.api_key)) {
    showStatus("Enter both a Zotero username and API key before building the literature outline.", true);
    return;
  }
  if (activeMode === "search" && payload.save_to_zotero && !payload.zotero_api_key) {
    showStatus("Enter a write-enabled Zotero API key to save accepted papers.", true);
    return;
  }

  submitButton.disabled = true;
  const loadingCaptionText = activeMode === "zotero"
    ? payload.delete_below_score || payload.delete_duplicates
      ? `Reading up to ${payload.max_items} Zotero library item(s), reviewing fit, drafting bullet summaries, auditing the workflow, and pruning selected items.`
      : `Reading up to ${payload.max_items} Zotero library item(s), reviewing fit, drafting bullet summaries, and running a sanity audit.`
    : activeMode === "literature"
      ? `Reading up to ${payload.max_items} Zotero library item(s), screening relevance, and drafting a literature review outline.`
    : activeMode === "organize"
      ? `Reading ${uploadedFiles.length} uploaded file(s), generating bullet summaries, and running a sanity audit.`
      : activeMode === "upload"
        ? `Reading ${uploadedFiles.length} uploaded file(s), reviewing fit, summarizing, and running a sanity audit.`
        : payload.save_to_zotero
          ? "Planning the query, reviewing candidate fit, summarizing accepted papers, auditing the workflow, and saving accepted papers to Zotero."
          : "Planning the query, reviewing candidate fit, summarizing accepted papers, and running a sanity audit.";
  startLoading("Agents Running", loadingCaptionText);
  showStatus(
    activeMode === "zotero"
      ? payload.delete_below_score || payload.delete_duplicates
        ? `Agents are reading up to ${payload.max_items} Zotero library item(s), reviewing fit, summarizing them, auditing the workflow, and pruning selected items...`
        : `Agents are reading up to ${payload.max_items} Zotero library item(s), reviewing fit, summarizing them, and auditing the workflow...`
      : activeMode === "literature"
        ? `Agents are reading up to ${payload.max_items} Zotero library item(s), screening relevance, and drafting a literature review outline...`
      : activeMode === "organize"
      ? `Agents are reading ${uploadedFiles.length} uploaded file(s), summarizing them, and auditing the workflow...`
      : activeMode === "upload"
      ? `Agents are reading ${uploadedFiles.length} uploaded file(s), reviewing fit, summarizing references, and auditing the workflow...`
      : payload.save_to_zotero
        ? "Agents are planning the query, reviewing fit, summarizing full papers, auditing the workflow, and saving accepted papers to Zotero..."
        : "Agents are planning the query, reviewing fit, summarizing full papers, and auditing the workflow..."
  );
  summaryPanel.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  outlinePanel.classList.add("hidden");
  selectedPaperIds.clear();
  currentPapers = [];
  currentOutline = null;
  updateAgentCards([
    "search_agent running",
    "review_agent running",
    "summary_agent running",
    "sanity_agent running",
    ...(activeMode === "literature" ? ["outline_agent running"] : []),
  ]);

  try {
    if (activeMode === "zotero") {
      const jobResponse = await startZoteroJob(payload);
      const jobData = await jobResponse.json();
      if (!jobResponse.ok) {
        throw new Error(jobData.detail || "Failed to start Zotero job");
      }

      const result = await pollZoteroJob(jobData.job_id);
      showStatus(buildCompletionMessage(result));
      renderResults(result);
      return;
    }
    if (activeMode === "literature") {
      const response = await fetch("/papers/zotero/outline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Literature outline generation failed");
      }
      showStatus(`Finished. Built literature outline from ${data.accepted_papers} accepted source(s).`);
      renderOutline(data);
      return;
    }

    const response = activeMode === "organize"
        ? await fetchOrganizedPapers(uploadedFiles)
        : activeMode === "upload"
          ? await fetchUploadedPapers(payload, uploadedFiles)
          : await fetch("/papers/discover", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Search failed");
    }

    showStatus(buildCompletionMessage(data));
    renderResults(data);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    stopLoading();
    submitButton.disabled = false;
  }
});

modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setActiveMode(tab.dataset.mode);
  });
});

selectAllPapers.addEventListener("change", () => {
  const checked = selectAllPapers.checked;
  document.querySelectorAll(".paper-checkbox").forEach((checkbox) => {
    checkbox.checked = checked;
    if (checked) {
      selectedPaperIds.add(checkbox.dataset.paperId);
    } else {
      selectedPaperIds.delete(checkbox.dataset.paperId);
    }
  });
  updateExportControls();
});

exportRisButton.addEventListener("click", async () => {
  try {
    await exportSelected("ris");
    showStatus(`Exported ${selectedPaperIds.size} paper(s) as RIS.`);
  } catch (error) {
    showStatus(error.message, true);
  }
});

exportXlsxButton.addEventListener("click", async () => {
  try {
    await exportSelected("xlsx");
    showStatus(`Exported ${selectedPaperIds.size} paper(s) as Excel.`);
  } catch (error) {
    showStatus(error.message, true);
  }
});

populateCategorySelect();
setActiveMode("search");
syncSearchZoteroFields();
saveToZoteroSearch.addEventListener("change", syncSearchZoteroFields);
