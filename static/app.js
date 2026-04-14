const chatForm = document.querySelector("#chatForm");
const questionInput = document.querySelector("#questionInput");
const conversation = document.querySelector("#conversation");
const suggestionRow = document.querySelector("#suggestionRow");
const welcomeText = document.querySelector("#welcomeText");
const conferenceName = document.querySelector("#conferenceName");
const datasetText = document.querySelector("#datasetText");
const eventCount = document.querySelector("#eventCount");
const attendeeCount = document.querySelector("#attendeeCount");
const rowCount = document.querySelector("#rowCount");
const sendButton = chatForm.querySelector(".send-button");

let conferenceOptions = null;

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(Number(value || 0));
}

function scrollConversationToBottom() {
  conversation.scrollTop = conversation.scrollHeight;
}

function addMessage(kind, innerHtml) {
  const article = document.createElement("article");
  article.className = `message ${kind}`;
  article.innerHTML = `
    <div class="avatar">${kind === "assistant" ? "AI" : "You"}</div>
    <div class="bubble">${innerHtml}</div>
  `;
  conversation.appendChild(article);
  scrollConversationToBottom();
  return article;
}

function detectGoals(question) {
  const text = question.toLowerCase();
  if (text.includes("session") || text.includes("event") || text.includes("schedule")) {
    return { looking_for: ["sessions"], target_roles: ["session"] };
  }
  if (
    text.includes("attendee") ||
    text.includes("people") ||
    text.includes("person") ||
    text.includes("who") ||
    text.includes("peer")
  ) {
    return { looking_for: ["peers"], target_roles: ["participant"] };
  }
  return { looking_for: ["sessions", "peers"], target_roles: ["session", "participant"] };
}

function detectSectors(question) {
  const text = question.toLowerCase();
  const sectors = [];
  const checks = [
    ["health tech", "healthcare"],
    ["health tech", "artificial intelligence"],
    ["healthtech", "healthcare"],
    ["medtech", "healthcare"],
    ["biotech", "healthcare"],
    ["ai", "artificial intelligence"],
    ["machine learning", "artificial intelligence"],
    ["health", "healthcare"],
    ["medical", "healthcare"],
    ["climate", "climate"],
    ["sustainability", "climate"],
    ["community", "community"],
    ["network", "community"],
    ["customer", "customer discovery"],
    ["startup", "entrepreneurship"],
    ["founder", "entrepreneurship"],
    ["invest", "fundraising"]
  ];
  checks.forEach(([needle, sector]) => {
    if (text.includes(needle)) {
      sectors.push(sector);
    }
  });
  return [...new Set(sectors)];
}

function buildRequest(question) {
  const inferred = detectGoals(question);
  return {
    role: "participant",
    stage: "all",
    looking_for: inferred.looking_for,
    target_roles: inferred.target_roles,
    sectors: detectSectors(question),
    asks: question,
    notes: question
  };
}

function renderMatches(question, payload) {
  const matches = payload.matches || [];
  if (!matches.length) {
    return `
      <p class="message-title">Blockie AI</p>
      <p>No relevant matches were found for “${escapeHtml(question)}”. Try a simpler topic or mention a known event theme.</p>
    `;
  }

  const topMatches = matches.slice(0, 4);
  return `
    <p class="message-title">Blockie AI</p>
    <p>Here are the strongest matches I found for “${escapeHtml(question)}”.</p>
    <div class="result-stack">
      ${topMatches
        .map(
          (match, index) => `
            <article class="result-item">
              <h3>#${index + 1} ${escapeHtml(match.name)}</h3>
              <p>${escapeHtml(match.title)} at ${escapeHtml(match.organization)} · ${escapeHtml(match.role)}</p>
              <div class="result-meta">
                ${(match.sectors || []).slice(0, 2).map((sector) => `<span class="mini-pill">${escapeHtml(sector)}</span>`).join("")}
              </div>
              <p>${escapeHtml((match.explanation && match.explanation[0]) || match.bio || "")}</p>
              ${match.llm_reason ? `<p class="llm-reason"><span class="llm-badge">&#x1F916; llama3</span> ${escapeHtml(match.llm_reason)}</p>` : ""}
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

async function runMatch(question) {
  const payload = buildRequest(question);
  const loadingNode = addMessage(
    "assistant",
    `<p class="message-title">Blockie AI</p><p>Searching the imported conference data...</p>`
  );

  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    const data = await response.json();
    loadingNode.remove();
    addMessage("assistant", renderMatches(question, data));
  } catch (error) {
    loadingNode.remove();
    addMessage(
      "assistant",
      `<p class="message-title">Blockie AI</p><p>I could not run that search right now. ${escapeHtml(error.message)}</p>`
    );
  }
}

function hydrateConference(options) {
  conferenceOptions = options;
  const conference = options.conference || {};
  conferenceName.textContent = conference.name || "Imported attendance dataset";
  datasetText.textContent =
    conference.description || "Imported attendee and session records are ready for search.";
  eventCount.textContent = formatNumber(conference.event_count);
  attendeeCount.textContent = formatNumber(conference.attendee_count);
  rowCount.textContent = formatNumber(conference.raw_row_count);

  welcomeText.textContent = `Hi, I can search ${formatNumber(conference.attendee_count)} attendees and ${formatNumber(conference.event_count)} events from your imported attendance dataset.`;
}

async function init() {
  const response = await fetch("/api/conference");
  const options = await response.json();
  hydrateConference(options);
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    return;
  }
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  questionInput.value = "";
  await runMatch(question);
});

suggestionRow.addEventListener("click", async (event) => {
  const button = event.target.closest(".suggestion-chip");
  if (!button) {
    return;
  }
  const question = button.dataset.query;
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  await runMatch(question);
});

init();
