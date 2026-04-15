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
  if (score >= 0.55) return { icon: "✅", cls: "signal-strong" };
  if (score >= 0.35) return { icon: "⚠️", cls: "signal-weak" };
  return null;
}

function extractEventMeta(name, bio) {
  const n = name.toLowerCase();
  const level =
    n.includes("advanced") || n.includes("expert") ? "Advanced" :
    n.includes("intermediate") ? "Intermediate" :
    (n.includes("beginner") || n.includes("fundamental") || n.includes("basic") || n.includes("intro")) ? "Beginner-friendly" : null;

  const type =
    n.includes("workshop") ? "Workshop 🛠" :
    n.includes("summit")   ? "Summit 🏔" :
    n.includes("seminar")  ? "Seminar 📖" :
    n.includes("hackathon")? "Hackathon 💻" :
    n.includes("panel")    ? "Panel 🎙" :
    n.includes("forum")    ? "Forum 💬" :
    n.includes("conference")? "Conference 🎤" : "Session";

  const attendeeMatch = (bio || "").match(/records (\d[\d,]*) attendee/);
  const attendeeCount = attendeeMatch ? parseInt(attendeeMatch[1].replace(/,/g, "")) : null;

  const focusWords = ["profit-focused","revenue","demand-driven","reactive","strategic","collaborative","applied","enterprise","global","practical","hands-on","real-time"];
  const adjectives = focusWords.filter(w => n.includes(w));

  return { level, type, attendeeCount, adjectives };
}

function buildCardContent(match, index) {
  const role = match.role;
  const sectors = (match.sectors || []).slice(0, 2);
  const topSector = sectors[0] || "this topic";

  if (role === "session" || match.entity_type === "resource") {
    const meta = extractEventMeta(match.name || "", match.bio || "");
    
    // 1. Shorter decision signal
    let why = `Best if you want hands-on experience`;
    if (meta.adjectives.includes("profit-focused") || meta.adjectives.includes("revenue"))
      why = `Best for: ${topSector} + business impact`;
    else if (meta.adjectives.includes("demand-driven") || meta.adjectives.includes("reactive") || meta.adjectives.includes("real-time"))
      why = `Best for: backend / systems engineers`;
    else if (meta.adjectives.includes("enterprise") || meta.adjectives.includes("global"))
      why = `Best for: enterprise leaders`;
    else if (meta.type && meta.type.startsWith("Workshop"))
      why = `Best for: practical, hands-on learning`;
    else
      why = `Best for: exploring ${topSector}`;

    // 2. Value preview
    const bullets = [];
    if (meta.adjectives.includes("profit-focused") || meta.adjectives.includes("revenue"))
      bullets.push("How companies use AI to drive revenue", "Real-world strategic case studies");
    else if (meta.adjectives.includes("demand-driven") || meta.adjectives.includes("real-time"))
      bullets.push("Real-time system design patterns", "Handling demand-driven workloads");
    else if (meta.type && meta.type.startsWith("Workshop"))
      bullets.push("Step-by-step practical implementation", "Interactive problem solving");
    else
      bullets.push(`Core insights on ${topSector}`, "Industry networking opportunities");

    // 3. Action Hint
    let actionHint = "";
    if (index === 0) actionHint = "⭐ Good pick if you only attend one session";
    else if (meta.type && meta.type.startsWith("Workshop")) actionHint = "👉 Worth attending if you want hands-on practice";
    else actionHint = "👉 Add to your schedule for broad exposure";

    const badges = [];
    if (meta.level)        badges.push(`📊 ${meta.level}`);
    if (meta.type)         badges.push(`🎤 ${meta.type.replace(/ .$/, "")}`);
    if (meta.attendeeCount && meta.attendeeCount >= 500)
      badges.push(`🔥 ${meta.attendeeCount.toLocaleString()} attendees`);

    return { why, bullets, actionHint, badges };
  } else {
    // People card
    const org = match.organization && match.organization !== "Example" ? match.organization : null;
    const why = org
      ? `Works on ${topSector} at ${org}`
      : `Attending similar ${topSector} sessions`;
      
    let eventContext = `Great to discuss real developments in ${topSector}`;
    if (match.bio && match.bio.includes("registered for")) {
      eventContext = `🤝 Also attending sessions related to your search`;
    }

    const bullets = [
      eventContext,
      `Potential peer for technical or strategic discussions`
    ];
    
    const actionHint = "👉 Good person to reach out to for networking";
    return { why, bullets, actionHint, badges: [] };
  }
}

function renderCard(match, index) {
  const confidence = scoreLabel(match.score);
  if (!confidence) return "";
  const { why, bullets, actionHint, badges } = buildCardContent(match, index);
  const tags = (match.sectors || []).slice(0, 3);
  return `
    <article class="result-item">
      <h3>#${index + 1} ${escapeHtml(match.name)}</h3>
      <p class="result-meta-line">📍 ${escapeHtml(match.organization || "")} · <span class="role-badge">${escapeHtml(match.role)}</span></p>
      ${tags.length ? `<div class="result-meta">${tags.map(s => `<span class="mini-pill">🏷 ${escapeHtml(s)}</span>`).join("")}</div>` : ""}
      ${badges.length ? `<div class="result-badges">${badges.map(b => `<span class="meta-badge">${escapeHtml(b)}</span>`).join("")}</div>` : ""}
      <p class="result-summary ${confidence.cls}">🎯 ${escapeHtml(why)}</p>
      ${bullets.length ? `<ul class="result-bullets">${bullets.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul>` : ""}
      ${actionHint ? `<p class="result-action-hint">${escapeHtml(actionHint)}</p>` : ""}
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
