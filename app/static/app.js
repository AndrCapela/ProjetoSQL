(() => {
  "use strict";

  const STORAGE_SOLVED_KEY = "sql_arena_solved_ids";
  const STORAGE_THEME_KEY = "sql_arena_theme";
  const STORAGE_HISTORY_KEY = "sql_arena_query_history";
  const STORAGE_DRAFTS_KEY = "sql_arena_drafts";

  const LEVEL_LABELS = {
    facil: "Fácil",
    medio: "Médio",
    dificil: "Difícil",
  };

  function storageGetJson(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  }

  function storageSet(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Ignora indisponibilidade de storage em modo privado restrito
    }
  }

  const state = {
    mode: "challenge", // "challenge" | "free"
    level: "facil",
    topic: "ALL",
    schema: [],
    challenges: [],
    currentChallenge: null,
    solvedIds: new Set(storageGetJson(STORAGE_SOLVED_KEY, [])),
    history: storageGetJson(STORAGE_HISTORY_KEY, []),
    drafts: storageGetJson(STORAGE_DRAFTS_KEY, {}),
    lastExpectedSql: "",
    expectedSqlRevealed: false,
    tables: {
      user: createTableState(),
      expected: createTableState(),
    },
    browser: {
      table: "alunos",
      page: 1,
      pageSize: 15,
      search: "",
      sortBy: null,
      sortDir: "asc",
    },
    lastExecution: {
      error: null,
      feedback: null,
      resultSummary: null,
    },
    chat: {
      open: false,
      sending: false,
      enabled: true,
      model: "gemini-3.5-flash-lite",
      messages: [],
    },
  };

  function createTableState() {
    return {
      columns: [],
      rows: [],
      rowStatuses: null,
      rowCount: 0,
      executionMs: 0,
      truncated: false,
      filter: "",
      sortIndex: null,
      sortDir: "asc",
      page: 1,
      pageSize: 25,
    };
  }

  // ==================== DOM HELPERS ====================
  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function saveSolved() {
    storageSet(STORAGE_SOLVED_KEY, JSON.stringify([...state.solvedIds]));
  }

  function getActiveDraftKey() {
    if (state.mode === "free") return "__free__";
    return state.currentChallenge ? state.currentChallenge.id : "__none__";
  }

  function saveCurrentDraft() {
    const key = getActiveDraftKey();
    state.drafts[key] = $("sql-input").value;
    storageSet(STORAGE_DRAFTS_KEY, JSON.stringify(state.drafts));
  }

  function restoreCurrentDraft() {
    const key = getActiveDraftKey();
    $("sql-input").value = state.drafts[key] || "";
    hideAutocomplete();
    updateLineNumbers();
  }

  // ==================== THEME ====================
  function initTheme() {
    let saved = "dark";
    try {
      saved = localStorage.getItem(STORAGE_THEME_KEY) || "dark";
    } catch {
      saved = "dark";
    }
    applyTheme(saved);
    $("theme-toggle-btn").addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      applyTheme(current === "dark" ? "light" : "dark");
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    storageSet(STORAGE_THEME_KEY, theme);
    $("theme-toggle-btn").textContent = theme === "dark" ? "☀" : "☾";
  }

  // ==================== API CALLS ====================
  async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const raw = await res.text();
      let detail = raw;
      try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.detail === "string") {
          detail = parsed.detail;
        }
      } catch {
        // Mantém texto bruto caso não seja JSON
      }
      throw new Error(detail || `Erro HTTP ${res.status}`);
    }
    return res.json();
  }

  async function loadInitialData() {
    const [schema, challenges] = await Promise.all([
      fetchJson("/api/schema"),
      fetchJson("/api/challenges"),
    ]);
    state.schema = schema;
    state.challenges = challenges;
    renderSchemaSidebar();
    renderChallengeControls();
    updateProgressPill();
    updateSqlHighlight();
    updateProgressPill();
  }

  // ==================== SCHEMA SIDEBAR ====================
  function renderSchemaSidebar() {
    const container = $("schema-list");
    if (!state.schema.length) {
      container.innerHTML = `<p class="muted-small">Nenhuma tabela encontrada.</p>`;
      return;
    }

    container.innerHTML = state.schema
      .map((table) => {
        const colsHtml = table.columns
          .map((col) => {
            const pkBadge = col.primary_key ? `<span class="key-tag key-pk">PK</span>` : "";
            const fkBadge = col.foreign_key
              ? `<span class="key-tag key-fk" title="Referencia ${escapeHtml(col.foreign_key)}">FK</span>`
              : "";
            return `
              <li class="schema-col-item" data-insert="${escapeHtml(col.name)}" title="Clique para inserir '${escapeHtml(col.name)}' no editor">
                <span class="col-name-wrap">
                  <span>${escapeHtml(col.name)}</span>
                  ${pkBadge}${fkBadge}
                </span>
                <span class="col-type">${escapeHtml(col.type)}</span>
              </li>
            `;
          })
          .join("");

        return `
          <div class="schema-table-card" data-table="${escapeHtml(table.name)}">
            <div class="schema-table-header">
              <span class="schema-table-name">${escapeHtml(table.name)}</span>
              <span class="schema-table-actions">
                <span class="count-badge">${table.row_count}</span>
                <button class="btn btn-ghost tiny browse-table-btn" data-table="${escapeHtml(table.name)}" title="Ver dados desta tabela">
                  Dados
                </button>
              </span>
            </div>
            <ul class="schema-columns">${colsHtml}</ul>
          </div>
        `;
      })
      .join("");

    container.querySelectorAll(".schema-table-header").forEach((header) => {
      header.addEventListener("click", (e) => {
        if (e.target.closest(".browse-table-btn")) return;
        const colsList = header.nextElementSibling;
        colsList.classList.toggle("collapsed");
      });
    });

    container.querySelectorAll(".browse-table-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        closeMobileSidebar();
        openDataBrowser(btn.dataset.table);
      });
    });

    container.querySelectorAll(".schema-col-item").forEach((item) => {
      item.addEventListener("click", () => {
        insertAtCursor(item.dataset.insert);
        if (isMobileViewport()) {
          closeMobileSidebar();
        }
      });
    });
  }

  // ==================== CHALLENGES ====================
  function getLevelChallenges() {
    return state.challenges.filter((c) => c.nivel === state.level);
  }

  function getFilteredChallenges() {
    const byLevel = getLevelChallenges();
    if (state.topic === "ALL") return byLevel;
    return byLevel.filter((c) => c.topicos.includes(state.topic));
  }

  function renderTopicFilter() {
    const topics = new Set();
    getLevelChallenges().forEach((c) => c.topicos.forEach((t) => topics.add(t)));
    const sortedTopics = [...topics].sort((a, b) => a.localeCompare(b, "pt-BR"));

    if (state.topic !== "ALL" && !topics.has(state.topic)) {
      state.topic = "ALL";
    }

    const select = $("topic-filter-select");
    select.innerHTML = [
      `<option value="ALL">Todos os tópicos</option>`,
      ...sortedTopics.map(
        (t) => `<option value="${escapeHtml(t)}" ${t === state.topic ? "selected" : ""}>${escapeHtml(t)}</option>`
      ),
    ].join("");
  }

  function renderChallengeControls() {
    renderTopicFilter();
    const list = getFilteredChallenges();
    const select = $("challenge-select");
    select.innerHTML = list
      .map((c, idx) => {
        const solvedMark = state.solvedIds.has(c.id) ? "✓ " : "";
        return `<option value="${escapeHtml(c.id)}">${solvedMark}${idx + 1}. ${escapeHtml(c.titulo)}</option>`;
      })
      .join("");

    if (!state.currentChallenge || !list.some((c) => c.id === state.currentChallenge.id)) {
      selectChallenge(list[0] || null);
    } else {
      select.value = state.currentChallenge.id;
      renderCurrentChallenge();
      updateChallengeNavButtons();
      renderCurrentChallenge();
    }
  }

  function updateChallengeNavButtons() {
    const list = getFilteredChallenges();
    const idx = state.currentChallenge ? list.findIndex((c) => c.id === state.currentChallenge.id) : -1;
    $("prev-challenge-btn").disabled = idx <= 0;
    $("next-challenge-btn").disabled = idx === -1 || idx >= list.length - 1;
  }

  function goToAdjacentChallenge(delta) {
    const list = getFilteredChallenges();
    if (!list.length) return;
    const idx = state.currentChallenge ? list.findIndex((c) => c.id === state.currentChallenge.id) : 0;
    const next = list[idx + delta];
    if (next) selectChallenge(next);
  }

  function getNextChallengeAction() {
    const list = getFilteredChallenges();
    const idx = state.currentChallenge ? list.findIndex((c) => c.id === state.currentChallenge.id) : -1;
    if (idx !== -1 && idx + 1 < list.length) {
      return { type: "challenge", challenge: list[idx + 1], label: "Próximo desafio ›" };
    }
    const levelsOrder = ["facil", "medio", "dificil"];
    const lvlIdx = levelsOrder.indexOf(state.level);
    if (state.topic === "ALL" && lvlIdx !== -1 && lvlIdx + 1 < levelsOrder.length) {
      const nextLevel = levelsOrder[lvlIdx + 1];
      return {
        type: "level",
        level: nextLevel,
        label: `Avançar para ${LEVEL_LABELS[nextLevel]} ›`,
      };
    }
    return null;
  }

  function isMobileViewport() {
    return window.matchMedia("(max-width: 960px)").matches;
  }

  function openMobileSidebar() {
    $("schema-sidebar").classList.add("mobile-open");
    $("sidebar-backdrop").classList.remove("hidden");
  }

  function closeMobileSidebar() {
    $("schema-sidebar").classList.remove("mobile-open");
    $("sidebar-backdrop").classList.add("hidden");
  }

  function closeMobileMenu() {
    $("topbar-tools-group").classList.remove("mobile-open");
  }

  function setMobileResultsTab(tab) {
    const grid = $("dual-results-grid");
    if (!grid) return;
    grid.setAttribute("data-mobile-tab", tab);
    const isUser = tab === "user";
    $("mobile-tab-user").classList.toggle("active", isUser);
    $("mobile-tab-user").setAttribute("aria-selected", String(isUser));
    $("mobile-tab-expected").classList.toggle("active", !isUser);
    $("mobile-tab-expected").setAttribute("aria-selected", String(!isUser));
  }

  function setExpectedSqlVisible(visible) {
    state.expectedSqlRevealed = Boolean(visible);
    $("expected-sql-code").classList.toggle("hidden", !state.expectedSqlRevealed);
    $("expected-sql-hidden-msg").classList.toggle("hidden", state.expectedSqlRevealed);
    $("copy-expected-sql-btn").classList.toggle("hidden", !state.expectedSqlRevealed);
    $("use-expected-sql-btn").classList.toggle("hidden", !state.expectedSqlRevealed);
    $("toggle-expected-sql-btn").textContent = state.expectedSqlRevealed
      ? "Ocultar solução"
      : "Revelar solução";
  }

  function resetResultsView() {
    $("feedback-banner").classList.add("hidden");
    $("banner-next-challenge-btn").classList.add("hidden");
    $("export-csv-btn").classList.add("hidden");
    $("mobile-results-tabs").classList.add("hidden");
    $("mobile-tab-user-badge").classList.add("hidden");
    $("mobile-tab-expected-badge").classList.add("hidden");
    setMobileResultsTab("user");
    $("dual-results-grid").classList.add("hidden");
    $("empty-results-state").classList.remove("hidden");
    $("user-error-box").classList.add("hidden");
    $("user-error-hint-box").classList.add("hidden");
    $("user-table-wrap").innerHTML = "";
    $("expected-table-wrap").innerHTML = "";
    $("user-pagination").innerHTML = "";
    $("expected-pagination").innerHTML = "";
    $("user-stats").textContent = "";
    $("expected-stats").textContent = "";
    $("user-diff-chip").classList.add("hidden");
    $("expected-diff-chip").classList.add("hidden");
    $("expected-sql-code").textContent = "";
    state.lastExpectedSql = "";
    state.lastExecution = { error: null, feedback: null, resultSummary: null };
    setExpectedSqlVisible(false);
  }

  function selectChallenge(challenge) {
    const previousId = state.currentChallenge ? state.currentChallenge.id : null;
    const nextId = challenge ? challenge.id : null;
    state.currentChallenge = challenge;
    if (challenge) {
      $("challenge-select").value = challenge.id;
    }
    $("challenge-hint-box").classList.add("hidden");
    $("toggle-hint-btn").textContent = "Ver dica";
    renderCurrentChallenge();
    updateChallengeNavButtons();
    if (state.mode === "challenge") {
      restoreCurrentDraft();
      if (previousId !== null && previousId !== nextId) {
        resetResultsView();
      }
    }
  }

  function renderCurrentChallenge() {
    const ch = state.currentChallenge;
    if (!ch) return;

    const badge = $("challenge-level-badge");
    badge.className = `badge badge-${ch.nivel}`;
    badge.textContent = LEVEL_LABELS[ch.nivel] || ch.nivel;

    $("challenge-title").textContent = ch.titulo;
    $("challenge-description").textContent = ch.enunciado;
    $("challenge-hint-box").textContent = `Dica: ${ch.dica}`;

    const isSolved = state.solvedIds.has(ch.id);
    $("challenge-solved-badge").classList.toggle("hidden", !isSolved);

    $("challenge-topics").innerHTML = ch.topicos
      .map((t) => `<span class="topic-tag">${escapeHtml(t)}</span>`)
      .join("");
  }

  function updateProgressPill() {
    const pill = $("progress-pill");
    pill.textContent = `${state.solvedIds.size} / ${state.challenges.length} resolvidos`;

    const levels = ["facil", "medio", "dificil"];
    const stats = levels.map((lvl) => {
      const items = state.challenges.filter((c) => c.nivel === lvl);
      const solved = items.filter((c) => state.solvedIds.has(c.id)).length;
      return { lvl, label: LEVEL_LABELS[lvl], solved, total: items.length };
    });

    pill.title =
      stats.map((s) => `${s.label}: ${s.solved}/${s.total}`).join(" • ") +
      " (clique para detalhar)";

    const pop = $("progress-popover");
    pop.innerHTML = stats
      .map((s) => {
        const pct = s.total ? Math.round((s.solved / s.total) * 100) : 0;
        return `
          <button type="button" class="progress-level-btn" data-jump-level="${s.lvl}">
            <div class="progress-level-head">
              <span>${escapeHtml(s.label)}</span>
              <span>${s.solved} / ${s.total} (${pct}%)</span>
            </div>
            <div class="progress-bar-track">
              <div class="progress-bar-fill" style="width: ${pct}%"></div>
            </div>
          </button>
        `;
      })
      .join("");

    pop.querySelectorAll("[data-jump-level]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const lvl = btn.dataset.jumpLevel;
        setMode("challenge");
        document.querySelectorAll(".diff-pill").forEach((p) => {
          p.classList.toggle("active", p.dataset.level === lvl);
        });
        state.level = lvl;
        renderChallengeControls();
        pop.classList.add("hidden");
      });
    });
  }

  function setMode(mode) {
    const modeChanged = state.mode !== mode;
    state.mode = mode;
    const isChallenge = mode === "challenge";

    $("mode-challenge-btn").classList.toggle("active", isChallenge);
    $("mode-free-btn").classList.toggle("active", !isChallenge);
    $("difficulty-controls").classList.toggle("hidden", !isChallenge);
    $("challenge-picker-wrap").classList.toggle("hidden", !isChallenge);
    $("challenge-card").classList.toggle("hidden", !isChallenge);
    $("free-mode-card").classList.toggle("hidden", isChallenge);

    if (!isChallenge) {
      $("feedback-banner").classList.add("hidden");
    $("banner-next-challenge-btn").classList.add("hidden");
    $("export-csv-btn").classList.add("hidden");
    $("mobile-results-tabs").classList.add("hidden");
    $("mobile-tab-user-badge").classList.add("hidden");
    $("mobile-tab-expected-badge").classList.add("hidden");
    setMobileResultsTab("user");
      $("expected-result-pane").classList.add("hidden");
      $("results-resizer").classList.add("hidden");
      $("user-result-pane").classList.add("single-full");
    } else {
      $("expected-result-pane").classList.remove("hidden");
      $("results-resizer").classList.remove("hidden");
      $("user-result-pane").classList.remove("single-full");
    }
    if (modeChanged) {
      resetResultsView();
    }
    restoreCurrentDraft();
  }

  // ==================== SQL EDITOR & FORMATADOR ====================
  function formatSqlQuery(rawSql) {
    // Protege literais '...' e "..." e comentários antes de formatar cláusulas
    const placeholders = [];
    const masked = rawSql.replace(/--[^\n]*|\/\*[\s\S]*?\*\/|'(?:''|[^'])*'|"(?:""|[^"])*"/g, (m) => {
      const idx = placeholders.length;
      placeholders.push(m);
      return `__SQL_PH_${idx}__`;
    });

    let formatted = masked.replace(/\s+/g, " ").trim();
    const keywords = [
      "SELECT", "DISTINCT", "FROM", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN",
      "JOIN", "ON", "WHERE", "AND", "OR", "GROUP BY", "HAVING", "ORDER BY", "LIMIT",
      "OFFSET", "WITH", "AS", "CASE", "WHEN", "THEN", "ELSE", "END", "UNION ALL", "UNION",
      "OVER", "PARTITION BY", "IS NOT NULL", "IS NULL", "NOT EXISTS", "EXISTS",
      "BETWEEN", "LIKE", "IN", "ASC", "DESC", "COUNT", "AVG", "SUM", "MIN", "MAX", "ROUND",
    ];
    keywords.forEach((kw) => {
      const re = new RegExp(`\\b${kw.replace(/ /g, "\\s+")}\\b`, "gi");
      formatted = formatted.replace(re, kw);
    });

    const newlineClauses = [
      "FROM", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN", "JOIN",
      "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "UNION ALL", "UNION",
    ];
    newlineClauses.forEach((clause) => {
      const re = new RegExp(`\\s+(${clause.replace(/ /g, "\\s+")})\\b`, "g");
      formatted = formatted.replace(re, "\n$1");
    });

    // Protege BETWEEN ... AND ... para não quebrar linha no AND do intervalo
    const betweenPlaceholders = [];
    formatted = formatted.replace(/\bBETWEEN\s+\S+\s+AND\s+\S+/g, (m) => {
      const idx = betweenPlaceholders.length;
      betweenPlaceholders.push(m);
      return `__SQL_BETWEEN_${idx}__`;
    });

    formatted = formatted.replace(/\s+(AND|OR)\b/g, "\n    $1");
    formatted = formatted.replace(/__SQL_BETWEEN_(\d+)__/g, (_, i) => betweenPlaceholders[Number(i)]);
    formatted = formatted.replace(/__SQL_PH_(\d+)__/g, (_, i) => placeholders[Number(i)]);
    return formatted;
  }

  const FREE_SQL_TEMPLATES = {
    top_notas:
      "SELECT\n    a.nome AS aluno,\n    d.nome AS disciplina,\n    n.avaliacao,\n    n.nota\nFROM notas n\nINNER JOIN alunos_disciplinas ad ON ad.id = n.aluno_disciplina_id\nINNER JOIN alunos a ON a.id = ad.aluno_id\nINNER JOIN disciplinas d ON d.id = ad.disciplina_id\nORDER BY n.nota DESC, a.nome ASC\nLIMIT 15;",
    join_completo:
      "SELECT\n    a.nome AS aluno,\n    c.nome AS curso,\n    d.nome AS disciplina,\n    p.nome AS professor,\n    ad.status\nFROM alunos_disciplinas ad\nINNER JOIN alunos a ON a.id = ad.aluno_id\nINNER JOIN disciplinas d ON d.id = ad.disciplina_id\nINNER JOIN cursos c ON c.id = d.curso_id\nINNER JOIN professores p ON p.id = d.professor_id\nORDER BY a.nome ASC, d.nome ASC;",
    media_disciplina:
      "SELECT\n    d.codigo,\n    d.nome AS disciplina,\n    COUNT(n.id) AS total_notas,\n    ROUND(AVG(n.nota), 2) AS media_nota\nFROM disciplinas d\nLEFT JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\nLEFT JOIN notas n ON n.aluno_disciplina_id = ad.id\nGROUP BY d.id, d.codigo, d.nome\nORDER BY media_nota DESC;",
    cte_ranking:
      "WITH medias AS (\n    SELECT\n        a.nome,\n        ROUND(AVG(n.nota), 2) AS media_geral,\n        COUNT(n.id) AS qtd_notas\n    FROM alunos a\n    INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n    INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n    GROUP BY a.id, a.nome\n)\nSELECT\n    nome,\n    qtd_notas,\n    media_geral,\n    RANK() OVER (ORDER BY media_geral DESC) AS ranking\nFROM medias\nORDER BY ranking ASC, nome ASC\nLIMIT 10;",
  };

  const SQL_KEYWORDS = new Set([
    "SELECT", "DISTINCT", "FROM", "INNER", "LEFT", "RIGHT", "CROSS", "JOIN", "ON",
    "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL", "BETWEEN", "LIKE", "EXISTS",
    "GROUP", "BY", "HAVING", "ORDER", "ASC", "DESC", "LIMIT", "OFFSET", "AS",
    "WITH", "RECURSIVE", "CASE", "WHEN", "THEN", "ELSE", "END", "UNION", "ALL",
    "OVER", "PARTITION", "FILTER", "GLOB", "ESCAPE", "CAST", "EXPLAIN", "QUERY", "PLAN",
  ]);

  const SQL_FUNCTIONS = new Set([
    "COUNT", "AVG", "SUM", "MIN", "MAX", "ROUND", "RANK", "DENSE_RANK", "ROW_NUMBER",
    "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "STRFTIME", "DATE", "DATETIME",
    "COALESCE", "IFNULL", "NULLIF", "LOWER", "UPPER", "LENGTH", "SUBSTR",
    "TRIM", "LTRIM", "RTRIM", "REPLACE", "GROUP_CONCAT", "ABS", "TYPEOF", "PRINTF",
  ]);

  const AUTOCOMPLETE_SNIPPETS = [
    { label: "SELECT", insert: "SELECT ", kind: "SQL" },
    { label: "DISTINCT", insert: "DISTINCT ", kind: "SQL" },
    { label: "FROM", insert: "FROM ", kind: "SQL" },
    { label: "INNER JOIN", insert: "INNER JOIN ", kind: "SQL" },
    { label: "LEFT JOIN", insert: "LEFT JOIN ", kind: "SQL" },
    { label: "WHERE", insert: "WHERE ", kind: "SQL" },
    { label: "GROUP BY", insert: "GROUP BY ", kind: "SQL" },
    { label: "HAVING", insert: "HAVING ", kind: "SQL" },
    { label: "ORDER BY", insert: "ORDER BY ", kind: "SQL" },
    { label: "LIMIT", insert: "LIMIT ", kind: "SQL" },
    { label: "WITH", insert: "WITH ", kind: "SQL" },
    { label: "CASE WHEN", insert: "CASE WHEN ", kind: "SQL" },
    { label: "BETWEEN", insert: "BETWEEN ", kind: "SQL" },
    { label: "NOT EXISTS", insert: "NOT EXISTS ", kind: "SQL" },
    { label: "IS NULL", insert: "IS NULL", kind: "SQL" },
    { label: "IS NOT NULL", insert: "IS NOT NULL", kind: "SQL" },
    { label: "COUNT(*)", insert: "COUNT(*)", kind: "Função" },
    { label: "AVG()", insert: "AVG(", kind: "Função" },
    { label: "SUM()", insert: "SUM(", kind: "Função" },
    { label: "MIN()", insert: "MIN(", kind: "Função" },
    { label: "MAX()", insert: "MAX(", kind: "Função" },
    { label: "ROUND(, 2)", insert: "ROUND(", kind: "Função" },
    { label: "RANK() OVER ()", insert: "RANK() OVER (", kind: "Função" },
    { label: "DENSE_RANK() OVER ()", insert: "DENSE_RANK() OVER (", kind: "Função" },
    { label: "strftime('%Y', )", insert: "strftime('%Y', ", kind: "Função" },
    { label: "COALESCE()", insert: "COALESCE(", kind: "Função" },
  ];

  const acState = {
    open: false,
    items: [],
    activeIndex: 0,
    replaceStart: 0,
  };

  function highlightSqlToHtml(sql) {
    const tableSet = new Set(state.schema.map((t) => t.name.toLowerCase()));
    const out = [];
    let i = 0;
    const len = sql.length;

    while (i < len) {
      const ch = sql[i];
      const nxt = i + 1 < len ? sql[i + 1] : "";

      if (ch === "-" && nxt === "-") {
        let end = i + 2;
        while (end < len && sql[end] !== "\n") end += 1;
        out.push(`<span class="tok-com">${escapeHtml(sql.slice(i, end))}</span>`);
        i = end;
        continue;
      }

      if (ch === "/" && nxt === "*") {
        let end = i + 2;
        while (end + 1 < len && !(sql[end] === "*" && sql[end + 1] === "/")) end += 1;
        end = end + 1 < len ? end + 2 : len;
        out.push(`<span class="tok-com">${escapeHtml(sql.slice(i, end))}</span>`);
        i = end;
        continue;
      }

      if (ch === "'") {
        let end = i + 1;
        while (end < len) {
          if (sql[end] === "'") {
            if (end + 1 < len && sql[end + 1] === "'") {
              end += 2;
              continue;
            }
            end += 1;
            break;
          }
          end += 1;
        }
        out.push(`<span class="tok-str">${escapeHtml(sql.slice(i, end))}</span>`);
        i = end;
        continue;
      }

      if (ch === '"' || ch === "`") {
        const quote = ch;
        let end = i + 1;
        while (end < len) {
          if (sql[end] === quote) {
            if (end + 1 < len && sql[end + 1] === quote) {
              end += 2;
              continue;
            }
            end += 1;
            break;
          }
          end += 1;
        }
        out.push(escapeHtml(sql.slice(i, end)));
        i = end;
        continue;
      }

      if (/[0-9]/.test(ch)) {
        let end = i + 1;
        while (end < len && /[0-9.]/.test(sql[end])) end += 1;
        out.push(`<span class="tok-num">${escapeHtml(sql.slice(i, end))}</span>`);
        i = end;
        continue;
      }

      if (/[A-Za-z_]/.test(ch)) {
        let end = i + 1;
        while (end < len && /[A-Za-z0-9_]/.test(sql[end])) end += 1;
        const word = sql.slice(i, end);
        const upper = word.toUpperCase();
        if (SQL_KEYWORDS.has(upper)) {
          out.push(`<span class="tok-kw">${escapeHtml(word)}</span>`);
        } else if (SQL_FUNCTIONS.has(upper)) {
          out.push(`<span class="tok-fn">${escapeHtml(word)}</span>`);
        } else if (tableSet.has(word.toLowerCase())) {
          out.push(`<span class="tok-tbl">${escapeHtml(word)}</span>`);
        } else {
          out.push(escapeHtml(word));
        }
        i = end;
        continue;
      }

      out.push(escapeHtml(ch));
      i += 1;
    }

    if (sql.endsWith("\n")) {
      out.push(" ");
    }
    return out.join("");
  }

  function syncEditorScroll() {
    const textarea = $("sql-input");
    const highlight = $("sql-highlight");
    $("line-numbers").scrollTop = textarea.scrollTop;
    highlight.scrollTop = textarea.scrollTop;
    highlight.scrollLeft = textarea.scrollLeft;
  }

  function updateSqlHighlight() {
    const textarea = $("sql-input");
    const highlight = $("sql-highlight");
    if (!textarea || !highlight) return;
    highlight.innerHTML = highlightSqlToHtml(textarea.value);
    syncEditorScroll();
  }

  function extractTableAliases(sql) {
    const aliases = new Map();
    const tableSet = new Set(state.schema.map((t) => t.name.toLowerCase()));
    const re = /\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?/gi;
    let match;
    while ((match = re.exec(sql)) !== null) {
      const tbl = match[1].toLowerCase();
      if (!tableSet.has(tbl)) continue;
      aliases.set(tbl, tbl);
      if (match[2] && !SQL_KEYWORDS.has(match[2].toUpperCase())) {
        aliases.set(match[2].toLowerCase(), tbl);
      }
    }
    return aliases;
  }

  function isInsideStringOrComment(text) {
    let inSingle = false;
    let inLineComment = false;
    let inBlockComment = false;
    for (let i = 0; i < text.length; i += 1) {
      const ch = text[i];
      const nxt = text[i + 1] || "";
      if (inLineComment) {
        if (ch === "\n") inLineComment = false;
        continue;
      }
      if (inBlockComment) {
        if (ch === "*" && nxt === "/") {
          inBlockComment = false;
          i += 1;
        }
        continue;
      }
      if (inSingle) {
        if (ch === "'") {
          if (nxt === "'") {
            i += 1;
          } else {
            inSingle = false;
          }
        }
        continue;
      }
      if (ch === "-" && nxt === "-") {
        inLineComment = true;
        i += 1;
      } else if (ch === "/" && nxt === "*") {
        inBlockComment = true;
        i += 1;
      } else if (ch === "'") {
        inSingle = true;
      }
    }
    return inSingle || inLineComment || inBlockComment;
  }

  function getCaretCoordinates(textarea, position) {
    const mirror = document.createElement("div");
    const style = window.getComputedStyle(textarea);
    const props = [
      "boxSizing", "width", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
      "fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "tabSize",
      "whiteSpace", "fontVariantLigatures",
    ];
    mirror.style.position = "absolute";
    mirror.style.visibility = "hidden";
    mirror.style.pointerEvents = "none";
    mirror.style.top = "0";
    mirror.style.left = "-9999px";
    props.forEach((p) => {
      mirror.style[p] = style[p];
    });
    mirror.textContent = textarea.value.slice(0, position);
    const marker = document.createElement("span");
    marker.textContent = "|";
    mirror.appendChild(marker);
    document.body.appendChild(mirror);
    const coords = {
      top: marker.offsetTop - textarea.scrollTop,
      left: marker.offsetLeft - textarea.scrollLeft,
      lineHeight: parseFloat(style.lineHeight) || 21,
    };
    document.body.removeChild(mirror);
    return coords;
  }

  function hideAutocomplete() {
    acState.open = false;
    acState.items = [];
    acState.activeIndex = 0;
    const pop = $("sql-autocomplete");
    if (pop) pop.classList.add("hidden");
  }

  function buildAutocompleteCandidates(textarea, forceOpen) {
    const cursor = textarea.selectionStart;
    if (cursor !== textarea.selectionEnd) return null;

    const before = textarea.value.slice(0, cursor);
    if (isInsideStringOrComment(before)) return null;

    const dotMatch = before.match(/([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_]*)$/);
    if (dotMatch) {
      const qualifier = dotMatch[1].toLowerCase();
      const prefix = dotMatch[2].toLowerCase();
      const aliases = extractTableAliases(textarea.value);
      const targetTableName = aliases.get(qualifier) || qualifier;
      const tableObj = state.schema.find((t) => t.name.toLowerCase() === targetTableName);
      if (!tableObj) return null;

      const cols = tableObj.columns
        .filter((c) => !prefix || c.name.toLowerCase().includes(prefix))
        .sort((a, b) => {
          const ap = a.name.toLowerCase().startsWith(prefix) ? 0 : 1;
          const bp = b.name.toLowerCase().startsWith(prefix) ? 0 : 1;
          return ap - bp || a.name.localeCompare(b.name);
        })
        .slice(0, 10)
        .map((c) => ({
          label: c.name,
          insert: c.name,
          kind: tableObj.name,
        }));

      return cols.length ? { items: cols, replaceStart: cursor - dotMatch[2].length } : null;
    }

    const wordMatch = before.match(/([A-Za-z_][A-Za-z0-9_]*)$/);
    const prefix = wordMatch ? wordMatch[1] : "";
    if (!forceOpen && prefix.length < 2) return null;

    const lower = prefix.toLowerCase();
    const seen = new Set();
    const pool = [];

    state.schema.forEach((tbl) => {
      if (!seen.has(`t:${tbl.name}`)) {
        seen.add(`t:${tbl.name}`);
        pool.push({ label: tbl.name, insert: tbl.name, kind: "Tabela" });
      }
      tbl.columns.forEach((col) => {
        const key = `c:${col.name}`;
        if (!seen.has(key)) {
          seen.add(key);
          pool.push({ label: col.name, insert: col.name, kind: tbl.name });
        }
      });
    });

    AUTOCOMPLETE_SNIPPETS.forEach((s) => {
      if (!seen.has(`k:${s.label}`)) {
        seen.add(`k:${s.label}`);
        pool.push(s);
      }
    });

    const filtered = pool
      .filter((item) => !lower || item.label.toLowerCase().includes(lower))
      .filter((item) => forceOpen || item.label.toLowerCase() !== lower)
      .sort((a, b) => {
        const ap = lower && a.label.toLowerCase().startsWith(lower) ? 0 : 1;
        const bp = lower && b.label.toLowerCase().startsWith(lower) ? 0 : 1;
        return ap - bp || a.label.localeCompare(b.label);
      })
      .slice(0, 10);

    return filtered.length ? { items: filtered, replaceStart: cursor - prefix.length } : null;
  }

  function renderAutocompletePopover(textarea) {
    const pop = $("sql-autocomplete");
    const stage = $("editor-stage");
    if (!acState.open || !acState.items.length) {
      pop.classList.add("hidden");
      return;
    }

    pop.innerHTML = acState.items
      .map(
        (item, idx) => `
          <button
            type="button"
            class="autocomplete-item ${idx === acState.activeIndex ? "active" : ""}"
            data-ac-idx="${idx}"
            role="option"
            aria-selected="${idx === acState.activeIndex}"
          >
            <span>${escapeHtml(item.label)}</span>
            <span class="autocomplete-kind">${escapeHtml(item.kind)}</span>
          </button>
        `
      )
      .join("");

    const coords = getCaretCoordinates(textarea, textarea.selectionStart);
    const maxLeft = Math.max(8, stage.clientWidth - 250);
    const maxTop = Math.max(8, stage.clientHeight - 180);
    pop.style.left = `${Math.min(Math.max(8, coords.left), maxLeft)}px`;
    pop.style.top = `${Math.min(Math.max(8, coords.top + coords.lineHeight + 4), maxTop)}px`;
    pop.classList.remove("hidden");

    pop.querySelectorAll(".autocomplete-item").forEach((btn) => {
      btn.addEventListener("mousedown", (e) => {
        e.preventDefault();
        applyAutocompleteItem(Number(btn.dataset.acIdx));
      });
    });
  }

  function updateAutocomplete(forceOpen = false) {
    const textarea = $("sql-input");
    const built = buildAutocompleteCandidates(textarea, forceOpen);
    if (!built) {
      hideAutocomplete();
      return;
    }
    acState.open = true;
    acState.items = built.items;
    acState.activeIndex = 0;
    acState.replaceStart = built.replaceStart;
    renderAutocompletePopover(textarea);
  }

  function applyAutocompleteItem(index) {
    const item = acState.items[index];
    if (!item) return;
    const textarea = $("sql-input");
    const before = textarea.value.slice(0, acState.replaceStart);
    const after = textarea.value.slice(textarea.selectionEnd);
    textarea.value = before + item.insert + after;
    const nextPos = before.length + item.insert.length;
    textarea.setSelectionRange(nextPos, nextPos);
    hideAutocomplete();
    updateLineNumbers();
    saveCurrentDraft();
    textarea.focus();
  }

  function updateLineNumbers() {
    const textarea = $("sql-input");
    const lines = textarea.value.split("\n").length;
    $("line-numbers").textContent = Array.from({ length: lines }, (_, i) => i + 1).join("\n");
    updateSqlHighlight();
  }

  function insertAtCursor(text, cursorOffset = null) {
    const textarea = $("sql-input");
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);
    textarea.value = before + text + after;
    const nextPos = start + (cursorOffset !== null ? cursorOffset : text.length);
    textarea.setSelectionRange(nextPos, nextPos);
    textarea.focus();
    updateLineNumbers();
    saveCurrentDraft();
  }

  function initEditor() {
    const textarea = $("sql-input");
    textarea.addEventListener("input", () => {
      updateLineNumbers();
      saveCurrentDraft();
      updateAutocomplete(false);
    });
    textarea.addEventListener("scroll", syncEditorScroll);
    textarea.addEventListener("blur", () => {
      setTimeout(hideAutocomplete, 120);
    });
    textarea.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        hideAutocomplete();
        runQuery();
        return;
      }
      if (e.ctrlKey && e.code === "Space") {
        e.preventDefault();
        updateAutocomplete(true);
        return;
      }
      if (acState.open) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          acState.activeIndex = (acState.activeIndex + 1) % acState.items.length;
          renderAutocompletePopover(textarea);
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          acState.activeIndex = (acState.activeIndex - 1 + acState.items.length) % acState.items.length;
          renderAutocompletePopover(textarea);
          return;
        }
        if (e.key === "Enter" || e.key === "Tab") {
          e.preventDefault();
          applyAutocompleteItem(acState.activeIndex);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          hideAutocomplete();
          return;
        }
      }
      if (e.key === "Tab") {
        e.preventDefault();
        insertAtCursor("    ");
      }
    });
    updateLineNumbers();
  }

  // ==================== QUERY EXECUTION ====================
  async function runQuery() {
    const sql = $("sql-input").value.trim();
    if (!sql) {
      showFeedback("error", "!", "Digite uma consulta SQL antes de executar.");
      return;
    }

    const runBtn = $("run-sql-btn");
    runBtn.disabled = true;
    runBtn.textContent = "Executando...";

    try {
      saveQueryHistory(sql);
      const payload = {
        sql,
        challenge_id: state.mode === "challenge" && state.currentChallenge
          ? state.currentChallenge.id
          : null,
      };

      const data = await fetchJson("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      renderExecutionResponse(data);
    } catch (err) {
      showFeedback("error", "!", `Falha ao comunicar com o servidor: ${err.message}`);
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = "▶ Executar SQL";
    }
  }

  async function runExplain() {
    const sql = $("sql-input").value.trim();
    if (!sql) {
      showFeedback("error", "!", "Digite uma consulta SQL para visualizar o plano de execução.");
      return;
    }

    const btn = $("explain-sql-btn");
    btn.disabled = true;
    try {
      const data = await fetchJson("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql }),
      });

      $("empty-results-state").classList.add("hidden");
      $("mobile-results-tabs").classList.add("hidden");
      setMobileResultsTab("user");
      $("dual-results-grid").classList.remove("hidden");
      $("expected-result-pane").classList.add("hidden");
      $("results-resizer").classList.add("hidden");
      $("user-result-pane").classList.add("single-full");

      $("user-diff-chip").classList.add("hidden");
      $("expected-diff-chip").classList.add("hidden");
      $("user-error-hint-box").classList.add("hidden");

      if (data.error) {
        state.lastExecution = { error: data.error, feedback: null, resultSummary: null };
        $("user-error-box").classList.remove("hidden");
        $("user-error-box").textContent = data.error;
        $("user-table-wrap").innerHTML = "";
        $("user-stats").textContent = "Erro";
        $("export-csv-btn").classList.add("hidden");
        showFeedback("error", "✕", data.error);
        $("banner-ask-tutor-btn").classList.remove("hidden");
      } else {
        state.lastExecution = {
          error: null,
          feedback: null,
          resultSummary: summarizeResultForTutor(data.result),
        };
        $("user-error-box").classList.add("hidden");
        hydrateResultTable("user", data.result, null);
        showFeedback(
          "success",
          "ℹ",
          "Plano de execução SQLite (EXPLAIN QUERY PLAN): veja abaixo se a query usa SCAN ou SEARCH."
        );
      }
    } catch (err) {
      showFeedback("error", "!", `Erro ao gerar plano: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  }

  function saveQueryHistory(sql) {
    const normalized = sql.trim();
    if (!normalized) return;
    state.history = [normalized, ...state.history.filter((q) => q !== normalized)].slice(0, 15);
    storageSet(STORAGE_HISTORY_KEY, JSON.stringify(state.history));
    renderHistoryPopover();
  }

  function renderHistoryPopover() {
    const pop = $("history-popover");
    if (!state.history.length) {
      pop.innerHTML = `<span class="muted-small history-empty">Nenhuma consulta executada ainda.</span>`;
      return;
    }
    pop.innerHTML = state.history
      .map(
        (sql, idx) =>
          `<button class="history-item" data-idx="${idx}" title="${escapeHtml(sql)}">${escapeHtml(sql)}</button>`
      )
      .join("");

    pop.querySelectorAll(".history-item").forEach((item) => {
      item.addEventListener("click", () => {
        $("sql-input").value = state.history[Number(item.dataset.idx)];
        updateLineNumbers();
        saveCurrentDraft();
        pop.classList.add("hidden");
        $("sql-input").focus();
      });
    });
  }

  function showFeedback(type, icon, message) {
    const banner = $("feedback-banner");
    banner.className = `feedback-banner ${type}`;
    $("feedback-icon").textContent = icon;
    $("feedback-text").textContent = message;
    $("banner-next-challenge-btn").classList.add("hidden");
    $("banner-ask-tutor-btn").classList.add("hidden");
  }

  function summarizeResultForTutor(result) {
    if (!result || !result.columns || !result.columns.length) return null;
    const sample = (result.rows || []).slice(0, 3).map((r) => JSON.stringify(r)).join("; ");
    return `Colunas: [${result.columns.join(", ")}] | ${result.row_count} linha(s)${sample ? ` | Amostra: ${sample}` : ""}`;
  }

  function renderExecutionResponse(data) {
    $("empty-results-state").classList.add("hidden");
    $("dual-results-grid").classList.remove("hidden");

    state.lastExecution = {
      error: data.user_error || null,
      feedback: data.feedback || null,
      resultSummary: summarizeResultForTutor(data.user_result),
    };

    // Resultado do usuário
    const userErrorBox = $("user-error-box");
    const userErrorHintBox = $("user-error-hint-box");
    const userTableWrap = $("user-table-wrap");
    if (data.user_error) {
      userErrorBox.classList.remove("hidden");
      userErrorBox.textContent = data.user_error;
      if (data.user_error_hint) {
        userErrorHintBox.classList.remove("hidden");
        userErrorHintBox.textContent = data.user_error_hint;
      } else {
        userErrorHintBox.classList.add("hidden");
      }
      userTableWrap.innerHTML = "";
      $("user-stats").textContent = "Erro";
      $("user-diff-chip").classList.add("hidden");
      $("user-pagination").innerHTML = "";
      $("export-csv-btn").classList.add("hidden");
    } else if (data.user_result) {
      userErrorBox.classList.add("hidden");
      userErrorHintBox.classList.add("hidden");
      hydrateResultTable("user", data.user_result, data.user_row_status || null);
    }

    if (data.mode === "challenge" && data.expected) {
      $("expected-result-pane").classList.remove("hidden");
      $("results-resizer").classList.remove("hidden");
      $("user-result-pane").classList.remove("single-full");
      $("mobile-results-tabs").classList.remove("hidden");
      setMobileResultsTab("user");

      const userBadge = $("mobile-tab-user-badge");
      const expectedBadge = $("mobile-tab-expected-badge");
      if (data.is_correct) {
        userBadge.textContent = "✓";
        userBadge.className = "mobile-tab-badge ok";
        expectedBadge.classList.add("hidden");
      } else if (data.user_error) {
        userBadge.textContent = "Erro";
        userBadge.className = "mobile-tab-badge err";
        expectedBadge.textContent = `${data.expected.result.row_count}`;
        expectedBadge.className = "mobile-tab-badge";
      } else {
        userBadge.textContent = "!";
        userBadge.className = "mobile-tab-badge warn";
        expectedBadge.textContent = `${data.expected.result.row_count}`;
        expectedBadge.className = "mobile-tab-badge";
      }

      state.lastExpectedSql = data.expected.sql;
      $("expected-sql-code").textContent = data.expected.sql;
      setExpectedSqlVisible(Boolean(data.is_correct));
      hydrateResultTable("expected", data.expected.result, data.expected_row_status || null);

      if (data.is_correct) {
        showFeedback("success", "✓", data.feedback);
        const nextAction = getNextChallengeAction();
        const nextBtn = $("banner-next-challenge-btn");
        if (nextAction) {
          nextBtn.textContent = nextAction.label;
          nextBtn.classList.remove("hidden");
        } else {
          nextBtn.classList.add("hidden");
        }
        if (data.challenge_id) {
          state.solvedIds.add(data.challenge_id);
          saveSolved();
          updateProgressPill();
          renderChallengeControls();
    updateProgressPill();
    updateSqlHighlight();
        }
      } else if (data.user_error) {
        showFeedback("error", "✕", data.feedback);
        $("banner-ask-tutor-btn").classList.remove("hidden");
      } else {
        showFeedback("warning", "!", data.feedback);
        $("banner-ask-tutor-btn").classList.remove("hidden");
      }
    } else {
      $("mobile-results-tabs").classList.add("hidden");
      setMobileResultsTab("user");
      $("expected-result-pane").classList.add("hidden");
      $("results-resizer").classList.add("hidden");
      $("user-result-pane").classList.add("single-full");
      $("expected-diff-chip").classList.add("hidden");

      if (data.user_error) {
        showFeedback("error", "✕", data.user_error);
        $("banner-ask-tutor-btn").classList.remove("hidden");
      } else {
        showFeedback(
          "success",
          "✓",
          `Consulta executada com sucesso (${data.user_result.row_count} linha(s) em ${data.user_result.execution_ms} ms).`
        );
      }
    }
  }

  // ==================== CLIENT-SIDE RESULT TABLE (FILTER / SORT / PAGINATE) ====================
  function updateDiffChip(key, rowStatuses) {
    const chip = $(`${key}-diff-chip`);
    if (!rowStatuses || !rowStatuses.length) {
      chip.classList.add("hidden");
      return;
    }
    const extraCount = rowStatuses.filter((s) => s === "extra").length;
    const missingCount = rowStatuses.filter((s) => s === "missing").length;
    const orderCount = rowStatuses.filter((s) => s === "order").length;

    if (extraCount > 0) {
      chip.className = "diff-chip extra";
      chip.textContent = `${extraCount} diferente(s)`;
    } else if (missingCount > 0) {
      chip.className = "diff-chip missing";
      chip.textContent = `${missingCount} faltando`;
    } else if (orderCount > 0) {
      chip.className = "diff-chip order";
      chip.textContent = `${orderCount} fora de ordem`;
    } else {
      chip.classList.add("hidden");
    }
  }

  function hydrateResultTable(key, result, rowStatuses = null) {
    const tState = state.tables[key];
    tState.columns = result.columns || [];
    tState.rows = result.rows || [];
    tState.rowStatuses = rowStatuses;
    tState.rowCount = result.row_count ?? tState.rows.length;
    tState.executionMs = result.execution_ms ?? 0;
    tState.truncated = Boolean(result.truncated);
    tState.filter = "";
    tState.sortIndex = null;
    tState.sortDir = "asc";
    tState.page = 1;

    $(`${key}-filter-input`).value = "";
    const truncTag = tState.truncated ? " (limite 500)" : "";
    $(`${key}-stats`).textContent = `${tState.rowCount} linha(s)${truncTag} • ${tState.executionMs} ms`;
    updateDiffChip(key, rowStatuses);
    if (key === "user") {
      $("export-csv-btn").classList.toggle("hidden", !tState.columns.length);
    }
    renderResultTable(key);
  }

  function getWorkingResultItems(key) {
    const tState = state.tables[key];
    let workingItems = tState.rows.map((cells, idx) => ({
      cells,
      status: tState.rowStatuses ? tState.rowStatuses[idx] : null,
    }));

    const term = tState.filter.trim().toLowerCase();
    if (term) {
      workingItems = workingItems.filter((item) =>
        item.cells.some((cell) => String(cell ?? "null").toLowerCase().includes(term))
      );
    }

    if (tState.sortIndex !== null) {
      const idx = tState.sortIndex;
      const dir = tState.sortDir === "asc" ? 1 : -1;
      workingItems = [...workingItems].sort(
        (a, b) => compareCells(a.cells[idx], b.cells[idx]) * dir
      );
    }
    return workingItems;
  }

  function exportUserCsv() {
    const tState = state.tables.user;
    if (!tState.columns.length) return;
    const items = getWorkingResultItems("user");

    const escapeCsvCell = (val) => {
      if (val === null || val === undefined) return "";
      const text = String(val);
      if (/[",;\n\r]/.test(text)) {
        return `"${text.replace(/"/g, '""')}"`;
      }
      return text;
    };

    const lines = [
      tState.columns.map(escapeCsvCell).join(","),
      ...items.map((item) => item.cells.map(escapeCsvCell).join(",")),
    ];
    const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const filename =
      state.mode === "challenge" && state.currentChallenge
        ? `${state.currentChallenge.id}.csv`
        : "resultado-sql.csv";
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function renderResultTable(key) {
    const tState = state.tables[key];
    const wrap = $(`${key}-table-wrap`);
    const footer = $(`${key}-pagination`);

    if (!tState.columns.length) {
      wrap.innerHTML = `<p class="empty-table-msg">Nenhuma coluna retornada.</p>`;
      footer.innerHTML = "";
      return;
    }

    const workingItems = getWorkingResultItems(key);

    const total = workingItems.length;
    const totalPages = Math.max(1, Math.ceil(total / tState.pageSize));
    if (tState.page > totalPages) tState.page = totalPages;

    const start = (tState.page - 1) * tState.pageSize;
    const pageItems = workingItems.slice(start, start + tState.pageSize);

    wrap.innerHTML = buildTableHtml(
      tState.columns,
      pageItems.map((i) => i.cells),
      tState.sortIndex,
      tState.sortDir,
      pageItems.map((i) => i.status)
    );

    wrap.querySelectorAll("th[data-col-idx]").forEach((th) => {
      th.addEventListener("click", () => {
        const colIdx = Number(th.dataset.colIdx);
        if (tState.sortIndex === colIdx) {
          tState.sortDir = tState.sortDir === "asc" ? "desc" : "asc";
        } else {
          tState.sortIndex = colIdx;
          tState.sortDir = "asc";
        }
        renderResultTable(key);
      });
    });

    renderPaginationFooter(footer, {
      page: tState.page,
      totalPages,
      totalRows: total,
      pageSize: tState.pageSize,
      onPageChange: (nextPage) => {
        tState.page = nextPage;
        renderResultTable(key);
      },
      onPageSizeChange: (nextSize) => {
        tState.pageSize = nextSize;
        tState.page = 1;
        renderResultTable(key);
      },
    });
  }

  function compareCells(a, b) {
    if (a === null || a === undefined) return b === null || b === undefined ? 0 : -1;
    if (b === null || b === undefined) return 1;
    if (typeof a === "number" && typeof b === "number") return a - b;
    return String(a).localeCompare(String(b), "pt-BR", { numeric: true });
  }

  function buildTableHtml(columns, rows, sortTarget, sortDir, rowStatuses = null) {
    const thead = columns
      .map((col, idx) => {
        const isSorted = sortTarget === idx || sortTarget === col;
        const arrow = isSorted ? (sortDir === "asc" ? " ▲" : " ▼") : "";
        return `<th data-col-idx="${idx}" data-col-name="${escapeHtml(col)}">${escapeHtml(col)}${arrow}</th>`;
      })
      .join("");

    if (!rows.length) {
      return `
        <table class="data-table">
          <thead><tr>${thead}</tr></thead>
        </table>
        <p class="empty-table-msg">Nenhum registro encontrado.</p>
      `;
    }

    const rowTitleMap = {
      extra: "Linha extra ou com valor diferente do gabarito",
      missing: "Linha esperada que faltou no seu resultado",
      order: "Registro correto, mas em posição de ordenação diferente",
    };

    const tbody = rows
      .map((row, rowIdx) => {
        const status = rowStatuses ? rowStatuses[rowIdx] : null;
        const trClass = status && status !== "match" ? `row-${status}` : "";
        const trTitle = status && rowTitleMap[status] ? ` title="${rowTitleMap[status]}"` : "";
        const tds = row
          .map((cell) => {
            if (cell === null || cell === undefined) {
              return `<td class="null-cell">NULL</td>`;
            }
            const text = escapeHtml(cell);
            return `<td title="${text}">${text}</td>`;
          })
          .join("");
        return `<tr${trClass ? ` class="${trClass}"` : ""}${trTitle}>${tds}</tr>`;
      })
      .join("");

    return `
      <table class="data-table">
        <thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
      </table>
    `;
  }

  function renderPaginationFooter(container, opts) {
    container.innerHTML = `
      <span>${opts.totalRows} registro(s) • Página ${opts.page} de ${opts.totalPages}</span>
      <div class="pagination-controls">
        <select class="page-size-select" aria-label="Linhas por página">
          ${[10, 15, 25, 50, 100]
            .map((sz) => `<option value="${sz}" ${sz === opts.pageSize ? "selected" : ""}>${sz}/pág</option>`)
            .join("")}
        </select>
        <button class="btn btn-ghost tiny prev-btn" ${opts.page <= 1 ? "disabled" : ""}>‹ Anterior</button>
        <button class="btn btn-ghost tiny next-btn" ${opts.page >= opts.totalPages ? "disabled" : ""}>Próxima ›</button>
      </div>
    `;

    container.querySelector(".page-size-select").addEventListener("change", (e) => {
      opts.onPageSizeChange(Number(e.target.value));
    });
    container.querySelector(".prev-btn").addEventListener("click", () => {
      if (opts.page > 1) opts.onPageChange(opts.page - 1);
    });
    container.querySelector(".next-btn").addEventListener("click", () => {
      if (opts.page < opts.totalPages) opts.onPageChange(opts.page + 1);
    });
  }

  // ==================== DATA BROWSER MODAL ====================
  function openDataBrowser(tableName) {
    if (tableName) {
      state.browser.table = tableName;
    } else if (state.schema.length && !state.schema.some((t) => t.name === state.browser.table)) {
      state.browser.table = state.schema[0].name;
    }
    state.browser.page = 1;
    state.browser.sortBy = null;
    state.browser.sortDir = "asc";
    $("data-browser-backdrop").classList.remove("hidden");
    renderBrowserTabs();
    loadBrowserData();
  }

  function closeDataBrowser() {
    const modal = $("data-browser-modal");
    modal.classList.remove("maximized", "minimized");
    $("data-browser-backdrop").classList.add("hidden");
  }

  function renderBrowserTabs() {
    $("browser-table-tabs").innerHTML = state.schema
      .map(
        (t) => `
          <button class="browser-tab ${t.name === state.browser.table ? "active" : ""}" data-table="${escapeHtml(t.name)}">
            ${escapeHtml(t.name)} (${t.row_count})
          </button>
        `
      )
      .join("");

    $("browser-table-tabs").querySelectorAll(".browser-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.browser.table = btn.dataset.table;
        state.browser.page = 1;
        state.browser.sortBy = null;
        state.browser.sortDir = "asc";
        renderBrowserTabs();
        loadBrowserData();
      });
    });
  }

  async function loadBrowserData() {
    const b = state.browser;
    const params = new URLSearchParams({
      page: String(b.page),
      page_size: String(b.pageSize),
      search: b.search,
      sort_dir: b.sortDir,
    });
    if (b.sortBy) params.set("sort_by", b.sortBy);

    const wrap = $("browser-table-wrap");
    let data;
    try {
      data = await fetchJson(`/api/tables/${encodeURIComponent(b.table)}?${params.toString()}`);
    } catch (err) {
      $("browser-stats").textContent = "Erro ao carregar";
      wrap.innerHTML = `<div class="error-box">Erro ao carregar dados da tabela: ${escapeHtml(err.message)}</div>`;
      $("browser-pagination").innerHTML = "";
      return;
    }

    $("browser-stats").textContent = `${data.table} • ${data.total_rows} registro(s)`;
    wrap.innerHTML = buildTableHtml(data.columns, data.rows, b.sortBy, b.sortDir);

    wrap.querySelectorAll("th[data-col-name]").forEach((th) => {
      th.addEventListener("click", () => {
        const colName = th.dataset.colName;
        if (b.sortBy === colName) {
          b.sortDir = b.sortDir === "asc" ? "desc" : "asc";
        } else {
          b.sortBy = colName;
          b.sortDir = "asc";
        }
        loadBrowserData();
      });
    });

    renderPaginationFooter($("browser-pagination"), {
      page: data.page,
      totalPages: data.total_pages,
      totalRows: data.total_rows,
      pageSize: data.page_size,
      onPageChange: (nextPage) => {
        b.page = nextPage;
        loadBrowserData();
      },
      onPageSizeChange: (nextSize) => {
        b.pageSize = nextSize;
        b.page = 1;
        loadBrowserData();
      },
    });
  }

  // ==================== DER / MAPEAMENTO DE OBJETOS ====================
  const DER_ORDER = [
    "professores",
    "disciplinas",
    "cursos",
    "alunos",
    "alunos_disciplinas",
    "notas",
  ];

  function openDerModal() {
    $("der-backdrop").classList.remove("hidden");
    renderDerDiagram();
    requestAnimationFrame(drawDerConnectors);
  }

  function closeDerModal() {
    const modal = $("der-modal");
    modal.classList.remove("maximized", "minimized");
    $("der-backdrop").classList.add("hidden");
  }

  function renderDerDiagram() {
    const ordered = [...state.schema].sort((a, b) => {
      const ia = DER_ORDER.indexOf(a.name);
      const ib = DER_ORDER.indexOf(b.name);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    $("der-grid").innerHTML = ordered
      .map((table) => {
        const colsHtml = table.columns
          .map((col) => {
            const pk = col.primary_key ? `<span class="key-tag key-pk">PK</span>` : "";
            const fk = col.foreign_key ? `<span class="key-tag key-fk">FK</span>` : "";
            return `
              <li>
                <span class="col-name-wrap">
                  ${pk}${fk}
                  <span>${escapeHtml(col.name)}</span>
                </span>
                <span class="col-type">${escapeHtml(col.type)}${col.foreign_key ? ` (${escapeHtml(col.foreign_key.split(".")[0])})` : ""}</span>
              </li>
            `;
          })
          .join("");

        return `
          <div class="der-card" data-der-table="${escapeHtml(table.name)}">
            <div class="der-card-header">
              <span>${escapeHtml(table.name)}</span>
              <button class="btn btn-ghost tiny der-open-data-btn" data-table="${escapeHtml(table.name)}">
                ${table.row_count} reg.
              </button>
            </div>
            <ul class="der-card-cols">${colsHtml}</ul>
          </div>
        `;
      })
      .join("");

    $("der-grid").querySelectorAll(".der-open-data-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        closeDerModal();
        openDataBrowser(btn.dataset.table);
      });
    });
  }

  function drawDerConnectors() {
    const wrap = $("der-canvas-wrap");
    const svg = $("der-svg");
    if (!wrap || !svg || $("der-backdrop").classList.contains("hidden")) return;

    const wrapRect = wrap.getBoundingClientRect();
    svg.setAttribute("width", String(wrap.scrollWidth));
    svg.setAttribute("height", String(wrap.scrollHeight));
    svg.style.width = `${wrap.scrollWidth}px`;
    svg.style.height = `${wrap.scrollHeight}px`;

    const elements = [];
    state.schema.forEach((table) => {
      const safeTable = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(table.name) : table.name;
      const manyCard = $("der-grid").querySelector(`[data-der-table="${safeTable}"]`);
      if (!manyCard) return;

      table.columns.forEach((col) => {
        if (!col.foreign_key) return;
        const targetTable = col.foreign_key.split(".")[0];
        const safeTarget = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(targetTable) : targetTable;
        const oneCard = $("der-grid").querySelector(`[data-der-table="${safeTarget}"]`);
        if (!oneCard) return;

        // toLocal converte coordenadas de viewport para coordenadas internas do canvas scrollável
        const rOne = oneCard.getBoundingClientRect();
        const rMany = manyCard.getBoundingClientRect();

        const oneBox = {
          left: rOne.left - wrapRect.left + wrap.scrollLeft,
          right: rOne.right - wrapRect.left + wrap.scrollLeft,
          top: rOne.top - wrapRect.top + wrap.scrollTop,
          bottom: rOne.bottom - wrapRect.top + wrap.scrollTop,
          cx: rOne.left - wrapRect.left + wrap.scrollLeft + rOne.width / 2,
          cy: rOne.top - wrapRect.top + wrap.scrollTop + rOne.height / 2,
        };
        const manyBox = {
          left: rMany.left - wrapRect.left + wrap.scrollLeft,
          right: rMany.right - wrapRect.left + wrap.scrollLeft,
          top: rMany.top - wrapRect.top + wrap.scrollTop,
          bottom: rMany.bottom - wrapRect.top + wrap.scrollTop,
          cx: rMany.left - wrapRect.left + wrap.scrollLeft + rMany.width / 2,
          cy: rMany.top - wrapRect.top + wrap.scrollTop + rMany.height / 2,
        };

        const dx = manyBox.cx - oneBox.cx;
        const dy = manyBox.cy - oneBox.cy;
        const isHorizontal = Math.abs(dx) >= Math.abs(dy);

        let pOne, pMany, outOne, outMany, cardLabel;
        if (isHorizontal) {
          if (dx >= 0) {
            // 1 à esquerda -> N à direita (1:N)
            pOne = { x: oneBox.right, y: oneBox.cy };
            pMany = { x: manyBox.left, y: manyBox.cy };
            outOne = { x: 1, y: 0 };
            outMany = { x: -1, y: 0 };
            cardLabel = "1 : N";
          } else {
            // N à esquerda <- 1 à direita (N:1)
            pOne = { x: oneBox.left, y: oneBox.cy };
            pMany = { x: manyBox.right, y: manyBox.cy };
            outOne = { x: -1, y: 0 };
            outMany = { x: 1, y: 0 };
            cardLabel = "N : 1";
          }
        } else if (dy >= 0) {
          // 1 acima -> N abaixo (1:N)
          pOne = { x: oneBox.cx, y: oneBox.bottom };
          pMany = { x: manyBox.cx, y: manyBox.top };
          outOne = { x: 0, y: 1 };
          outMany = { x: 0, y: -1 };
          cardLabel = "1 : N";
        } else {
          // N acima <- 1 abaixo (N:1)
          pOne = { x: oneBox.cx, y: oneBox.top };
          pMany = { x: manyBox.cx, y: manyBox.bottom };
          outOne = { x: 0, y: -1 };
          outMany = { x: 0, y: 1 };
          cardLabel = "N : 1";
        }

        // Vetores perpendiculares para desenhar o traço de "1" e o tridente de "N"
        const perpOne = { x: -outOne.y, y: outOne.x };
        const perpMany = { x: -outMany.y, y: outMany.x };

        // Lado 1: linha entrando + traço perpendicular única ("1 registro")
        const oneStubEnd = { x: pOne.x + outOne.x * 12, y: pOne.y + outOne.y * 12 };
        const tickPos = { x: pOne.x + outOne.x * 8, y: pOne.y + outOne.y * 8 };
        const tickA = { x: tickPos.x + perpOne.x * 6, y: tickPos.y + perpOne.y * 6 };
        const tickB = { x: tickPos.x - perpOne.x * 6, y: tickPos.y - perpOne.y * 6 };

        // Lado N: ponto de bifurcação + tridente de 3 pontas tocando a borda ("N registros")
        const fork = { x: pMany.x + outMany.x * 15, y: pMany.y + outMany.y * 15 };
        const prongTop = { x: pMany.x + perpMany.x * 7, y: pMany.y + perpMany.y * 7 };
        const prongBot = { x: pMany.x - perpMany.x * 7, y: pMany.y - perpMany.y * 7 };

        // Curva suave ligando o lado 1 ao ponto de bifurcação do tridente
        let curveD;
        if (isHorizontal) {
          const midX = (oneStubEnd.x + fork.x) / 2;
          curveD = `M ${pOne.x} ${pOne.y} L ${oneStubEnd.x} ${oneStubEnd.y} C ${midX} ${oneStubEnd.y}, ${midX} ${fork.y}, ${fork.x} ${fork.y}`;
        } else {
          const midY = (oneStubEnd.y + fork.y) / 2;
          curveD = `M ${pOne.x} ${pOne.y} L ${oneStubEnd.x} ${oneStubEnd.y} C ${oneStubEnd.x} ${midY}, ${fork.x} ${midY}, ${fork.x} ${fork.y}`;
        }

        const midPt = {
          x: (oneStubEnd.x + fork.x) / 2,
          y: (oneStubEnd.y + fork.y) / 2,
        };

        elements.push(`
          <g>
            <path d="${curveD}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-opacity="0.85" />
            <line x1="${tickA.x}" y1="${tickA.y}" x2="${tickB.x}" y2="${tickB.y}" stroke="var(--accent)" stroke-width="2.2" />
            <line x1="${fork.x}" y1="${fork.y}" x2="${pMany.x}" y2="${pMany.y}" stroke="var(--accent)" stroke-width="2" />
            <line x1="${fork.x}" y1="${fork.y}" x2="${prongTop.x}" y2="${prongTop.y}" stroke="var(--accent)" stroke-width="2" />
            <line x1="${fork.x}" y1="${fork.y}" x2="${prongBot.x}" y2="${prongBot.y}" stroke="var(--accent)" stroke-width="2" />
            <rect x="${midPt.x - 19}" y="${midPt.y - 9}" width="38" height="18" rx="9" fill="var(--bg-elevated)" stroke="var(--accent)" stroke-width="1.2" />
            <text x="${midPt.x}" y="${midPt.y + 3.5}" text-anchor="middle" font-size="10" font-weight="700" font-family="var(--mono)" fill="var(--text)">${cardLabel}</text>
          </g>
        `);
      });
    });

    svg.innerHTML = elements.join("");
  }

  // ==================== GUIA RÁPIDO ====================
  function openGuideModal() {
    $("guide-backdrop").classList.remove("hidden");
  }

  function closeGuideModal() {
    $("guide-modal").classList.remove("maximized");
    $("guide-backdrop").classList.add("hidden");
  }

  // ==================== MINIMIZE / MAXIMIZE & RESIZERS ====================
  function initPaneControls() {
    document.querySelectorAll(".pane-minimize-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pane = $(btn.dataset.target);
        pane.classList.remove("maximized");
        const isMin = pane.classList.toggle("minimized");
        btn.textContent = isMin ? "+" : "−";
      });
    });

    document.querySelectorAll(".pane-maximize-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pane = $(btn.dataset.target);
        pane.classList.remove("minimized");
        const isMax = pane.classList.toggle("maximized");
        btn.textContent = isMax ? "⤡" : "⤢";
      });
    });

    // Controles do Explorador de Dados
    $("browser-minimize-btn").addEventListener("click", () => {
      const modal = $("data-browser-modal");
      modal.classList.remove("maximized");
      const isMin = modal.classList.toggle("minimized");
      $("browser-minimize-btn").textContent = isMin ? "+" : "−";
    });

    $("browser-maximize-btn").addEventListener("click", () => {
      const modal = $("data-browser-modal");
      modal.classList.remove("minimized");
      const isMax = modal.classList.toggle("maximized");
      $("browser-maximize-btn").textContent = isMax ? "⤡" : "⤢";
    });

    $("browser-close-btn").addEventListener("click", closeDataBrowser);
    $("data-browser-backdrop").addEventListener("click", (e) => {
      if (e.target === $("data-browser-backdrop")) closeDataBrowser();
    });

    // Controles do DER (Mapeamento de Objetos)
    $("der-minimize-btn").addEventListener("click", () => {
      const modal = $("der-modal");
      modal.classList.remove("maximized");
      const isMin = modal.classList.toggle("minimized");
      $("der-minimize-btn").textContent = isMin ? "+" : "−";
    });
    $("der-maximize-btn").addEventListener("click", () => {
      const modal = $("der-modal");
      modal.classList.remove("minimized");
      const isMax = modal.classList.toggle("maximized");
      $("der-maximize-btn").textContent = isMax ? "⤡" : "⤢";
      requestAnimationFrame(drawDerConnectors);
    });
    $("der-close-btn").addEventListener("click", closeDerModal);
    $("der-backdrop").addEventListener("click", (e) => {
      if (e.target === $("der-backdrop")) closeDerModal();
    });

    // Controles do Guia SQL
    $("guide-maximize-btn").addEventListener("click", () => {
      const modal = $("guide-modal");
      const isMax = modal.classList.toggle("maximized");
      $("guide-maximize-btn").textContent = isMax ? "⤡" : "⤢";
    });
    $("guide-close-btn").addEventListener("click", closeGuideModal);
    $("guide-backdrop").addEventListener("click", (e) => {
      if (e.target === $("guide-backdrop")) closeGuideModal();
    });
    document.querySelectorAll("[data-guide-tab]").forEach((tabBtn) => {
      tabBtn.addEventListener("click", () => {
        document.querySelectorAll("[data-guide-tab]").forEach((b) => b.classList.remove("active"));
        tabBtn.classList.add("active");
        const target = tabBtn.dataset.guideTab;
        $("guide-tab-cheat").classList.toggle("hidden", target !== "cheat");
        $("guide-tab-dialects").classList.toggle("hidden", target !== "dialects");
      });
    });

    window.addEventListener("resize", () => {
      if (!$("der-backdrop").classList.contains("hidden")) {
        drawDerConnectors();
      }
      if (!isMobileViewport()) {
        closeMobileSidebar();
        closeMobileMenu();
      }
    });

    if (typeof ResizeObserver !== "undefined") {
      const derObserver = new ResizeObserver(() => {
        if (!$("der-backdrop").classList.contains("hidden")) {
          drawDerConnectors();
        }
      });
      derObserver.observe($("der-canvas-wrap"));
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document.querySelectorAll(".result-pane.maximized").forEach((p) => {
          p.classList.remove("maximized");
          const maxBtn = p.querySelector(".pane-maximize-btn");
          if (maxBtn) maxBtn.textContent = "⤢";
        });
        if (!$("data-browser-backdrop").classList.contains("hidden")) closeDataBrowser();
        if (!$("der-backdrop").classList.contains("hidden")) closeDerModal();
        if (!$("guide-backdrop").classList.contains("hidden")) closeGuideModal();
        $("history-popover").classList.add("hidden");
        $("progress-popover").classList.add("hidden");
        hideAutocomplete();
        closeMobileSidebar();
        closeMobileMenu();
        if (state.chat.open) closeChatDrawer();
      }
    });
  }

  function makeHorizontalResizer(resizerEl, getTargetEl, minWidth, maxWidth) {
    resizerEl.addEventListener("mousedown", (e) => {
      e.preventDefault();
      resizerEl.classList.add("active");
      const target = getTargetEl();
      const startX = e.clientX;
      const startWidth = target.getBoundingClientRect().width;

      function onMove(ev) {
        const delta = ev.clientX - startX;
        const nextWidth = Math.min(maxWidth, Math.max(minWidth, startWidth + delta));
        target.style.flex = `0 0 ${nextWidth}px`;
        target.style.width = `${nextWidth}px`;
      }

      function onUp() {
        resizerEl.classList.remove("active");
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    });
  }

  function makeVerticalResizer(resizerEl, targetEl, containerEl) {
    resizerEl.addEventListener("mousedown", (e) => {
      e.preventDefault();
      resizerEl.classList.add("active");
      const startY = e.clientY;
      const startHeight = targetEl.getBoundingClientRect().height;
      const totalHeight = containerEl.getBoundingClientRect().height;

      function onMove(ev) {
        const delta = ev.clientY - startY;
        const nextHeight = Math.min(totalHeight * 0.75, Math.max(190, startHeight + delta));
        targetEl.style.height = `${nextHeight}px`;
      }

      function onUp() {
        resizerEl.classList.remove("active");
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      }

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    });
  }

  function initResizers() {
    makeHorizontalResizer($("sidebar-resizer"), () => $("schema-sidebar"), 210, 520);
    makeHorizontalResizer($("results-resizer"), () => $("user-result-pane"), 240, 900);
    makeVerticalResizer($("vertical-resizer"), $("editor-section"), $("main-workspace"));
  }

  // ==================== EVENT WIRING ====================
  function initControls() {
    $("toggle-sidebar-btn").addEventListener("click", () => {
      if (isMobileViewport()) {
        const isOpen = $("schema-sidebar").classList.toggle("mobile-open");
        $("sidebar-backdrop").classList.toggle("hidden", !isOpen);
      } else {
        $("schema-sidebar").classList.toggle("collapsed");
      }
    });

    $("close-sidebar-mobile-btn").addEventListener("click", closeMobileSidebar);
    $("sidebar-backdrop").addEventListener("click", closeMobileSidebar);

    $("mobile-menu-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      $("topbar-tools-group").classList.toggle("mobile-open");
    });

    $("topbar-tools-group").querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", closeMobileMenu);
    });

    document.querySelectorAll(".mobile-sql-chip").forEach((chip) => {
      chip.addEventListener("mousedown", (e) => {
        e.preventDefault();
      });
      chip.addEventListener("click", () => {
        const offset = chip.dataset.offset ? Number(chip.dataset.offset) : null;
        insertAtCursor(chip.dataset.insert || "", offset);
      });
    });

    $("mobile-tab-user").addEventListener("click", () => setMobileResultsTab("user"));
    $("mobile-tab-expected").addEventListener("click", () => setMobileResultsTab("expected"));

    $("collapse-all-tables-btn").addEventListener("click", () => {
      const lists = document.querySelectorAll(".schema-columns");
      const anyExpanded = [...lists].some((el) => !el.classList.contains("collapsed"));
      lists.forEach((el) => el.classList.toggle("collapsed", anyExpanded));
    });

    $("mode-challenge-btn").addEventListener("click", () => setMode("challenge"));
    $("mode-free-btn").addEventListener("click", () => setMode("free"));

    document.querySelectorAll(".diff-pill").forEach((pill) => {
      pill.addEventListener("click", () => {
        document.querySelectorAll(".diff-pill").forEach((p) => p.classList.remove("active"));
        pill.classList.add("active");
        state.level = pill.dataset.level;
        renderChallengeControls();
    updateProgressPill();
    updateSqlHighlight();
      });
    });

    $("topic-filter-select").addEventListener("change", (e) => {
      state.topic = e.target.value;
      renderChallengeControls();
    updateProgressPill();
    updateSqlHighlight();
    });

    $("prev-challenge-btn").addEventListener("click", () => goToAdjacentChallenge(-1));
    $("next-challenge-btn").addEventListener("click", () => goToAdjacentChallenge(1));

    $("banner-next-challenge-btn").addEventListener("click", () => {
      const action = getNextChallengeAction();
      if (!action) return;
      if (action.type === "challenge") {
        selectChallenge(action.challenge);
      } else if (action.type === "level") {
        document.querySelectorAll(".diff-pill").forEach((p) => {
          p.classList.toggle("active", p.dataset.level === action.level);
        });
        state.level = action.level;
        renderChallengeControls();
      }
    });

    $("progress-pill").addEventListener("click", (e) => {
      e.stopPropagation();
      $("progress-popover").classList.toggle("hidden");
    });

    document.querySelectorAll(".free-template-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const sql = FREE_SQL_TEMPLATES[btn.dataset.template];
        if (!sql) return;
        $("sql-input").value = sql;
        updateLineNumbers();
        saveCurrentDraft();
        $("sql-input").focus();
      });
    });

    $("export-csv-btn").addEventListener("click", exportUserCsv);

    $("challenge-select").addEventListener("change", (e) => {
      const found = state.challenges.find((c) => c.id === e.target.value);
      selectChallenge(found || null);
    });

    $("reset-progress-btn").addEventListener("click", () => {
      if (!state.solvedIds.size) return;
      if (!window.confirm("Deseja zerar todos os exercícios marcados como resolvidos?")) return;
      state.solvedIds.clear();
      saveSolved();
      updateProgressPill();
      renderChallengeControls();
    updateProgressPill();
    updateSqlHighlight();
    });

    $("random-challenge-btn").addEventListener("click", () => {
      const list = getFilteredChallenges();
      if (list.length <= 1) return;
      const candidates = list.filter((c) => c.id !== state.currentChallenge?.id);
      const picked = candidates[Math.floor(Math.random() * candidates.length)];
      selectChallenge(picked);
    });

    $("toggle-hint-btn").addEventListener("click", () => {
      const box = $("challenge-hint-box");
      const hidden = box.classList.toggle("hidden");
      $("toggle-hint-btn").textContent = hidden ? "Ver dica" : "Ocultar dica";
    });

    $("format-sql-btn").addEventListener("click", () => {
      const current = $("sql-input").value;
      if (!current.trim()) return;
      $("sql-input").value = formatSqlQuery(current);
      updateLineNumbers();
      saveCurrentDraft();
      $("sql-input").focus();
    });

    $("clear-sql-btn").addEventListener("click", () => {
      $("sql-input").value = "";
      updateLineNumbers();
      saveCurrentDraft();
      $("sql-input").focus();
    });

    $("run-sql-btn").addEventListener("click", runQuery);
    $("explain-sql-btn").addEventListener("click", runExplain);

    renderHistoryPopover();
    $("history-toggle-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      $("history-popover").classList.toggle("hidden");
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".history-wrap")) {
        $("history-popover").classList.add("hidden");
      }
      if (!e.target.closest(".progress-wrap")) {
        $("progress-popover").classList.add("hidden");
      }
      if (!e.target.closest(".editor-stage")) {
        hideAutocomplete();
      }
      if (!e.target.closest(".mobile-menu-wrap")) {
        closeMobileMenu();
      }
    });

    $("user-filter-input").addEventListener("input", (e) => {
      state.tables.user.filter = e.target.value;
      state.tables.user.page = 1;
      renderResultTable("user");
    });

    $("expected-filter-input").addEventListener("input", (e) => {
      state.tables.expected.filter = e.target.value;
      state.tables.expected.page = 1;
      renderResultTable("expected");
    });

    $("toggle-expected-sql-btn").addEventListener("click", () => {
      setExpectedSqlVisible(!state.expectedSqlRevealed);
    });

    $("copy-expected-sql-btn").addEventListener("click", async () => {
      if (!state.lastExpectedSql) return;
      try {
        await navigator.clipboard.writeText(state.lastExpectedSql);
        $("copy-expected-sql-btn").textContent = "Copiado!";
        setTimeout(() => {
          $("copy-expected-sql-btn").textContent = "Copiar";
        }, 1200);
      } catch {
        $("copy-expected-sql-btn").textContent = "Erro";
      }
    });

    $("use-expected-sql-btn").addEventListener("click", () => {
      if (!state.lastExpectedSql) return;
      $("sql-input").value = state.lastExpectedSql;
      updateLineNumbers();
      saveCurrentDraft();
      $("sql-input").focus();
    });

    $("open-browser-btn").addEventListener("click", () => openDataBrowser());
    $("open-der-btn").addEventListener("click", openDerModal);
    $("open-guide-btn").addEventListener("click", openGuideModal);

    let browserSearchTimer = null;
    $("browser-search-input").addEventListener("input", (e) => {
      clearTimeout(browserSearchTimer);
      browserSearchTimer = setTimeout(() => {
        state.browser.search = e.target.value;
        state.browser.page = 1;
        loadBrowserData();
      }, 180);
    });
  }

  // ==================== CHAT TUTOR SQL (GEMINI) ====================
  function formatChatMarkdown(text) {
    const codeBlocks = [];
    const withPlaceholders = String(text || "").replace(/```(?:\w+)?\n?([\s\S]*?)```/g, (_, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre class="chat-code-block">${escapeHtml(code.trim())}</pre>`);
      return `__CHAT_CODE_${idx}__`;
    });

    let html = escapeHtml(withPlaceholders)
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");

    html = html.replace(/__CHAT_CODE_(\d+)__/g, (_, i) => codeBlocks[Number(i)]);
    return html;
  }

  function updateChatContextLabel() {
    const label = $("chat-context-label");
    if (!label) return;
    const parts = [];
    if (state.mode === "challenge" && state.currentChallenge) {
      parts.push(state.currentChallenge.titulo);
    } else {
      parts.push("Modo Livre");
    }
    if ($("sql-input").value.trim()) parts.push("query do editor");
    if (state.lastExecution.error) parts.push("último erro");
    label.textContent = `Anexar contexto (${parts.join(" • ")})`;
  }

  function renderChatMessages() {
    const container = $("chat-messages");
    if (!container) return;

    if (!state.chat.messages.length) {
      container.innerHTML = `
        <div class="chat-msg model">
          ${formatChatMarkdown(
            "Olá! Sou o **Tutor SQL**.\nEscreva ou execute uma consulta e me pergunte **por que ela não funcionou**, como corrigir um `JOIN`, `GROUP BY`, ou diferenças do **SQLite**."
          )}
        </div>
      `;
      return;
    }

    container.innerHTML = state.chat.messages
      .map((msg) => `<div class="chat-msg ${escapeHtml(msg.role)}">${formatChatMarkdown(msg.text)}</div>`)
      .join("");
    container.scrollTop = container.scrollHeight;
  }

  function openChatDrawer(prefillPrompt = null) {
    state.chat.open = true;
    $("chat-drawer").classList.remove("hidden");
    $("chat-fab").classList.add("hidden");
    updateChatContextLabel();
    renderChatMessages();
    const input = $("chat-input");
    if (prefillPrompt) {
      input.value = prefillPrompt;
    }
    input.focus();
  }

  function closeChatDrawer() {
    state.chat.open = false;
    $("chat-drawer").classList.add("hidden");
    $("chat-fab").classList.remove("hidden");
  }

  async function checkChatStatus() {
    try {
      const status = await fetchJson("/api/chat/status");
      state.chat.enabled = Boolean(status.enabled);
      state.chat.model = status.model || "gemini-3.5-flash-lite";
      const badge = $("chat-status-badge");
      if (badge) {
        badge.textContent = state.chat.enabled ? state.chat.model : "Chave não configurada";
      }
    } catch {
      // Silencioso no boot
    }
  }

  async function sendChatMessage(overrideText = null) {
    if (state.chat.sending) return;
    const input = $("chat-input");
    const message = (overrideText !== null ? overrideText : input.value).trim();
    if (!message) return;

    if (overrideText === null) {
      input.value = "";
    }

    const history = state.chat.messages
      .filter((m) => m.role === "user" || m.role === "model")
      .slice(-10)
      .map((m) => ({ role: m.role, text: m.text }));

    state.chat.messages.push({ role: "user", text: message });
    state.chat.messages.push({ role: "model", text: "Analisando sua query..." });
    state.chat.sending = true;
    $("chat-send-btn").disabled = true;
    renderChatMessages();

    const includeCtx = $("chat-include-context").checked;
    const payload = {
      message,
      history,
      sql: includeCtx ? $("sql-input").value : null,
      challenge_id:
        includeCtx && state.mode === "challenge" && state.currentChallenge
          ? state.currentChallenge.id
          : null,
      last_error: includeCtx ? state.lastExecution.error : null,
      last_feedback: includeCtx ? state.lastExecution.feedback : null,
      last_result_summary: includeCtx ? state.lastExecution.resultSummary : null,
    };

    try {
      const data = await fetchJson("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.chat.messages[state.chat.messages.length - 1] = {
        role: "model",
        text: data.reply,
      };
      if (data.model) {
        state.chat.model = data.model;
      }
      const badge = $("chat-status-badge");
      if (badge) {
        const rem =
          typeof data.remaining_daily === "number" ? ` • ${data.remaining_daily} restam hoje` : "";
        badge.textContent = `${state.chat.model}${rem}`;
      }
    } catch (err) {
      state.chat.messages[state.chat.messages.length - 1] = {
        role: "error",
        text: `Não foi possível obter resposta do tutor: ${err.message}`,
      };
    } finally {
      state.chat.sending = false;
      $("chat-send-btn").disabled = false;
      renderChatMessages();
      updateChatContextLabel();
      input.focus();
    }
  }

  function initChat() {
    $("chat-fab").addEventListener("click", () => openChatDrawer());
    $("chat-close-btn").addEventListener("click", closeChatDrawer);
    $("chat-clear-btn").addEventListener("click", () => {
      state.chat.messages = [];
      renderChatMessages();
    });
    $("chat-send-btn").addEventListener("click", () => sendChatMessage());
    $("chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });
    document.querySelectorAll(".chat-quick-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        sendChatMessage(btn.dataset.prompt || "");
      });
    });
    $("banner-ask-tutor-btn").addEventListener("click", () => {
      const prompt = state.lastExecution.error
        ? "Por que minha query deu esse erro e como posso corrigir?"
        : "Por que o resultado da minha query ficou diferente do esperado?";
      openChatDrawer(prompt);
    });
    renderChatMessages();
    checkChatStatus();
  }

  // ==================== BOOT ====================
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initEditor();
    initControls();
    initPaneControls();
    initResizers();
    initChat();
    loadInitialData().catch((err) => {
      showFeedback("error", "!", `Erro ao inicializar aplicação: ${err.message}`);
    });
  });
})();
