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

/** Single-conference (GTC) product: matching is people-only; agenda words refine the query. */
function detectGoals() {
  return { intent: "people", looking_for: ["peers"], target_roles: ["participant"] };
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
    ["llm", "artificial intelligence"],
    ["llms", "artificial intelligence"],
    ["cuda", "developer tools"],
    ["robotics", "robotics"],
    ["edge ai", "artificial intelligence"],
    ["autonomous", "artificial intelligence"],
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
  const inferred = detectGoals();
  return {
    role: "participant",
    stage: "all",
    looking_for: inferred.looking_for,
    target_roles: inferred.target_roles,
    search_intent: "people",
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
  if (score >= 0.55) return { icon: "✅", cls: "signal-strong" };
  if (score >= 0.35) return { icon: "⚠️", cls: "signal-weak" };
  // Always show a card: hybrid scores are often < 0.35 even for good relative matches.
  return { icon: "·", cls: "signal-low" };
}

function queryTokens(question) {
  return new Set(
    question
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((token) => token.length >= 4)
  );
}

function eventOverlap(events, question) {
  if (!events.length) return [];
  const tokens = queryTokens(question);
  if (!tokens.size) return [];
  return events.filter((eventName) =>
    eventName
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .some((token) => token.length >= 4 && tokens.has(token))
  );
}

function buildCardContent(match, question) {
  const sectors = (match.sectors || []).slice(0, 2);
  const topSector = sectors[0] || "your search";
  const events = (match.source_events || []).slice(0, 4);
  const overlappingEvents = eventOverlap(events, question).slice(0, 2);
  const eventLabel = overlappingEvents.length
    ? overlappingEvents.join(" + ")
    : (events[0] || null);
  const org = match.organization && match.organization !== "Example" ? match.organization : null;
  const why = eventLabel
    ? `Activity overlap: ${eventLabel}`
    : (org ? `Profile overlap: ${topSector} · ${org}` : `Interests and profile align with ${topSector}`);

  const profileContext = match.title
    ? `Professional fit: ${topSector} · ${match.title}`
    : `Professional fit: ${topSector}`;

  const bullets = [profileContext];

  const actionHint = "";
  return { why, bullets, actionHint, badges: [] };
}

function renderCard(match, index, question) {
  const confidence = scoreLabel(match.score);
  const { why, bullets, actionHint, badges } = buildCardContent(match, question);
  const personalizedTags = [
    ...(match.asks || []),
    ...(match.tags || []),
    ...(match.offers || [])
  ]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  const tags = [...new Set(personalizedTags)].slice(0, 3);
  const headlineRole = (match.title && match.title.trim()) || (match.role && match.role.trim()) || "Attendee";
  return `
    <article class="result-item">
      <h3>#${index + 1} ${escapeHtml(match.name)}</h3>
      <p class="result-meta-line">💼 ${escapeHtml(headlineRole)}</p>
      ${tags.length ? `<div class="result-meta">${tags.map(s => `<span class="mini-pill">🏷 ${escapeHtml(s)}</span>`).join("")}</div>` : ""}
      ${badges.length ? `<div class="result-badges">${badges.map(b => `<span class="meta-badge">${escapeHtml(b)}</span>`).join("")}</div>` : ""}
      <p class="result-summary ${confidence.cls}">🎯 ${escapeHtml(why)}</p>
      ${bullets.length ? `<ul class="result-bullets">${bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul>` : ""}
      ${actionHint ? `<p class="result-action-hint">${escapeHtml(actionHint)}</p>` : ""}
      ${
        match.llm_reason
          ? `<p class="llm-reason-text"><strong>Why connect with this person</strong> · ${escapeHtml(match.llm_reason)}</p>`
          : ""
      }
    </article>
  `;
}

function renderGroup(title, icon, items, question) {
  const cards = items.map((m, i) => renderCard(m, i, question)).filter(Boolean);
  if (!cards.length) return "";
  return `
    <div class="result-group">
      <p class="result-group-title">${icon} ${escapeHtml(title)} (${cards.length})</p>
      ${cards.join("")}
    </div>
  `;
}

function isPeopleMatch(m) {
  return (
    m.entity_type === "attendee" ||
    m.entity_type === "person" ||
    (m.role === "participant" && m.entity_type !== "resource")
  );
}

function renderMatches(question, payload) {
  if (isWeakQuery(question)) {
    return `
      <p class="message-title">Blockie</p>
      <p>Not sure what you're looking for yet 👀</p>
      <p class="result-suggestions-hint">Try something concrete, for example:</p>
      <ul class="query-suggestions">
        <li>Who works on CUDA or LLM inference</li>
        <li>Attendees into robotics or edge AI</li>
        <li>People who picked keynote + healthcare sessions</li>
        <li>PhDs in CS who list simulation interests</li>
      </ul>
    `;
  }

  const matches = (payload.matches || []).filter(isPeopleMatch).slice(0, 12);
  const peopleHtml = renderGroup("People", "👥", matches, question);

  if (!peopleHtml) {
    return `
      <p class="message-title">Blockie</p>
      <p>No strong people matches for "<strong>${escapeHtml(question)}</strong>".</p>
      <p>Try <em>CUDA</em>, <em>LLMs</em>, <em>robotics</em>, a job title, or an agenda phrase people put in their profile.</p>
    `;
  }

  return `
    <p class="message-title">Blockie</p>
    <p class="intent-banner">👥 <strong>Recommended people to meet at GTC</strong></p>
    <p>Prioritized by interest alignment, role fit, and agenda overlap.</p>
    ${peopleHtml}
  `;
}

async function runMatch(question) {
  const payload = buildRequest(question);
  const loadingNode = addMessage(
    "assistant",
    `<p class="message-title">Blockie</p><p>Searching attendee profiles…</p>`
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
      `<p class="message-title">Blockie</p><p>I could not run that search right now. ${escapeHtml(error.message)}</p>`
    );
  }
}

function hydrateConference(options) {
  conferenceOptions = options;
  const conference = options.conference || {};
  conferenceName.textContent = conference.name || "GTC roster";
  datasetText.textContent =
    conference.description ||
    "People-only matching; registered sessions appear as text in each profile.";
  eventCount.textContent = formatNumber(Math.max(1, conference.event_count || 1));
  attendeeCount.textContent = formatNumber(conference.attendee_count);
  rowCount.textContent = formatNumber(conference.raw_row_count);

  welcomeText.textContent = `Hi — ${formatNumber(conference.attendee_count)} attendees on file for this conference (source rows: ${formatNumber(conference.raw_row_count)}). Ask who to meet by interests, role, major, or agenda keywords.`;
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
