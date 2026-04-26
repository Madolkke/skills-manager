const baseCases = [
  {
    id: "case-null-check",
    title: "遗漏空值检查",
    source: "manual",
    severity: "medium",
    weight: 2,
    expectation: "指出新增路径可能传入 null，并要求补测试。",
  },
  {
    id: "case-race",
    title: "异步竞态条件",
    source: "manual",
    severity: "high",
    weight: 4,
    expectation: "识别异步写入顺序不稳定，并说明可复现风险。",
  },
  {
    id: "case-auth",
    title: "权限绕过",
    source: "manual",
    severity: "critical",
    weight: 5,
    expectation: "指出缺少 owner 校验导致越权读取。",
  },
  {
    id: "case-tests",
    title: "缺少回归测试",
    source: "manual",
    severity: "medium",
    weight: 2,
    expectation: "要求补充失败路径测试，而不是只看 happy path。",
  },
  {
    id: "case-noise",
    title: "避免风格噪声",
    source: "manual",
    severity: "low",
    weight: 1,
    expectation: "不要把低价值命名建议当成主要 finding。",
  },
];

const badCaseEval = {
  id: "case-secret-log",
  title: "日志泄露 JWT secret",
  source: "bad_case",
  severity: "critical",
  weight: 5,
  expectation: "必须指出 secret 被写入日志，并标为高风险安全问题。",
};

const variantsSeed = [
  {
    id: "variant-a",
    name: "Variant A",
    label: "Codex baseline",
    tags: ["codex"],
    contentRef: "inline_bundle:code-reviewer-a@sha-91aa",
    parent: null,
    summary: "通用 Codex 审查，关注 bug、测试缺口和可维护性。",
  },
  {
    id: "variant-b",
    name: "Variant B",
    label: "Codex + GPT-5.4 tuned",
    tags: ["codex", "gpt5.4"],
    contentRef: "inline_bundle:code-reviewer-b@sha-23bc",
    parent: "variant-a",
    summary: "针对 GPT-5.4 的长上下文审查，引用更完整，但输出更长。",
  },
];

const variantC = {
  id: "variant-c",
  name: "Variant C",
  label: "Secret-aware Codex",
  tags: ["codex"],
  contentRef: "inline_bundle:code-reviewer-c@sha-77cf",
  parent: "variant-a",
  summary: "从 bad case 升级而来，加入 secret、credential、token 日志泄露检查。",
};

const initialRuns = {
  v1: {
    "variant-a": {
      "case-null-check": 1,
      "case-race": 1,
      "case-auth": 1,
      "case-tests": 1,
      "case-noise": 0,
    },
    "variant-b": {
      "case-null-check": 1,
      "case-race": 1,
      "case-auth": 0,
      "case-tests": 1,
      "case-noise": 1,
    },
  },
  v2: {
    "variant-a": {
      "case-null-check": 1,
      "case-race": 1,
      "case-auth": 1,
      "case-tests": 1,
      "case-noise": 0,
      "case-secret-log": 0,
    },
    "variant-b": {
      "case-null-check": 1,
      "case-race": 1,
      "case-auth": 0,
      "case-tests": 1,
      "case-noise": 1,
      "case-secret-log": 1,
    },
    "variant-c": {
      "case-null-check": 1,
      "case-race": 1,
      "case-auth": 1,
      "case-tests": 1,
      "case-noise": 1,
      "case-secret-log": 1,
    },
  },
};

const badCase = {
  id: "bc-001",
  title: "JWT secret 被写入日志但审查未发现",
  skill: "code-reviewer",
  variant: "Variant A",
  tags: ["codex"],
  failureType: "missed_security_issue",
  rawInput: `diff --git a/auth/session.ts b/auth/session.ts
+ console.info("jwt secret", process.env.JWT_SECRET)
+ return sign(payload, process.env.JWT_SECRET)

用户期望：
审查应该指出 secret 被写入日志。`,
  rawOutput: `Finding 1: 建议把 session.ts 中的变量名改得更清晰。
Finding 2: 这里缺少针对 sign() 的单元测试。

遗漏：
没有指出 JWT_SECRET 被输出到日志。`,
};

const state = {
  view: "hub",
  requestedTags: ["codex"],
  evalVersion: "v1",
  rankingStrategy: "balanced",
  badCaseConverted: false,
  variantCRegistered: false,
  variantCRun: false,
  compareLeft: "variant-a",
  compareRight: "variant-b",
  selectedVariant: "variant-a",
};

const tagOptions = ["codex", "gpt5.4", "opencode", "minimax2.7"];

const skillCards = [
  {
    id: "code-reviewer",
    name: "code-reviewer",
    summary: "审查代码变更，发现 bug、安全风险、测试缺口和高价值维护问题。",
    tags: ["codex", "gpt5.4"],
    variants: 3,
    cases: 6,
    score: "100%",
  },
  {
    id: "research-summarizer",
    name: "research-summarizer",
    summary: "把多来源材料整理成带引用的研究摘要，区分事实、推断和冲突。",
    tags: ["codex", "minimax2.7"],
    variants: 4,
    cases: 18,
    score: "83%",
  },
  {
    id: "sql-migration-assistant",
    name: "sql-migration-assistant",
    summary: "生成数据库迁移方案，检查回滚、锁表、危险 DDL 和上线风险。",
    tags: ["opencode", "codex"],
    variants: 2,
    cases: 11,
    score: "76%",
  },
];

function getEvalCases(version = state.evalVersion) {
  if (version === "v2" && state.badCaseConverted) {
    return [...baseCases, badCaseEval];
  }
  return baseCases;
}

function getVersions() {
  return state.badCaseConverted ? ["v1", "v2"] : ["v1"];
}

function getVariants() {
  const variants = [...variantsSeed];
  if (state.variantCRegistered) variants.push(variantC);
  return variants;
}

function getRun(version, variantId) {
  if (variantId === "variant-c" && (!state.variantCRegistered || !state.variantCRun)) return null;
  if (version === "v2" && !state.badCaseConverted) return null;
  return initialRuns[version]?.[variantId] ?? null;
}

function caseScore(version, variantId, caseId) {
  const run = getRun(version, variantId);
  if (!run || run[caseId] === undefined) return null;
  return run[caseId];
}

function aggregateScore(version, variantId) {
  const cases = getEvalCases(version);
  const run = getRun(version, variantId);
  if (!run) return null;
  const totalWeight = cases.reduce((sum, item) => sum + item.weight, 0);
  const score = cases.reduce((sum, item) => sum + (run[item.id] ?? 0) * item.weight, 0);
  return score / totalWeight;
}

function tagMatchScore(variant) {
  if (state.requestedTags.length === 0) return 0.5;
  const variantTags = new Set(variant.tags);
  const matches = state.requestedTags.filter((tag) => variantTags.has(tag)).length;
  const exact = matches === state.requestedTags.length && variant.tags.length === state.requestedTags.length;
  if (exact) return 1;
  if (matches === state.requestedTags.length) return 0.86;
  if (matches > 0) return 0.62;
  return 0.2;
}

function rankVariants() {
  return getVariants()
    .map((variant) => {
      const evalScore = aggregateScore(state.evalVersion, variant.id);
      const matchScore = tagMatchScore(variant);
      let score = evalScore === null ? 0 : evalScore;
      if (state.rankingStrategy === "tag-match-first") {
        score = score * 0.55 + matchScore * 0.45;
      } else if (state.rankingStrategy === "regression-first") {
        const secret = caseScore(state.evalVersion, variant.id, "case-secret-log");
        const regressionBonus = secret === 1 ? 0.12 : secret === 0 ? -0.18 : 0;
        score = score * 0.82 + matchScore * 0.18 + regressionBonus;
      } else {
        score = score * 0.72 + matchScore * 0.28;
      }
      return { variant, evalScore, matchScore, score };
    })
    .sort((a, b) => b.score - a.score);
}

function percent(value) {
  if (value === null || Number.isNaN(value)) return "未运行";
  return `${Math.round(value * 100)}%`;
}

function severityLabel(severity) {
  return {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  }[severity] ?? severity;
}

function sourceLabel(source) {
  return {
    manual: "人工",
    bad_case: "BadCase",
    imported: "导入",
    generated: "生成",
  }[source] ?? source;
}

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function render() {
  renderNav();
  renderTopbar();
  renderControls();
  renderStatus();
  renderHubView();
  renderSkillView();
  renderEvalView();
  syncButtons();
}

function renderNav() {
  qsa(".nav-item").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.view);
  });
  qsa(".view").forEach((view) => {
    view.classList.toggle("is-active", view.id === `view-${state.view}`);
  });
  qsa(".detail-only").forEach((element) => {
    element.classList.toggle("is-hidden", state.view === "hub");
  });
}

function renderTopbar() {
  const titles = {
    hub: ["SkillHub", "Explore Skills"],
    skill: ["Skill Detail", "code-reviewer"],
    eval: ["Eval Corpus", "code-reviewer corpus"],
  };
  const [eyebrow, title] = titles[state.view] ?? titles.hub;
  qs("#pageEyebrow").textContent = eyebrow;
  qs("#pageTitle").textContent = title;
  qs("#installTop").classList.toggle("is-hidden", state.view === "hub");
}

function renderControls() {
  qs("#requestedTags").innerHTML = tagOptions
    .map(
      (tag) =>
        `<button class="chip ${state.requestedTags.includes(tag) ? "is-active" : ""}" data-tag="${tag}">${tag}</button>`,
    )
    .join("");

  qs("#evalVersionPicker").innerHTML = getVersions()
    .map(
      (version) =>
        `<button class="${state.evalVersion === version ? "is-active" : ""}" data-version="${version}">${version}</button>`,
    )
    .join("");

  qs("#rankingStrategy").value = state.rankingStrategy;
}

function renderStatus() {
  const statuses = {
    badcase: true,
    evalcase: state.badCaseConverted,
    variant: state.variantCRegistered,
    run: state.variantCRun,
  };
  qsa(".status-step").forEach((step) => {
    step.classList.toggle("is-done", Boolean(statuses[step.dataset.step]));
  });
}

function renderHubView() {
  qs("#hubGrid").innerHTML = skillCards
    .map(
      (skill) => `
        <article class="skill-card" data-open-skill="${skill.id}">
          <div class="skill-card-head">
            <div>
              <h2>${skill.name}</h2>
              <p>${skill.summary}</p>
            </div>
            <button class="primary-button" data-open-skill="${skill.id}">查看</button>
          </div>
          <div class="skill-card-tags">
            ${skill.tags.map((tag) => `<span class="tag-pill">${tag}</span>`).join("")}
          </div>
          <div class="skill-card-metrics">
            <div><strong>${skill.variants}</strong><span>variants</span></div>
            <div><strong>${skill.cases}</strong><span>eval cases</span></div>
            <div><strong>${skill.score}</strong><span>latest pass</span></div>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderSkillView() {
  const ranked = rankVariants();
  qs("#rankingHint").textContent = `请求 tags: [${state.requestedTags.join(", ") || "none"}]，测评版本: ${state.evalVersion}。`;
  renderVariantMap(ranked);
  renderVariantDrawer(ranked);

  const best = ranked[0];
  const runnable = ranked.filter((item) => item.evalScore !== null);
  const criticalFailures = getEvalCases().filter((item) =>
    runnable.some(({ variant }) => item.severity === "critical" && caseScore(state.evalVersion, variant.id, item.id) === 0),
  );
  const scoreSummary = qs("#scoreSummary");
  if (scoreSummary) scoreSummary.innerHTML = `
    <div class="metric">
      <div class="metric-label">当前最佳</div>
      <div class="metric-value">${best?.variant.name ?? "无"}</div>
      <div class="metric-note">${best ? percent(best.evalScore) : "没有可用测评"}</div>
    </div>
    <div class="metric">
      <div class="metric-label">EvalSetVersion</div>
      <div class="metric-value">${state.evalVersion}</div>
      <div class="metric-note">${getEvalCases().length} 个 cases</div>
    </div>
    <div class="metric">
      <div class="metric-label">严重失败</div>
      <div class="metric-value">${criticalFailures.length}</div>
      <div class="metric-note">跨可运行 variants 统计</div>
    </div>
  `;

  renderCompareSelectors();
  renderComparison();
}

function renderVariantMap(ranked) {
  const variants = getVariants();
  const groups = groupVariantsByTagSet(variants);
  const rankIndex = new Map(ranked.map((item, index) => [item.variant.id, { ...item, rank: index + 1 }]));
  qs("#variantMap").innerHTML = groups
    .map(([tagKey, groupVariants]) => {
      const tagLabel = tagKey || "untagged";
      return `
        <section class="tag-lane">
          <div class="tag-start-node">
            <div class="tag-start-label">TagSet</div>
            <div class="tag-start-title">[${tagLabel}]</div>
          </div>
          <div class="lane-connector" aria-hidden="true"></div>
          <div class="variant-node-row">
            ${groupVariants
              .map((variant) => {
                const rankedItem = rankIndex.get(variant.id);
                const evalScore = rankedItem?.evalScore ?? null;
                const run = getRun(state.evalVersion, variant.id);
                const failedCritical = getEvalCases().some(
                  (item) => item.severity === "critical" && caseScore(state.evalVersion, variant.id, item.id) === 0,
                );
                const stateClass = !run ? "warn" : failedCritical ? "fail" : "pass";
                const stateText = !run ? "未运行" : failedCritical ? "严重失败" : "可比较";
                const parent = variant.parent ? getVariants().find((item) => item.id === variant.parent)?.name : "root";
                return `
                  <button class="variant-node ${state.selectedVariant === variant.id ? "is-selected" : ""}" data-select-variant="${variant.id}">
                    <span class="rank-badge">#${rankedItem?.rank ?? "-"}</span>
                    <span class="variant-node-title">${variant.name}</span>
                    <span class="state-pill ${stateClass}">${stateText}</span>
                    <span class="variant-node-score">${percent(evalScore)}</span>
                    <span class="variant-node-parent">parent: ${parent}</span>
                  </button>
                `;
              })
              .join("")}
          </div>
        </section>
      `;
    })
    .join("");
}

function groupVariantsByTagSet(variants) {
  const groups = new Map();
  variants.forEach((variant) => {
    const key = [...variant.tags].sort().join(", ");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(variant);
  });
  return Array.from(groups.entries());
}

function renderVariantDrawer(ranked) {
  const selected = getVariants().find((variant) => variant.id === state.selectedVariant) ?? getVariants()[0];
  const rankedItem = ranked.find((item) => item.variant.id === selected.id);
  const children = getVariants().filter((variant) => variant.parent === selected.id);
  const parent = selected.parent ? getVariants().find((variant) => variant.id === selected.parent) : null;
  const fixedCases = getEvalCases().filter((item) => caseScore(state.evalVersion, selected.id, item.id) === 1);
  const failedCases = getEvalCases().filter((item) => caseScore(state.evalVersion, selected.id, item.id) === 0);
  qs("#variantDrawer").innerHTML = `
    <div class="drawer-hero">
      <div>
        <div class="variant-titleline">
          <span class="variant-name">${selected.name}</span>
          ${selected.tags.map((tag) => `<span class="tag-pill">${tag}</span>`).join("")}
        </div>
        <p>${selected.label}。${selected.summary}</p>
      </div>
      <div class="score-number">${percent(rankedItem?.evalScore ?? null)}</div>
    </div>
    <div class="drawer-facts">
      <div class="fact-row">
        <div class="fact-label">content_ref</div>
        <div class="fact-value">${selected.contentRef}</div>
      </div>
      <div class="fact-row">
        <div class="fact-label">parent</div>
        <div class="fact-value">${parent ? parent.name : "root variant"}</div>
      </div>
      <div class="fact-row">
        <div class="fact-label">children</div>
        <div class="fact-value">${children.length ? children.map((item) => item.name).join(", ") : "无"}</div>
      </div>
      <div class="fact-row">
        <div class="fact-label">history</div>
        <div class="fact-value">${variantHistory(selected)}</div>
      </div>
    </div>
    <div class="drawer-split">
      <div class="diff-box">
        <h3>通过 cases</h3>
        <ul class="diff-list">${listCases(fixedCases)}</ul>
      </div>
      <div class="diff-box">
        <h3>失败 cases</h3>
        <ul class="diff-list">${listCases(failedCases)}</ul>
      </div>
    </div>
  `;
}

function variantHistory(variant) {
  if (variant.id === "variant-c") return "由 Variant A 根据 case-secret-log 升级；v2 运行后 critical regression 清零。";
  if (variant.id === "variant-b") return "由 Variant A 调整为 codex + gpt5.4 情境；更强引用和长上下文表现。";
  return "初始 Codex 变体；作为后续变体的根节点。";
}

function renderCaseMatrix() {
  const variants = getVariants();
  const cases = getEvalCases();
  qs("#caseMatrix").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>EvalCase</th>
          <th>来源</th>
          <th>严重度</th>
          ${variants.map((variant) => `<th>${variant.name}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${cases
          .map(
            (item) => `
              <tr>
                <td>${item.title}</td>
                <td>${sourceLabel(item.source)}</td>
                <td>${severityLabel(item.severity)}</td>
                ${variants
                  .map((variant) => {
                    const score = caseScore(state.evalVersion, variant.id, item.id);
                    const cls = score === null ? "missing" : score ? "pass" : "fail";
                    const text = score === null ? "·" : score ? "✓" : "×";
                    return `<td><span class="result-dot ${cls}">${text}</span></td>`;
                  })
                  .join("")}
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderCompareSelectors() {
  const options = getVariants()
    .map((variant) => `<option value="${variant.id}">${variant.name}</option>`)
    .join("");
  qs("#compareLeft").innerHTML = options;
  qs("#compareRight").innerHTML = options;
  if (!getVariants().some((variant) => variant.id === state.compareLeft)) state.compareLeft = getVariants()[0]?.id;
  if (!getVariants().some((variant) => variant.id === state.compareRight)) state.compareRight = getVariants()[1]?.id ?? state.compareLeft;
  qs("#compareLeft").value = state.compareLeft;
  qs("#compareRight").value = state.compareRight;
}

function renderComparison() {
  const left = getVariants().find((variant) => variant.id === state.compareLeft);
  const right = getVariants().find((variant) => variant.id === state.compareRight);
  if (!left || !right) {
    qs("#comparison").innerHTML = "<p>请选择两个 variants。</p>";
    return;
  }

  const cases = getEvalCases();
  const rightWins = cases.filter(
    (item) => caseScore(state.evalVersion, left.id, item.id) === 0 && caseScore(state.evalVersion, right.id, item.id) === 1,
  );
  const leftWins = cases.filter(
    (item) => caseScore(state.evalVersion, left.id, item.id) === 1 && caseScore(state.evalVersion, right.id, item.id) === 0,
  );
  const bothFail = cases.filter(
    (item) => caseScore(state.evalVersion, left.id, item.id) === 0 && caseScore(state.evalVersion, right.id, item.id) === 0,
  );

  qs("#comparison").innerHTML = `
    <div class="diff-grid">
      <div class="diff-box">
        <h3>${right.name} 新通过</h3>
        <ul class="diff-list">${listCases(rightWins)}</ul>
      </div>
      <div class="diff-box">
        <h3>${left.name} 保留优势</h3>
        <ul class="diff-list">${listCases(leftWins)}</ul>
      </div>
      <div class="diff-box">
        <h3>共同失败</h3>
        <ul class="diff-list">${listCases(bothFail)}</ul>
      </div>
    </div>
  `;
}

function listCases(cases) {
  if (cases.length === 0) return "<li>无</li>";
  return cases.map((item) => `<li>${item.title} · ${severityLabel(item.severity)}</li>`).join("");
}

function renderEvalView() {
  const cases = getEvalCases(state.evalVersion);
  const badCaseCount = cases.filter((item) => item.source === "bad_case").length;
  const totalWeight = cases.reduce((sum, item) => sum + item.weight, 0);
  const ranked = rankVariants();
  const best = ranked[0];
  const runnable = ranked.filter((item) => item.evalScore !== null);
  const criticalFailures = getEvalCases().filter((item) =>
    runnable.some(({ variant }) => item.severity === "critical" && caseScore(state.evalVersion, variant.id, item.id) === 0),
  );
  qs("#corpusSummary").innerHTML = `
    <div class="metric">
      <div class="metric-label">当前版本</div>
      <div class="metric-value">${state.evalVersion}</div>
      <div class="metric-note">${getVersions().join(" / ")}</div>
    </div>
    <div class="metric">
      <div class="metric-label">Cases</div>
      <div class="metric-value">${cases.length}</div>
      <div class="metric-note">当前快照</div>
    </div>
    <div class="metric">
      <div class="metric-label">BadCase 来源</div>
      <div class="metric-value">${badCaseCount}</div>
      <div class="metric-note">转化后才计入</div>
    </div>
    <div class="metric">
      <div class="metric-label">总权重</div>
      <div class="metric-value">${totalWeight}</div>
      <div class="metric-note">用于聚合分数</div>
    </div>
  `;

  qs("#sourceEvent").innerHTML = `
    <div class="source-card">
      <div>
        <div class="fact-label">待处理来源事件</div>
        <div class="source-title">${badCase.title}</div>
        <p>${state.badCaseConverted ? "已转化为 case-secret-log，并进入 EvalSetVersion v2。" : "尚未进入测评集，不影响任何变体排名。"}</p>
      </div>
      <div class="source-actions-inline">
        <span class="state-pill ${state.badCaseConverted ? "pass" : "warn"}">${state.badCaseConverted ? "已入集" : "待转化"}</span>
      </div>
    </div>
  `;

  qs("#scoreSummary").innerHTML = `
    <div class="metric">
      <div class="metric-label">当前最佳</div>
      <div class="metric-value">${best?.variant.name ?? "无"}</div>
      <div class="metric-note">${best ? percent(best.evalScore) : "没有可用测评"}</div>
    </div>
    <div class="metric">
      <div class="metric-label">EvalSetVersion</div>
      <div class="metric-value">${state.evalVersion}</div>
      <div class="metric-note">${getEvalCases().length} 个 cases</div>
    </div>
    <div class="metric">
      <div class="metric-label">严重失败</div>
      <div class="metric-value">${criticalFailures.length}</div>
      <div class="metric-note">跨可运行 variants 统计</div>
    </div>
  `;

  renderCaseMatrix();

  qs("#evalCaseTable").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Case</th>
          <th>来源</th>
          <th>严重度</th>
          <th>权重</th>
          <th>期望行为</th>
        </tr>
      </thead>
      <tbody>
        ${cases
          .map(
            (item) => `
              <tr>
                <td>${item.title}</td>
                <td>${sourceLabel(item.source)}</td>
                <td>${severityLabel(item.severity)}</td>
                <td>${item.weight}</td>
                <td>${item.expectation}</td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function syncButtons() {
  qs("#convertBadcase").disabled = state.badCaseConverted;
  qs("#registerVariant").disabled = !state.badCaseConverted || state.variantCRegistered;
  qs("#runVariantC").disabled = !state.variantCRegistered || state.variantCRun;
}

function setView(view) {
  state.view = view;
  render();
}

function resetDemo() {
  state.view = "hub";
  state.requestedTags = ["codex"];
  state.evalVersion = "v1";
  state.rankingStrategy = "balanced";
  state.badCaseConverted = false;
  state.variantCRegistered = false;
  state.variantCRun = false;
  state.compareLeft = "variant-a";
  state.compareRight = "variant-b";
  state.selectedVariant = "variant-a";
  render();
}

document.addEventListener("click", (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) setView(nav.dataset.view);

  const openSkill = event.target.closest("[data-open-skill]");
  if (openSkill) {
    state.view = "skill";
    render();
  }

  const tagButton = event.target.closest("[data-tag]");
  if (tagButton) {
    const tag = tagButton.dataset.tag;
    if (state.requestedTags.includes(tag)) {
      state.requestedTags = state.requestedTags.filter((item) => item !== tag);
    } else {
      state.requestedTags = [...state.requestedTags, tag];
    }
    render();
  }

  const versionButton = event.target.closest("[data-version]");
  if (versionButton) {
    state.evalVersion = versionButton.dataset.version;
    render();
  }

  const compareButton = event.target.closest("[data-select-compare]");
  if (compareButton) {
    state.compareLeft = state.compareRight;
    state.compareRight = compareButton.dataset.selectCompare;
    render();
  }

  const variantNode = event.target.closest("[data-select-variant]");
  if (variantNode) {
    state.selectedVariant = variantNode.dataset.selectVariant;
    state.compareRight = state.selectedVariant;
    render();
  }

  const installButton = event.target.closest("[data-install]");
  if (installButton) {
    const variant = getVariants().find((item) => item.id === installButton.dataset.install);
    if (variant) {
      window.alert(`已选择安装 ${variant.name}。这是纯前端原型，不会写入本地系统。`);
    }
  }

  if (event.target.id === "compareBest") {
    const ranked = rankVariants().filter((item) => item.evalScore !== null);
    if (ranked.length >= 2) {
      state.compareLeft = ranked[1].variant.id;
      state.compareRight = ranked[0].variant.id;
      render();
    }
  }

  if (event.target.id === "convertBadcase") {
    state.badCaseConverted = true;
    state.evalVersion = "v2";
    state.view = "eval";
    render();
  }

  if (event.target.id === "registerVariant") {
    state.variantCRegistered = true;
    state.selectedVariant = "variant-c";
    state.compareLeft = "variant-a";
    state.compareRight = "variant-c";
    state.view = "skill";
    render();
  }

  if (event.target.id === "runVariantC") {
    state.variantCRun = true;
    state.evalVersion = "v2";
    state.selectedVariant = "variant-c";
    state.compareLeft = "variant-a";
    state.compareRight = "variant-c";
    state.view = "skill";
    render();
  }

  if (event.target.id === "resetDemo") resetDemo();
});

document.addEventListener("change", (event) => {
  if (event.target.id === "rankingStrategy") {
    state.rankingStrategy = event.target.value;
    render();
  }
  if (event.target.id === "compareLeft") {
    state.compareLeft = event.target.value;
    render();
  }
  if (event.target.id === "compareRight") {
    state.compareRight = event.target.value;
    render();
  }
});

qs("#installTop").addEventListener("click", () => {
  const best = rankVariants().find((item) => item.evalScore !== null);
  if (!best) return;
  window.alert(`已选择安装 ${best.variant.name}。这是纯前端原型，不会写入本地系统。`);
});

render();
