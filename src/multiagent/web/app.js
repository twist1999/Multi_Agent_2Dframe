const state = {
  prompt: "",
  outputs: {},
  currentView: "node_output",
  pollTimer: null,
  selectedIssue: null,
  benchmarkOutputs: {},
};

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function formatValue(value, asCode = false) {
  if (typeof value === "string") {
    return asCode ? value : value || "(empty)";
  }
  return JSON.stringify(value ?? {}, null, 2);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function highlightJson(text) {
  return escapeHtml(text).replace(
    /(&quot;(?:\\.|[^"\\])*&quot;)(\s*:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b/gi,
    (match, stringValue, colon, literal) => {
      if (stringValue) {
        const className = colon ? "token-key" : "token-string";
        return `<span class="${className}">${stringValue}</span>${colon || ""}`;
      }
      if (literal) {
        return `<span class="token-literal">${match}</span>`;
      }
      return `<span class="token-number">${match}</span>`;
    },
  );
}

function highlightPython(text) {
  const escaped = escapeHtml(text);
  return escaped.replace(
    /(#.*$)|(&quot;.*?&quot;|'.*?')|\b(def|class|return|import|from|for|in|if|else|elif|while|try|except|with|as|None|True|False)\b|\b([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()/gm,
    (match, comment, stringValue, keyword, callable) => {
      if (comment) {
        return `<span class="token-comment">${comment}</span>`;
      }
      if (stringValue) {
        return `<span class="token-string">${stringValue}</span>`;
      }
      if (keyword) {
        return `<span class="token-keyword">${keyword}</span>`;
      }
      if (callable) {
        return `<span class="token-function">${callable}</span>`;
      }
      return match;
    },
  );
}

function renderViewer() {
  const viewer = document.getElementById("viewer");
  const key = state.currentView;
  const isCode = key === "geometry_code" || key === "complete_code" || key === "pipeline_log";
  const formatted = formatValue(state.outputs[key], isCode);
  viewer.classList.toggle("code-viewer", isCode);
  if (isCode) {
    viewer.innerHTML = highlightPython(formatted);
  } else {
    viewer.innerHTML = highlightJson(formatted);
  }
}

function renderStages(stages) {
  const host = document.getElementById("stage-grid");
  host.innerHTML = "";
  const totalAgents = stages.reduce((sum, stage) => sum + (stage.agents || []).length, 0);
  const readyAgents = stages.reduce(
    (sum, stage) => sum + (stage.agents || []).filter((agent) => agent.status === "ready").length,
    0,
  );
  const percent = totalAgents ? Math.round((readyAgents / totalAgents) * 100) : 0;
  const progress = document.createElement("div");
  progress.className = "pipeline-progress";
  progress.innerHTML = `
    <div class="pipeline-progress-top">
      <span>${readyAgents}/${totalAgents} agents ready</span>
      <strong>${percent}%</strong>
    </div>
    <div class="pipeline-progress-track">
      <span style="width: ${percent}%"></span>
    </div>
  `;
  host.appendChild(progress);

  const rail = document.createElement("div");
  rail.className = "stage-rail";
  stages.forEach((stage, index) => {
    const agentsMarkup = (stage.agents || [])
      .map(
        (agent) => `
          <li class="agent-step agent-step-${agent.status}">
            <span class="agent-step-dot"></span>
            <span class="agent-name">${agent.name}</span>
          </li>
        `,
      )
      .join("");
    const stageReady = (stage.agents || []).filter((agent) => agent.status === "ready").length;
    const stageTotal = (stage.agents || []).length;
    const stagePercent = stageTotal ? Math.round((stageReady / stageTotal) * 100) : 0;
    const item = document.createElement("article");
    item.className = `stage-step stage-step-${stage.status}`;
    item.innerHTML = `
      <div class="stage-marker">
        <span>${index + 1}</span>
      </div>
      <div class="stage-step-body">
        <div class="stage-top">
          <div class="stage-title">${stage.title}</div>
          <span class="status status-${stage.status}">${stage.status}</span>
        </div>
        <div class="stage-mini-track">
          <span style="width: ${stagePercent}%"></span>
        </div>
        <ul class="agent-list">${agentsMarkup}</ul>
      </div>
    `;
    rail.appendChild(item);
  });
  host.appendChild(rail);
}

function hydrateState(payload) {
  state.prompt = payload.prompt || "";
  state.outputs = payload.outputs || {};
  document.getElementById("prompt-input").value = state.prompt;
  document.getElementById("prompt-source").textContent = `Source: ${payload.prompt_source || "unknown"}`;
  renderRun(payload.run || {});
  renderExecution(payload.execution || {}, payload.section_diagrams || {}, payload.outputs || {});
  renderVisualization(payload.outputs || {});
  renderStages(payload.stages || []);
  renderRL(payload.rl || {});
  renderPromptHistory(payload.rl?.prompt_history || []);
  renderBenchmark(payload.benchmark || {});
  renderViewer();
  renderSelectionPrompt();
  syncPolling(payload.run || {}, payload.execution || {}, payload.section_diagrams || {}, payload.benchmark || {});
}

function shortPrompt(prompt) {
  const compact = String(prompt || "").replace(/\s+/g, " ").trim();
  return compact.length > 180 ? `${compact.slice(0, 180)}...` : compact;
}

function renderPromptHistory(items) {
  const host = document.getElementById("prompt-history-list");
  host.innerHTML = "";
  if (!items.length) {
    host.innerHTML = `<div class="prompt-history-empty">No prompt history yet. Submit a prompt to create the first record.</div>`;
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("article");
    row.className = "prompt-history-item";
    const reward = item.total_reward === null || item.total_reward === undefined ? "pending" : Number(item.total_reward).toFixed(2);
    row.innerHTML = `
      <div class="prompt-history-top">
        <strong>${escapeHtml(item.status || "submitted")}</strong>
        <span>${escapeHtml(item.created_at || "")}</span>
      </div>
      <p>${escapeHtml(shortPrompt(item.prompt))}</p>
      <div class="prompt-history-meta">
        <span>Reward: ${escapeHtml(reward)}</span>
        <span>Error: ${escapeHtml(item.error_type || "none")}</span>
        <span>Policy: ${escapeHtml(item.policy_action || "pending")}</span>
      </div>
      <div class="actions prompt-history-actions">
        <button class="ghost use-history-prompt" type="button">Use Prompt</button>
        <button class="primary rerun-history-prompt" type="button">Run Again</button>
      </div>
    `;
    row.querySelector(".use-history-prompt").addEventListener("click", () => {
      document.getElementById("prompt-input").value = item.prompt || "";
      document.getElementById("submit-message").textContent = "Historical prompt loaded into the prompt box.";
    });
    row.querySelector(".rerun-history-prompt").addEventListener("click", () => {
      document.getElementById("prompt-input").value = item.prompt || "";
      submitPrompt(item.prompt || "").catch((error) => {
        document.getElementById("submit-message").textContent = error.message;
      });
    });
    host.appendChild(row);
  });
}

function renderRL(rl) {
  const reward = rl.reward || {};
  const action = rl.policy_action || {};
  document.getElementById("rl-total-reward").textContent = Number(reward.total_reward || 0).toFixed(2);
  document.getElementById("rl-error-type").textContent = reward.error_type || "none";
  document.getElementById("rl-policy-action").textContent =
    `${action.action_type || "observe_more"} -> ${action.target_agent || "orchestrator"}`;
  document.getElementById("rl-policy-reason").textContent = action.reason || "Waiting for more signals.";
  document.getElementById("rl-db-path").textContent = rl.database_path ? `SQLite: ${rl.database_path}` : "Reward database";

  const list = document.getElementById("rl-component-list");
  list.innerHTML = "";
  (reward.components || []).forEach((component) => {
    const value = Number(component.value || 0);
    const item = document.createElement("div");
    item.className = `rl-component ${value < 0 ? "negative" : value > 0 ? "positive" : "neutral"}`;
    item.innerHTML = `
      <span>${escapeHtml(component.name || "unknown")}</span>
      <strong>${value > 0 ? "+" : ""}${value.toFixed(2)}</strong>
      <small>${escapeHtml(component.reason || "")}</small>
    `;
    list.appendChild(item);
  });
  if (!list.children.length) {
    list.innerHTML = `<div class="rl-component neutral"><span>No reward components yet</span><strong>0.00</strong><small>Run the pipeline or save feedback.</small></div>`;
  }
}

function renderBenchmark(benchmark) {
  const status = benchmark.status || "idle";
  const statusNode = document.getElementById("benchmark-status");
  statusNode.textContent = status;
  statusNode.className = `run-status status-${status}`;
  const progress =
    benchmark.total && benchmark.total > 0 ? ` Progress: ${benchmark.completed || 0}/${benchmark.total}` : "";
  const batch = benchmark.batch_id ? ` Batch: ${benchmark.batch_id}` : "";
  const error = benchmark.error ? ` Error: ${benchmark.error}` : "";
  document.getElementById("benchmark-message").textContent =
    `${benchmark.message || "Ready to run benchmark cases."}${progress}${batch}${error}`;

  const button = document.getElementById("run-benchmark");
  button.disabled = status === "running";
  button.textContent = status === "running" ? "Running Benchmark..." : "Run 30 Prompt Cases";
  const retryButton = document.getElementById("retry-failed-benchmark");
  retryButton.disabled = status === "running";
  retryButton.textContent = status === "running" ? "Retry Waiting..." : "Retry Failed Cases";
  const reviewButton = document.getElementById("run-review-set");
  reviewButton.disabled = status === "running";
  reviewButton.textContent = status === "running" ? "Review Set Waiting..." : "Run Review Set";

  const host = document.getElementById("benchmark-case-list");
  host.innerHTML = "";
  const cases = benchmark.cases || [];
  if (!cases.length) {
    host.innerHTML = `<div class="prompt-history-empty">No benchmark cases yet. Click Run 30 Prompt Cases to start.</div>`;
    return;
  }
  cases.forEach((item) => {
    const row = document.createElement("article");
    row.className = "benchmark-case-item";
    row.innerHTML = `
      <div class="prompt-history-top">
        <strong>${escapeHtml(item.case_id || "")}</strong>
        <span>${escapeHtml(item.status || "pending")}</span>
      </div>
      <p class="benchmark-prompt-summary">${escapeHtml(shortPrompt(item.prompt))}</p>
      <details class="benchmark-full-prompt">
        <summary>Full Prompt</summary>
        <pre>${escapeHtml(item.prompt || "")}</pre>
      </details>
      <div class="prompt-history-meta">
        <span>Total tokens: ${Number(item.total_tokens || 0)}</span>
        <span>Prompt: ${Number(item.prompt_tokens || 0)}</span>
        <span>Completion: ${Number(item.completion_tokens || 0)}</span>
        <span>Reward: ${item.reward === null || item.reward === undefined ? "pending" : Number(item.reward).toFixed(2)}</span>
        <span>Review: ${escapeHtml(item.human_verdict || "unreviewed")}</span>
        ${item.retry_from_case_id ? `<span>Retry from: ${escapeHtml(item.retry_from_case_id)}</span>` : ""}
      </div>
      <textarea class="notes benchmark-review-notes" placeholder="Manual review notes...">${escapeHtml(item.human_notes || "")}</textarea>
      <div class="actions benchmark-actions">
        <button class="ghost view-benchmark-outputs" type="button">View Outputs</button>
        <button class="ghost view-benchmark-code" type="button">View Generated Code</button>
        <button class="ghost run-benchmark-code" type="button">Run Code</button>
        <button class="success mark-benchmark-correct" type="button">Correct</button>
        <button class="danger mark-benchmark-incorrect" type="button">Incorrect</button>
        <button class="ghost use-benchmark-prompt" type="button">Use Prompt</button>
        <button class="ghost copy-benchmark-prompt" type="button">Copy Prompt</button>
      </div>
      <div class="benchmark-code-run-panel"></div>
      <div class="benchmark-output-panel" data-case-output="${escapeHtml(item.case_id || "")}"></div>
    `;
    row.querySelector(".use-benchmark-prompt").addEventListener("click", () => {
      document.getElementById("prompt-input").value = item.prompt || "";
      document.getElementById("submit-message").textContent = "Benchmark prompt loaded into the prompt box.";
    });
    row.querySelector(".copy-benchmark-prompt").addEventListener("click", () => {
      navigator.clipboard.writeText(item.prompt || "").then(
        () => {
          document.getElementById("submit-message").textContent = "Full benchmark prompt copied.";
        },
        () => {
          document.getElementById("submit-message").textContent = "Clipboard copy failed. Use Full Prompt to select the text manually.";
        },
      );
    });
    row.querySelector(".view-benchmark-outputs").addEventListener("click", () => {
      toggleBenchmarkOutputs(row, item.case_id).catch((error) => {
        document.getElementById("feedback-message").textContent = error.message;
      });
    });
    row.querySelector(".view-benchmark-code").addEventListener("click", () => {
      toggleBenchmarkOutputs(row, item.case_id, "complete_code").catch((error) => {
        document.getElementById("feedback-message").textContent = error.message;
      });
    });
    row.querySelector(".run-benchmark-code").addEventListener("click", () => {
      runBenchmarkCode(row, item.case_id).catch((error) => {
        document.getElementById("feedback-message").textContent = error.message;
      });
    });
    row.querySelector(".mark-benchmark-correct").addEventListener("click", () => {
      reviewBenchmarkCase(item.case_id, "correct", row.querySelector(".benchmark-review-notes").value).catch((error) => {
        document.getElementById("feedback-message").textContent = error.message;
      });
    });
    row.querySelector(".mark-benchmark-incorrect").addEventListener("click", () => {
      reviewBenchmarkCase(item.case_id, "incorrect", row.querySelector(".benchmark-review-notes").value).catch((error) => {
        document.getElementById("feedback-message").textContent = error.message;
      });
    });
    host.appendChild(row);
  });
}

function renderBenchmarkCodeRun(panel, payload) {
  const status = payload.status || "unknown";
  const stdout = payload.stdout || "";
  const stderr = payload.stderr || "";
  panel.innerHTML = `
    <div class="benchmark-code-run-head">
      <strong>Generated Code Execution</strong>
      <span class="run-status status-${escapeHtml(status)}">${escapeHtml(status)}</span>
    </div>
    <div class="prompt-history-meta benchmark-code-run-meta">
      <span>Python: ${escapeHtml(payload.python_path || "unknown")}</span>
      <span>Return code: ${payload.returncode === null || payload.returncode === undefined ? "none" : Number(payload.returncode)}</span>
      <span>Started: ${escapeHtml(payload.started_at || "")}</span>
      <span>Finished: ${escapeHtml(payload.finished_at || "")}</span>
    </div>
    <p class="benchmark-code-run-message">${escapeHtml(payload.message || "")}</p>
    <div class="benchmark-code-run-grid">
      <div>
        <h4>stdout</h4>
        <pre class="viewer benchmark-code-run-log">${escapeHtml(stdout || "(empty)")}</pre>
      </div>
      <div>
        <h4>stderr</h4>
        <pre class="viewer benchmark-code-run-log">${escapeHtml(stderr || "(empty)")}</pre>
      </div>
    </div>
  `;
}

async function runBenchmarkCode(row, caseId) {
  const button = row.querySelector(".run-benchmark-code");
  const panel = row.querySelector(".benchmark-code-run-panel");
  button.disabled = true;
  button.textContent = "Running Code...";
  panel.innerHTML = `<div class="benchmark-output-empty">Running archived complete_code.py for ${escapeHtml(caseId)}...</div>`;
  try {
    const payload = await request("/api/run-benchmark-code", {
      method: "POST",
      body: JSON.stringify({ case_id: caseId }),
    });
    renderBenchmarkCodeRun(panel, payload);
    document.getElementById("feedback-message").textContent = payload.message || "Archived case code execution finished.";
  } finally {
    button.disabled = false;
    button.textContent = "Run Code";
  }
}

function formatBenchmarkArtifact(value) {
  if (typeof value === "string") {
    return value || "(empty)";
  }
  return JSON.stringify(value || {}, null, 2);
}

async function toggleBenchmarkOutputs(row, caseId, preferredArtifact = "node_output") {
  const panel = row.querySelector(".benchmark-output-panel");
  if (panel.dataset.open === "true") {
    if (panel.dataset.caseId === caseId && panel.dataset.activeArtifact !== preferredArtifact) {
      const targetTab = panel.querySelector(`[data-artifact="${preferredArtifact}"]`);
      if (targetTab) {
        targetTab.click();
        return;
      }
    }
    panel.dataset.open = "false";
    panel.dataset.caseId = "";
    panel.dataset.activeArtifact = "";
    panel.innerHTML = "";
    return;
  }
  panel.dataset.open = "true";
  panel.dataset.caseId = caseId;
  panel.innerHTML = `<div class="muted">Loading archived outputs...</div>`;
  const payload = await request(`/api/benchmark-case-artifacts?case_id=${encodeURIComponent(caseId)}`);
  if (!payload.available) {
    panel.innerHTML = `<div class="benchmark-output-empty">${escapeHtml(payload.message || "No archived outputs available.")}</div>`;
    return;
  }
  const outputs = payload.outputs || {};
  const hasCompleteCode = Boolean(String(outputs.complete_code || "").trim());
  const tabs = [
    ["complete_code", "Complete Code"],
    ["node_output", "Node"],
    ["element_output", "Element"],
    ["geometry_code", "Geometry Code"],
    ["load_output", "Loads"],
    ["compiled_model", "Compiled"],
    ["pipeline_log", "Pipeline Log"],
    ["debug_problem_analysis", "Debug Analysis"],
    ["debug_construction_plan", "Debug Plan"],
  ];
  panel.innerHTML = `
    <div class="benchmark-output-head">
      <div>
        <strong>Archived Outputs</strong>
        <small class="${hasCompleteCode ? "artifact-ok" : "artifact-missing"}">
          ${hasCompleteCode ? "Generated Python code is available." : "Generated Python code is missing for this case."}
        </small>
      </div>
      <span>${escapeHtml(payload.artifact_dir || "")}</span>
    </div>
    <div class="tabs benchmark-output-tabs">
      ${tabs.map(([key, label]) => `<button class="tab ${key === preferredArtifact ? "active" : ""}" data-artifact="${key}" type="button">${label}</button>`).join("")}
    </div>
    <pre class="viewer benchmark-output-viewer"></pre>
  `;
  const viewer = panel.querySelector(".benchmark-output-viewer");
  const renderArtifact = (key) => {
    panel.dataset.activeArtifact = key;
    const text = formatBenchmarkArtifact(outputs[key]);
    if (!String(text).trim() || text === "(empty)") {
      viewer.innerHTML = escapeHtml(
        key === "complete_code"
          ? "No complete_code.py was archived for this case. Failed cases may stop before CompleteCodeGenerator runs; rerun or retry the case after the latest checkpoint fixes to create generated Python code."
          : `No archived content found for ${key}.`,
      );
      return;
    }
    if (key.includes("code") || key.includes("log")) {
      viewer.innerHTML = key.includes("code") ? highlightPython(text) : escapeHtml(text);
    } else {
      viewer.innerHTML = highlightJson(text);
    }
  };
  renderArtifact(preferredArtifact);
  panel.querySelectorAll(".benchmark-output-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      panel.querySelectorAll(".benchmark-output-tabs .tab").forEach((candidate) => candidate.classList.remove("active"));
      tab.classList.add("active");
      renderArtifact(tab.dataset.artifact);
    });
  });
}

function renderRun(run) {
  const status = run.status || "idle";
  const statusNode = document.getElementById("run-status");
  statusNode.textContent = status;
  statusNode.className = `run-status status-${status}`;

  const startedAt = run.started_at ? ` Started: ${run.started_at}` : "";
  const finishedAt = run.finished_at ? ` Finished: ${run.finished_at}` : "";
  const error = run.error ? ` Error: ${run.error}` : "";
  document.getElementById("run-message").textContent = `${run.message || "Ready to run."}${startedAt}${finishedAt}${error}`;

  const submitButton = document.getElementById("submit-prompt");
  submitButton.disabled = status === "running";
  submitButton.textContent = status === "running" ? "Running…" : "Run Pipeline";

}

function renderExecution(execution, sectionDiagrams, outputs) {
  const status = execution.status || "idle";
  const statusNode = document.getElementById("execution-status");
  statusNode.textContent = status;
  statusNode.className = `run-status status-${status}`;

  const pythonPath = execution.python_path ? ` Python: ${execution.python_path}` : "";
  const startedAt = execution.started_at ? ` Started: ${execution.started_at}` : "";
  const finishedAt = execution.finished_at ? ` Finished: ${execution.finished_at}` : "";
  const error = execution.error ? ` Error: ${execution.error}` : "";
  document.getElementById("execution-message").textContent =
    `${execution.message || "Ready to execute generated code."}${pythonPath}${startedAt}${finishedAt}${error}`;

  const runButton = document.getElementById("run-generated-code");
  runButton.disabled = status === "running";
  runButton.textContent = status === "running" ? "Executing…" : "Run Generated Code";

  document.getElementById("execution-stdout").textContent = outputs.execution_stdout || "(empty)";
  document.getElementById("execution-stderr").textContent = outputs.execution_stderr || "(empty)";
  document.getElementById("python-check-viewer").textContent =
    JSON.stringify(outputs.python_check_output || {}, null, 2) || "(empty)";

  renderSectionDiagrams(sectionDiagrams, outputs);

}

function syncPolling(run, execution, sectionDiagrams, benchmark = {}) {
  const shouldPoll =
    (run.status || "idle") === "running" ||
    (execution.status || "idle") === "running" ||
    (sectionDiagrams.status || "idle") === "running" ||
    (benchmark.status || "idle") === "running";
  if (shouldPoll) {
    startPolling();
  } else {
    stopPolling();
  }
}

function renderSectionDiagrams(sectionDiagrams, outputs) {
  const status = sectionDiagrams.status || "idle";
  const statusNode = document.getElementById("opsvis-status");
  statusNode.textContent = status;
  statusNode.className = `run-status status-${status}`;

  const pythonPath = sectionDiagrams.python_path ? ` Python: ${sectionDiagrams.python_path}` : "";
  const startedAt = sectionDiagrams.started_at ? ` Started: ${sectionDiagrams.started_at}` : "";
  const finishedAt = sectionDiagrams.finished_at ? ` Finished: ${sectionDiagrams.finished_at}` : "";
  const error = sectionDiagrams.error ? ` Error: ${sectionDiagrams.error}` : "";
  document.getElementById("opsvis-message").textContent =
    `${sectionDiagrams.message || "Run generated code to render section-force diagrams."}${pythonPath}${startedAt}${finishedAt}${error}`;

  [
    ["axial", sectionDiagrams.axial_image_url],
    ["shear", sectionDiagrams.shear_image_url],
    ["moment", sectionDiagrams.moment_image_url],
  ].forEach(([prefix, url]) => {
    const image = document.getElementById(`${prefix}-diagram-image`);
    const empty = document.getElementById(`${prefix}-diagram-empty`);
    if (url) {
      image.src = url;
      image.style.display = "block";
      empty.style.display = "none";
    } else {
      image.removeAttribute("src");
      image.style.display = "none";
      empty.style.display = "block";
    }
  });

  if (status === "failed" && outputs.section_diagram_stderr) {
    document.getElementById("opsvis-message").textContent += ` Details: ${outputs.section_diagram_stderr.trim()}`;
  }
}

function extractNodes(nodeOutput, elementOutput) {
  const map = new Map();
  if (Array.isArray(nodeOutput.nodes)) {
    nodeOutput.nodes.forEach((item) => {
      const id = Number(item.id ?? item.node_id);
      const x = Number(item.x ?? item.x_m ?? item.coordinates?.[0]);
      const y = Number(item.y ?? item.y_m ?? item.coordinates?.[1]);
      if (Number.isFinite(id) && Number.isFinite(x) && Number.isFinite(y)) {
        map.set(id, { id, x, y, raw: item });
      }
    });
  }
  if (Array.isArray(nodeOutput.construction_sequence)) {
    nodeOutput.construction_sequence.forEach((step) => {
      (step.nodes_added || []).forEach((item) => {
        const id = Number(item.id ?? item.node_id);
        const x = Number(item.x ?? item.x_m ?? item.coordinates?.[0]);
        const y = Number(item.y ?? item.y_m ?? item.coordinates?.[1]);
        if (Number.isFinite(id) && Number.isFinite(x) && Number.isFinite(y)) {
          map.set(id, { id, x, y, raw: item });
        }
      });
    });
  }
  if (Array.isArray(elementOutput.nodes)) {
    elementOutput.nodes.forEach((item) => {
      const id = Number(item.id ?? item.node_id);
      const x = Number(item.x ?? item.x_m ?? item.coordinates?.[0]);
      const y = Number(item.y ?? item.y_m ?? item.coordinates?.[1]);
      if (Number.isFinite(id) && Number.isFinite(x) && Number.isFinite(y)) {
        map.set(id, { id, x, y, raw: item });
      }
    });
  }
  return Array.from(map.values()).sort((a, b) => a.id - b.id);
}

function normalizeElement(item) {
  let node1 = Number(item.node1 ?? item.i_node ?? item.iNode);
  let node2 = Number(item.node2 ?? item.j_node ?? item.jNode);
  if (!Number.isFinite(node1) || !Number.isFinite(node2)) {
    const pair = item.nodes;
    if (Array.isArray(pair) && pair.length === 2) {
      node1 = Number(pair[0]);
      node2 = Number(pair[1]);
    }
  }
  if (!Number.isFinite(node1) || !Number.isFinite(node2)) {
    const rawI = String(item.node_i || "").replace("N", "");
    const rawJ = String(item.node_j || "").replace("N", "");
    if (/^\d+$/.test(rawI) && /^\d+$/.test(rawJ)) {
      node1 = Number(rawI);
      node2 = Number(rawJ);
    }
  }
  return {
    id: Number(item.element_id ?? item.id),
    node1,
    node2,
    type: item.type || item.element_type || "",
    raw: item,
  };
}

function extractElements(elementOutput) {
  const elements = [];
  if (Array.isArray(elementOutput.elements)) {
    elementOutput.elements.forEach((item) => elements.push(normalizeElement(item)));
  }
  if (Array.isArray(elementOutput.element_definitions)) {
    elementOutput.element_definitions.forEach((item) => elements.push(normalizeElement(item)));
  }
  if (Array.isArray(elementOutput.steps)) {
    elementOutput.steps.forEach((step) => {
      (step.elements_added || []).forEach((item) => elements.push(normalizeElement(item)));
    });
  }
  return elements.filter((item) => Number.isFinite(item.id));
}

function projectPoint(node, bounds, width, height, padding) {
  const spanX = Math.max(bounds.maxX - bounds.minX, 1);
  const spanY = Math.max(bounds.maxY - bounds.minY, 1);
  const usableW = width - padding * 2;
  const usableH = height - padding * 2;
  const scale = Math.min(usableW / spanX, usableH / spanY);
  const offsetX = (width - spanX * scale) / 2;
  const offsetY = (height - spanY * scale) / 2;
  return {
    x: offsetX + (node.x - bounds.minX) * scale,
    y: height - (offsetY + (node.y - bounds.minY) * scale),
  };
}

function createSvgNode(name, attributes = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => {
    node.setAttribute(key, String(value));
  });
  return node;
}

function selectIssue(kind, payload) {
  state.selectedIssue = { kind, payload };
  renderSelectionPrompt();
  renderVisualization(state.outputs || {});
}

function buildSelectionPrompt() {
  if (!state.selectedIssue) {
    return "";
  }
  const originalPrompt = state.prompt || document.getElementById("prompt-input").value.trim();
  if (state.selectedIssue.kind === "node") {
    const node = state.selectedIssue.payload;
    return [
      "You are rerunning the Node Agent for a structural frame model.",
      "",
      "Original user request:",
      originalPrompt,
      "",
      `A reviewer clicked node ${node.id} in the visualization and marked it as incorrect.`,
      "Selected node record:",
      JSON.stringify(node.raw ?? node, null, 2),
      "",
      "Please re-check this node against the frame geometry, story progression, bay spacing, support conditions, and neighboring elements.",
      "If the node is wrong, regenerate a corrected node-output JSON for the full node set while preserving valid nodes when possible.",
      "Return structured JSON only and keep the current node-output schema consistent.",
    ].join("\n");
  }
  const element = state.selectedIssue.payload;
  const relatedNodes = extractNodes(state.outputs.node_output || {}, state.outputs.element_output || {})
    .filter((item) => item.id === element.node1 || item.id === element.node2)
    .map((item) => item.raw ?? item);
  return [
    "You are rerunning the Element Agent for a structural frame model.",
    "",
    "Original user request:",
    originalPrompt,
    "",
    `A reviewer clicked element ${element.id} in the visualization and marked it as incorrect.`,
    "Selected element record:",
    JSON.stringify(element.raw ?? element, null, 2),
    "",
    "Connected node records:",
    JSON.stringify(relatedNodes, null, 2),
    "",
    "Please re-check this element against the frame topology, intended member type, node connectivity, orientation, and story/bay placement.",
    "If the element is wrong, regenerate a corrected element-output JSON for the full element set while preserving valid members when possible.",
    "Return structured JSON only and keep the current element-output schema consistent.",
  ].join("\n");
}

function renderSelectionPrompt() {
  const promptBox = document.getElementById("selection-prompt");
  const message = document.getElementById("selection-message");
  const prompt = buildSelectionPrompt();
  promptBox.value = prompt;
  if (!state.selectedIssue) {
    message.textContent = "Click a node or element on the right to generate a targeted reanalysis prompt.";
    return;
  }
  if (state.selectedIssue.kind === "node") {
    message.textContent = `Node ${state.selectedIssue.payload.id} selected. Send this targeted prompt back to the Node Agent for reanalysis.`;
  } else {
    message.textContent = `Element ${state.selectedIssue.payload.id} selected. Send this targeted prompt back to the Element Agent for reanalysis.`;
  }
}

function renderVisualization(outputs) {
  const nodeSvg = document.getElementById("node-visualization-svg");
  const nodeEmpty = document.getElementById("node-visualization-empty");
  const elementSvg = document.getElementById("element-visualization-svg");
  const elementEmpty = document.getElementById("element-visualization-empty");
  const nodes = extractNodes(outputs.node_output || {}, outputs.element_output || {});
  const elements = extractElements(outputs.element_output || {});

  nodeSvg.innerHTML = "";
  elementSvg.innerHTML = "";

  if (!nodes.length) {
    nodeSvg.style.display = "none";
    nodeEmpty.style.display = "block";
    elementSvg.style.display = "none";
    elementEmpty.style.display = "block";
    return;
  }

  const bounds = {
    minX: Math.min(...nodes.map((n) => n.x)),
    maxX: Math.max(...nodes.map((n) => n.x)),
    minY: Math.min(...nodes.map((n) => n.y)),
    maxY: Math.max(...nodes.map((n) => n.y)),
  };
  const width = 100;
  const height = 100;
  const padding = 10;
  const projected = new Map(
    nodes.map((node) => [node.id, projectPoint(node, bounds, width, height, padding)]),
  );

  nodes.forEach((node) => {
    const point = projected.get(node.id);
    const circle = createSvgNode("circle", {
      cx: point.x,
      cy: point.y,
      r: 2.3,
      fill: "#0f766e",
      class: `node-point${state.selectedIssue?.kind === "node" && state.selectedIssue.payload.id === node.id ? " selected" : ""}`,
    });
    circle.addEventListener("click", () => selectIssue("node", node));
    const label = createSvgNode("text", {
      x: point.x + 2.5,
      y: point.y - 2.5,
      "font-size": 4,
      fill: "#16313a",
    });
    label.textContent = String(node.id);
    label.addEventListener("click", () => selectIssue("node", node));
    nodeSvg.appendChild(circle);
    nodeSvg.appendChild(label);
  });
  nodeSvg.style.display = "block";
  nodeEmpty.style.display = "none";

  if (!elements.length) {
    elementSvg.style.display = "none";
    elementEmpty.style.display = "block";
    return;
  }

  elements.forEach((item) => {
    if (!Number.isFinite(item.node1) || !Number.isFinite(item.node2)) {
      return;
    }
    const start = projected.get(item.node1);
    const end = projected.get(item.node2);
    if (!start || !end) {
      return;
    }
    const line = createSvgNode("line", {
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      stroke: "#e58b2a",
      "stroke-width": 1.8,
      class: `element-line${state.selectedIssue?.kind === "element" && state.selectedIssue.payload.id === item.id ? " selected" : ""}`,
    });
    const hitbox = createSvgNode("line", {
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      class: "element-hitbox",
    });
    const mx = (start.x + end.x) / 2;
    const my = (start.y + end.y) / 2;
    const label = createSvgNode("text", {
      x: mx + 1.5,
      y: my - 1.5,
      "font-size": 3.2,
      fill: "#16313a",
    });
    label.textContent = String(item.id);
    const choose = () => selectIssue("element", item);
    line.addEventListener("click", choose);
    hitbox.addEventListener("click", choose);
    label.addEventListener("click", choose);
    elementSvg.appendChild(line);
    elementSvg.appendChild(hitbox);
    elementSvg.appendChild(label);
  });
  elementSvg.style.display = "block";
  elementEmpty.style.display = "none";
}

async function loadState() {
  document.getElementById("submit-message").textContent = "Loading workspace snapshot...";
  const payload = await request("/api/state");
  hydrateState(payload);
  document.getElementById("submit-message").textContent = "Workspace outputs loaded.";
}

async function submitPrompt(promptOverride = null) {
  const prompt = (promptOverride ?? document.getElementById("prompt-input").value).trim();
  const payload = await request("/api/submit", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("submit-message").textContent = payload.message;
}

function startPolling() {
  if (state.pollTimer) {
    return;
  }
  state.pollTimer = window.setInterval(() => {
    loadState().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
      stopPolling();
    });
  }, 2500);
}

function stopPolling() {
  if (!state.pollTimer) {
    return;
  }
  window.clearInterval(state.pollTimer);
  state.pollTimer = null;
}

async function sendFeedback(verdict) {
  const payload = await request("/api/feedback", {
    method: "POST",
    body: JSON.stringify({
      prompt: document.getElementById("prompt-input").value.trim(),
      verdict,
      notes: document.getElementById("feedback-notes").value.trim(),
      selected_object: state.selectedIssue || null,
    }),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("feedback-message").textContent = payload.message;
}

async function runGeneratedCode() {
  const payload = await request("/api/run-generated-code", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("feedback-message").textContent = payload.message;
}

async function runBenchmark() {
  const payload = await request("/api/run-benchmark", {
    method: "POST",
    body: JSON.stringify({ count: 30, seed: 20260506 }),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("submit-message").textContent = payload.message;
}

async function retryFailedBenchmark() {
  const payload = await request("/api/retry-failed-benchmark", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("submit-message").textContent = payload.message;
}

async function runReviewSet() {
  const payload = await request("/api/run-review-set", {
    method: "POST",
    body: JSON.stringify({}),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("submit-message").textContent = payload.message;
}

async function reviewBenchmarkCase(caseId, verdict, notes) {
  const payload = await request("/api/review-benchmark", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId, verdict, notes }),
  });
  if (payload.state) {
    hydrateState(payload.state);
  }
  document.getElementById("feedback-message").textContent = payload.message;
}

function bindEvents() {
  document.getElementById("submit-prompt").addEventListener("click", () => {
    submitPrompt().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
    });
  });

  document.getElementById("reload-state").addEventListener("click", () => {
    loadState().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
    });
  });

  document.getElementById("mark-correct").addEventListener("click", () => {
    sendFeedback("correct").catch((error) => {
      document.getElementById("feedback-message").textContent = error.message;
    });
  });

  document.getElementById("mark-incorrect").addEventListener("click", () => {
    sendFeedback("incorrect").catch((error) => {
      document.getElementById("feedback-message").textContent = error.message;
    });
  });

  document.getElementById("run-generated-code").addEventListener("click", () => {
    runGeneratedCode().catch((error) => {
      document.getElementById("feedback-message").textContent = error.message;
    });
  });

  document.getElementById("run-benchmark").addEventListener("click", () => {
    runBenchmark().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
    });
  });

  document.getElementById("retry-failed-benchmark").addEventListener("click", () => {
    retryFailedBenchmark().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
    });
  });

  document.getElementById("run-review-set").addEventListener("click", () => {
    runReviewSet().catch((error) => {
      document.getElementById("submit-message").textContent = error.message;
    });
  });

  document.getElementById("use-selection-prompt").addEventListener("click", () => {
    const prompt = buildSelectionPrompt();
    if (!prompt) {
      document.getElementById("selection-message").textContent = "Select a node or element before generating a reanalysis prompt.";
      return;
    }
    document.getElementById("prompt-input").value = prompt;
    document.getElementById("selection-message").textContent = "The targeted reanalysis prompt has been copied to the prompt box.";
  });

  document.getElementById("run-selection-reanalysis").addEventListener("click", () => {
    const prompt = buildSelectionPrompt();
    if (!prompt) {
      document.getElementById("selection-message").textContent = "Select a node or element before running reanalysis.";
      return;
    }
    document.getElementById("prompt-input").value = prompt;
    submitPrompt(prompt).catch((error) => {
      document.getElementById("selection-message").textContent = error.message;
    });
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((candidate) => {
        candidate.classList.remove("active");
      });
      tab.classList.add("active");
      state.currentView = tab.dataset.view;
      renderViewer();
    });
  });
}

bindEvents();
loadState().catch((error) => {
  document.getElementById("submit-message").textContent = error.message;
});
