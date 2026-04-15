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

function isWeakQuery(text) {
  const clean = text.trim().toLowerCase();
  const greetings = ["hi", "hello", "hey", "thanks", "ok", "okay", "test", "?"];
  if (greetings.includes(clean)) return true;
  if (clean.split(/\s+/).filter(w => w.length > 1).length < 2) return true;
  return false;
}

function scoreLabel(score) {
  if (score >= 0.55) return { icon: "✅", text: "Strong match", cls: "signal-strong" };
  if (score >= 0.35) return { icon: "⚠️", text: "Possible match", cls: "signal-weak" };
  return null;
}

function buildMatchSummary(match, question) {
  const sectors = (match.sectors || []).slice(0, 2).join(" & ");
  const role = match.role === "session" ? "event" : "profile";
  if (sectors) return `Matches your interest in ${sectors}`;
  if (match.score >= 0.55) return `Strong ${role} match for your query`;
  return `May relate to your search`;
}

function renderCard(match, index) {
  const confidence = scoreLabel(match.score);
  if (!confidence) return "";  // hide low-confidence results entirely
  const summary = buildMatchSummary(match, "");
  const location = match.organization || "";
  const tags = (match.sectors || []).slice(0, 3);
  return `
    <article class="result-item">
      <h3>#${index + 1} ${escapeHtml(match.name)}</h3>
      <p class="result-meta-line">📍 ${escapeHtml(location)} · <span class="role-badge">${escapeHtml(match.role)}</span></p>
      ${tags.length ? `<div class="result-meta">${tags.map(s => `<span class="mini-pill">🏷 ${escapeHtml(s)}</span>`).join("")}</div>` : ""}
      <p class="result-summary ${confidence.cls}">${confidence.icon} ${escapeHtml(summary)}</p>
    </article>
  `;
}

function renderGroup(title, icon, items) {
  const cards = items.map((m, i) => renderCard(m, i)).filter(Boolean);
  if (!cards.length) return "";
  return `
    <div class="result-group">
      <p class="result-group-title">${icon} ${escapeHtml(title)} (${cards.length})</p>
      ${cards.join("")}
    </div>
  `;
}

function renderMatches(question, payload) {
  if (isWeakQuery(question)) {
    return `
      <p class="message-title">Blockie AI</p>
      <p>Not sure what you're looking for yet 👀</p>
      <p class="result-suggestions-hint">Try searching for something specific, for example:</p>
      <ul class="query-suggestions">
        <li>AI and machine learning sessions</li>
        <li>Networking events</li>
        <li>People in healthcare or biotech</li>
        <li>Climate change conferences</li>
      </ul>
    `;
  }

  const matches = payload.matches || [];
  const sessions = matches.filter(m => m.entity_type === "resource" || m.role === "session").slice(0, 4);
  const people   = matches.filter(m => m.entity_type === "person"   || m.role === "participant").slice(0, 2);

  const sessionHtml = renderGroup("Sessions & Events", "🎯", sessions);
  const peopleHtml  = renderGroup("Related People", "👥", people);

  if (!sessionHtml && !peopleHtml) {
    return `
      <p class="message-title">Blockie AI</p>
      <p>No strong matches found for "<strong>${escapeHtml(question)}</strong>".</p>
      <p>Try a more specific topic like <em>AI sessions</em> or <em>climate networking</em>.</p>
    `;
  }

  return `
    <p class="message-title">Blockie AI</p>
    <p>Top results for "<strong>${escapeHtml(question)}</strong>".</p>
    ${sessionHtml}
    ${peopleHtml}
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
