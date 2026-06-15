import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const tabs = ["Current State", "Import + Pipeline", "Actions", "Risk Recommendations"];

function formatBadgeValue(value) {
  const number = Number(value || 0);
  if (number > 99) return "99+";
  return number.toLocaleString();
}

async function api(path, options = {}, timeoutMs = 25000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const method = options.method || "GET";
  const response = await fetch(path, {
    cache: method === "GET" ? "no-store" : "default",
    ...options,
    headers: {
      ...(method === "GET" ? { "Cache-Control": "no-cache" } : {}),
      ...(options.headers || {}),
    },
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function Metric({ label, value, detail, tone = "neutral", onClick }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag className={`metric metric-${tone} ${onClick ? "metric-clickable" : ""}`} onClick={onClick}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </Tag>
  );
}

function ScoreBar({ label, value }) {
  return (
    <div className="score-row">
      <div className="score-label">
        <span>{label}</span>
        <b>{value}%</b>
      </div>
      <div className="bar">
        <div style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

function renderMarkdown(markdown) {
  const blocks = [];
  let listItems = [];
  const flushList = () => {
    if (listItems.length) {
      blocks.push(
        <ul key={`list-${blocks.length}`}>
          {listItems.map((item, index) => (
            <li key={index}>{renderInlineMarkdown(item)}</li>
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  markdown.split(/\r?\n/).forEach((rawLine, index) => {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      return;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      listItems.push(line.slice(2));
      return;
    }
    flushList();
    if (line.startsWith("### ")) {
      blocks.push(<h4 key={index}>{renderInlineMarkdown(line.slice(4))}</h4>);
    } else if (line.startsWith("## ")) {
      blocks.push(<h3 key={index}>{renderInlineMarkdown(line.slice(3))}</h3>);
    } else if (line.startsWith("# ")) {
      blocks.push(<h2 key={index}>{renderInlineMarkdown(line.slice(2))}</h2>);
    } else {
      blocks.push(<p key={index}>{renderInlineMarkdown(line)}</p>);
    }
  });
  flushList();
  return blocks;
}

function renderInlineMarkdown(text) {
  return text.split(/(#[A-Za-z][A-Za-z0-9_-]*)/g).map((part, index) => {
    if (part.startsWith("#")) {
      return (
        <span className="inline-tag" key={index}>
          {part}
        </span>
      );
    }
    return part;
  });
}

function DataTable({ rows, columns, onRowClick, selectedId, sort, onSort }) {
  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>
                {onSort ? (
                  <button className="sort-header" onClick={() => onSort(column.key)}>
                    <span>{column.label}</span>
                    <span>{sort?.key === column.key ? (sort.direction === "asc" ? "↑" : "↓") : ""}</span>
                  </button>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="empty-cell">
                No rows for this view.
              </td>
            </tr>
          ) : (
            rows.map((row, index) => {
              const id = row.action_id || row.location || row.name || index;
              return (
                <tr
                  key={id}
                  className={selectedId === id ? "selected" : ""}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((column) => (
                    <td key={column.key}>{column.render ? column.render(row) : String(row[column.key] ?? "")}</td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

function readinessFlagTone(flag) {
  const normalized = String(flag || "").toLowerCase();
  if (normalized.includes("missing") || normalized.includes("sparse")) return "risk";
  if (normalized.includes("cluster")) return "muted";
  return "info";
}

function ReadinessFlags({ value }) {
  const flags = String(value || "ok")
    .split(",")
    .map((flag) => flag.trim())
    .filter(Boolean);

  return (
    <div className="readiness-flags">
      {flags.map((flag) => (
        <span className={`readiness-flag readiness-${readinessFlagTone(flag)}`} key={flag}>
          {flag}
        </span>
      ))}
    </div>
  );
}

function CurrentState({ state, onActionJump }) {
  const profile = state.run.profile;
  const components = profile.score_components || {};
  const previewColumns = [
    { key: "name", label: "Facility" },
    { key: "address_city", label: "City" },
    { key: "address_stateOrRegion", label: "State" },
    { key: "address_zipOrPostcode", label: "PIN" },
    { key: "organization_type", label: "Type" },
    { key: "readiness_flags", label: "Readiness flags", render: (row) => <ReadinessFlags value={row.readiness_flags} /> }
  ];
  const [previewSearch, setPreviewSearch] = useState("");
  const [previewSort, setPreviewSort] = useState({ key: "name", direction: "asc" });
  const previewRows = useMemo(() => {
    const search = previewSearch.trim().toLowerCase();
    const filtered = search
      ? state.preview.filter((row) =>
          previewColumns.some((column) =>
            String(row[column.key] ?? "")
              .toLowerCase()
              .includes(search)
          )
        )
      : [...state.preview];
    filtered.sort((left, right) => {
      const leftValue = String(left[previewSort.key] ?? "").toLowerCase();
      const rightValue = String(right[previewSort.key] ?? "").toLowerCase();
      const comparison = leftValue.localeCompare(rightValue, undefined, { numeric: true });
      return previewSort.direction === "asc" ? comparison : -comparison;
    });
    return filtered;
  }, [state.preview, previewSearch, previewSort]);

  function togglePreviewSort(key) {
    setPreviewSort((current) => ({
      key,
      direction: current.key === key && current.direction === "asc" ? "desc" : "asc"
    }));
  }

  return (
    <section className="page-grid">
      <div className="full">
        <div className="metric-grid">
          <Metric
            label="Data consistency"
            value={`${profile.consistency_score}%`}
            detail={`+${profile.expected_lift} pts possible · open all actions`}
            tone="warn"
            onClick={() => onActionJump({ issue: "All", status: "All", owner: "All" })}
          />
          <Metric
            label="Facilities"
            value={profile.row_count.toLocaleString()}
            detail="open readiness actions"
            onClick={() => onActionJump({ issue: "All", status: "All", owner: "All" })}
          />
          <Metric
            label="Duplicate clusters"
            value={profile.duplicate_clusters.toLocaleString()}
            detail="open dedupe recommendations"
            onClick={() => onActionJump({ issue: "Duplicate cluster", status: "All", owner: "All" })}
          />
          <Metric
            label="Human review"
            value={profile.human_review_queue.toLocaleString()}
            detail="open human queue"
            tone="risk"
            onClick={() => onActionJump({ issue: "All", status: "Needs review", owner: "Human" })}
          />
        </div>
      </div>

      <div className="panel current-numbers">
        <div className="panel-head">
          <div>
            <h2>Mission Control</h2>
            <p>Executive summary for the current source/resulting state.</p>
          </div>
        </div>
        <p className="dataset-path">{state.catalog}.{state.schema}.{state.table}</p>
        <div className="mini-grid">
          <Metric label="States" value={profile.state_count.toLocaleString()} />
          <Metric label="Cities" value={profile.city_count.toLocaleString()} />
          <Metric label="Sparse locations" value={profile.sparse_locations.toLocaleString()} />
        </div>
        <div className="score-list">
          {Object.entries(components).map(([label, value]) => (
            <ScoreBar key={label} label={label} value={value} />
          ))}
        </div>
        <div className="tag-line">
          {(profile.tags || []).length ? profile.tags.map((tag) => <span key={tag}>#{tag}</span>) : <span>No tags yet</span>}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>What This Means</h2>
            <p>These numbers are navigation into the work queue, not passive KPIs.</p>
          </div>
        </div>
        <div className="callout-list">
          <button onClick={() => onActionJump({ issue: "Duplicate cluster", status: "All", owner: "All" })}>
            Dedupe recommendations affect facility counts and coverage.
          </button>
          <button onClick={() => onActionJump({ issue: "Location quality", status: "All", owner: "All" })}>
            Sparse or weak locations reduce planning confidence.
          </button>
          <button onClick={() => onActionJump({ issue: "NICU review", status: "All", owner: "Human" })}>
            Clinical claims need evidence before planners trust them.
          </button>
        </div>
      </div>

      <div className="panel full">
        <div className="panel-head">
          <div>
            <h2>Dataset Preview</h2>
            <p>
              Showing {previewRows.length.toLocaleString()} preview rows from {profile.row_count.toLocaleString()} loaded facility records.
            </p>
          </div>
          <div className="preview-controls">
            <input
              type="search"
              value={previewSearch}
              onChange={(event) => setPreviewSearch(event.target.value)}
              placeholder="Search preview"
            />
            <select
              value={previewSort.key}
              onChange={(event) => setPreviewSort({ ...previewSort, key: event.target.value })}
            >
              {previewColumns.map((column) => (
                <option key={column.key} value={column.key}>
                  Order by {column.label}
                </option>
              ))}
            </select>
            <button onClick={() => setPreviewSort({ ...previewSort, direction: previewSort.direction === "asc" ? "desc" : "asc" })}>
              {previewSort.direction === "asc" ? "Asc" : "Desc"}
            </button>
          </div>
        </div>
        <DataTable
          rows={previewRows}
          columns={previewColumns}
          sort={previewSort}
          onSort={togglePreviewSort}
        />
      </div>
    </section>
  );
}

const AGENT_NAMES = ["ingestion", "qa", "dedup", "evidence", "geo", "shortage", "review", "risk"];
const AGENT_LABELS = {
  ingestion: "Ingest",
  qa: "QA profile",
  dedup: "De-dup",
  evidence: "Evidence",
  geo: "Geo filter",
  shortage: "Shortage",
  review: "Review gate",
  risk: "Risk synthesis"
};
const STATUS_TONE = { completed: "ok", failed: "risk", running: "warn", pending: "neutral", idle: "neutral" };

function AgentCard({ name, agentState }) {
  const status = agentState?.status || "pending";
  const tone = STATUS_TONE[status] || "neutral";
  const result = agentState?.result || {};
  return (
    <div className={`agent-card agent-${tone}`}>
      <div className="agent-header">
        <b>{AGENT_LABELS[name]}</b>
        <span className={`badge badge-${tone}`}>{status}</span>
      </div>
      {agentState?.error ? <p className="agent-error">{agentState.error}</p> : null}
      {status === "completed" && name === "ingestion" && result.summary ? (
        <p className="agent-detail">
          {result.incoming_count ?? 0} incoming · route: {result.route || "qa_ready"}
        </p>
      ) : null}
      {status === "completed" && name === "qa" && result.summary ? (
        <p className="agent-detail">
          Quality: {result.overall_quality_score ?? "—"}% · {result.summary.flag_count ?? 0} flags
        </p>
      ) : null}
      {status === "completed" && name === "dedup" && result.mode === "ingest" && result.summary ? (
        <p className="agent-detail">
          {result.summary.insert_count ?? 0} insert · {result.summary.update_count ?? 0} update · {result.summary.duplicate_count ?? 0} dup · {result.summary.review_count ?? 0} review
        </p>
      ) : null}
      {status === "completed" && name === "dedup" && result.mode !== "ingest" && result.summary ? (
        <p className="agent-detail">
          {result.summary.merge_count ?? "—"} merges · {result.summary.split_count ?? "—"} splits
        </p>
      ) : null}
      {status === "completed" && name === "geo" && result.summary ? (
        <p className="agent-detail">
          {result.flagged_records?.length ?? 0} flagged · {result.coverage_gaps?.length ?? 0} gaps
        </p>
      ) : null}
      {status === "completed" && name === "evidence" && result.summary ? (
        <p className="agent-detail">
          {result.summary.review_claims ?? 0} claims for review
        </p>
      ) : null}
      {status === "completed" && name === "shortage" && result.summary ? (
        <p className="agent-detail">
          {result.shortage_areas?.filter((a) => a.severity === "critical").length ?? 0} critical areas
        </p>
      ) : null}
      {status === "completed" && name === "review" && result.summary ? (
        <p className="agent-detail">
          {result.summary.review_count ?? 0} review items · impact {result.summary.material_planning_impact_score ?? 0}
        </p>
      ) : null}
      {status === "completed" && name === "risk" ? (
        <p className="agent-detail">
          Data readiness: {result.data_readiness_score ?? "—"}% · Planning: {result.planning_readiness_score ?? "—"}%
        </p>
      ) : null}
    </div>
  );
}

function PipelinePanel({ pipeline, onStart, busy, ingestRecords }) {
  const status = pipeline?.status || "idle";
  const agents = pipeline?.agents || {};
  const riskResult = agents.risk?.result || {};
  const tone = STATUS_TONE[status] || "neutral";
  const isRunning = status === "running";
  const pipelineMode = pipeline?.mode || "analysis";

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>AI Pipeline</h2>
          <p>
            {ingestRecords
              ? `Ingest mode: ${ingestRecords.length} incoming records → QA → Dedupe/Evidence/Geo → Shortage → Review → Risk.`
              : "Analysis mode: Ingest → QA → Dedupe/Evidence/Geo → Shortage → Review → Risk."}
            {pipeline?.pipeline_id ? <span className="run-id"> Run: {pipeline.pipeline_id}</span> : null}
            {pipeline?.mode ? <span className="run-id"> [{pipeline.mode}]</span> : null}
          </p>
        </div>
        <div className="button-row">
          <span className={`badge badge-${tone}`}>{status}</span>
          {ingestRecords ? (
            <button className="primary" onClick={() => onStart(ingestRecords)} disabled={busy || isRunning}>
              {isRunning ? "Running…" : `Run ingestion (${ingestRecords.length} records)`}
            </button>
          ) : null}
          <button onClick={() => onStart(null)} disabled={busy || isRunning}>
            {isRunning ? "Running…" : "Run analysis"}
          </button>
        </div>
      </div>

      <div className="agent-grid">
        {AGENT_NAMES.map((name) => (
          <AgentCard key={name} name={name} agentState={agents[name]} />
        ))}
      </div>

      {status === "completed" && riskResult.executive_summary ? (
        <div className="risk-summary">
          <h3>Executive Summary</h3>
          <p>{riskResult.executive_summary}</p>
          {riskResult.top_3_priorities?.length ? (
            <ul>
              {riskResult.top_3_priorities.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}

      {status === "failed" ? (
        <div className="error">Pipeline failed. Check server logs or retry.</div>
      ) : null}
    </div>
  );
}

function ImportPipeline({ scratchpad, setScratchpad, onSaveScratchpad, onReparse, busy, pipeline, onPipelineStart, pipelineBusy }) {
  const [upload, setUpload] = useState(null);
  const [uploadError, setUploadError] = useState("");
  const [uploadPreview, setUploadPreview] = useState(null);
  const [scratchpadMode, setScratchpadMode] = useState("view");

  async function previewUpload(file) {
    setUpload(file);
    setUploadError("");
    setUploadPreview(null);
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const result = await api("/api/import/preview", { method: "POST", body: formData });
      setUploadPreview(result);
    } catch (error) {
      setUploadError(error.message);
    }
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>Import</h2>
            <p>Stage XLS, XLSX, or CSV before it touches trusted tables.</p>
          </div>
        </div>
        <label className="dropzone">
          <input type="file" accept=".csv,.xls,.xlsx" onChange={(event) => previewUpload(event.target.files?.[0] || null)} />
          <span>{upload ? upload.name : "Drop or choose a facility file"}</span>
        </label>
        {uploadError ? <div className="error">{uploadError}</div> : null}
        {uploadPreview ? (
          <div className="import-summary">
            <Metric label="Parsed rows" value={uploadPreview.row_count.toLocaleString()} />
            <Metric label="Import readiness" value={`${uploadPreview.import_readiness}%`} />
            <Metric label="Columns" value={uploadPreview.columns.length.toLocaleString()} />
          </div>
        ) : null}
      </div>

      <PipelinePanel
        pipeline={pipeline}
        onStart={onPipelineStart}
        busy={pipelineBusy}
        ingestRecords={uploadPreview?.preview || null}
      />

      <div className="panel scratchpad full">
        <div className="panel-head">
          <div>
            <h2>Scratchpad</h2>
            <p>Markdown notes, comments, and tags that steer the next parse.</p>
          </div>
          <div className="button-row wrap">
            <div className="segmented">
              <button className={scratchpadMode === "view" ? "active" : ""} onClick={() => setScratchpadMode("view")}>
                View
              </button>
              <button className={scratchpadMode === "edit" ? "active" : ""} onClick={() => setScratchpadMode("edit")}>
                Edit
              </button>
            </div>
            <button onClick={onSaveScratchpad}>Save</button>
            <button className="primary" onClick={onReparse} disabled={busy}>
              {busy ? "Parsing..." : "Trigger re-parse"}
            </button>
          </div>
        </div>
        {scratchpadMode === "edit" ? (
          <textarea value={scratchpad} onChange={(event) => setScratchpad(event.target.value)} spellCheck="false" />
        ) : (
          <div className="markdown-view">{renderMarkdown(scratchpad)}</div>
        )}
      </div>
    </section>
  );
}

function inferredQueue(action) {
  if (!action) return "Open queue";
  if (["Approved", "Applied", "Rejected"].includes(action.status)) return "Closed";
  if (action.queue) return action.queue;
  if (action.owner === "AI agent" || action.status === "Ready") return "Agent ready";
  if (action.issue_type?.includes("evidence") || action.issue_type?.includes("NICU")) return "Evidence review";
  if (action.status === "Needs review" || action.owner === "Human") return "Human review";
  return "Open queue";
}

function actionButtonsFor(action) {
  const queue = inferredQueue(action);
  if (queue === "Agent ready") {
    return [
      { label: action.primary_action || "Apply safe fix", status: "Applied", tone: "primary", noteRequired: true },
      { label: action.secondary_action || "Send to review", status: "Needs review", noteRequired: false },
      { label: "Reject", status: "Rejected", noteRequired: true }
    ];
  }
  if (queue === "Evidence review") {
    return [
      { label: action.primary_action || "Confirm claim", status: "Approved", tone: "primary", noteRequired: true },
      { label: action.secondary_action || "Reject claim", status: "Rejected", noteRequired: true },
      { label: "Needs more evidence", status: "Needs evidence", noteRequired: false }
    ];
  }
  if (queue === "Closed") {
    return [
      { label: "Reopen", status: "Needs review", noteRequired: true }
    ];
  }
  return [
    { label: action?.primary_action || "Approve", status: "Approved", tone: "primary", noteRequired: true },
    { label: action?.secondary_action || "Reject", status: "Rejected", noteRequired: true },
    { label: "Needs review", status: "Needs review", noteRequired: false }
  ];
}

function tabBadgeCounts(state, pipeline) {
  const profile = state.run.profile || {};
  const actions = state.run.actions || [];
  const risks = state.run.risks || [];
  const openActions = actions.filter((action) => !["Approved", "Applied", "Rejected"].includes(action.status)).length;
  const driverCount = [
    profile.expected_lift,
    profile.duplicate_clusters,
    profile.sparse_locations,
    profile.suspicious_claims,
    profile.human_review_queue
  ].filter((value) => Number(value || 0) > 0).length;
  const agents = pipeline?.agents || {};
  const runningAgents = Object.values(agents).filter((agent) => ["running", "pending"].includes(agent?.status)).length;
  const reviewItems = agents.review?.result?.summary?.review_count || 0;
  const importPipelineCount =
    pipeline?.status === "running"
      ? runningAgents || 1
      : pipeline?.status === "completed"
        ? reviewItems
        : 1;

  return {
    "Current State": driverCount,
    "Import + Pipeline": importPipelineCount,
    Actions: openActions,
    "Risk Recommendations": risks.length
  };
}

function ActionsQueue({ state, onDecision, focus }) {
  const actions = state.run.actions || [];
  const [filters, setFilters] = useState({ queue: "All", priority: "All", owner: "All", status: "All", issue: "All" });
  const [selected, setSelected] = useState(actions[0] || null);
  const [note, setNote] = useState("");
  const [decisionError, setDecisionError] = useState("");
  const [decisionSaved, setDecisionSaved] = useState("");
  const [decisionBusy, setDecisionBusy] = useState("");

  useEffect(() => {
    if (focus) {
      setFilters((current) => ({ ...current, ...focus }));
    }
  }, [focus]);

  const queueOrder = ["All", "Human review", "Agent ready", "Evidence review", "Steward triage", "Open queue", "Closed"];
  const filtered = useMemo(() => actions.filter((action) => {
    const queue = inferredQueue(action);
    return (
      (filters.queue === "All" || queue === filters.queue) &&
      (filters.priority === "All" || action.priority === filters.priority) &&
      (filters.owner === "All" || action.owner === filters.owner) &&
      (filters.status === "All" || action.status === filters.status) &&
      (filters.issue === "All" || action.issue_type === filters.issue)
    );
  }), [actions, filters]);

  useEffect(() => {
    if (!selected || !filtered.some((action) => action.action_id === selected.action_id)) {
      chooseAction(filtered[0] || null);
    }
  }, [filtered, selected]);

  function chooseAction(action) {
    setSelected(action);
    setNote(action?.review_note || "");
    setDecisionError("");
    setDecisionSaved("");
  }

  async function decide(button) {
    if (!selected) return;
    const trimmed = note.trim();
    if (button.noteRequired && !trimmed) {
      setDecisionSaved("");
      setDecisionError("Add a short note before saving this decision.");
      return;
    }
    setDecisionBusy(button.status);
    setDecisionError("");
    setDecisionSaved("");
    try {
      await onDecision(selected.action_id, button.status, trimmed);
      setDecisionSaved(`${button.label} saved to the action queue.`);
    } catch (error) {
      setDecisionError(error.message);
    } finally {
      setDecisionBusy("");
    }
  }

  function applyFilter(next) {
    setFilters((current) => ({ ...current, ...next }));
  }

  const queueCounts = queueOrder.slice(1).map((queue) => ({
    queue,
    count: actions.filter((action) => inferredQueue(action) === queue).length
  }));
  const selectedQueue = inferredQueue(selected);
  const decisionButtons = selected ? actionButtonsFor(selected) : [];

  return (
    <section className="page-grid">
      <div className="panel full">
        <div className="panel-head">
          <div>
            <h2>Recommendations / Actions</h2>
            <p>Operational proof/reject queue generated from the current parse and imports.</p>
          </div>
          <div className="filters">
            {["priority", "issue", "owner", "status"].map((key) => (
              <select key={key} value={filters[key]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })}>
                <option>All</option>
                {[...new Set(actions.map((action) => (key === "issue" ? action.issue_type : action[key])).filter(Boolean))].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            ))}
          </div>
        </div>
        <div className="queue-lanes">
          <button className={filters.queue === "All" ? "queue-lane active" : "queue-lane"} onClick={() => applyFilter({ queue: "All" })}>
            <span>All actions</span>
            <b>{actions.length.toLocaleString()}</b>
            <small>full queue</small>
          </button>
          {queueCounts.map(({ queue, count }) => (
            <button key={queue} className={filters.queue === queue ? "queue-lane active" : "queue-lane"} onClick={() => applyFilter({ queue })}>
              <span>{queue}</span>
              <b>{count.toLocaleString()}</b>
              <small>{queue === "Agent ready" ? "safe fix candidates" : queue === "Closed" ? "decided items" : "proof/reject work"}</small>
            </button>
          ))}
        </div>
        <div className="queue-summary">
          <Metric label="Visible actions" value={filtered.length.toLocaleString()} detail="current filters" />
          <Metric label="Needs review" value={actions.filter((a) => inferredQueue(a) === "Human review").length.toLocaleString()} detail="human queue" tone="risk" />
          <Metric label="Agent ready" value={actions.filter((a) => inferredQueue(a) === "Agent ready").length.toLocaleString()} detail="safe-fix candidates" />
          <Metric label="Decision required" value={actions.filter((a) => a.decision_required !== false && inferredQueue(a) !== "Closed").length.toLocaleString()} detail="open proof/reject items" tone="warn" />
        </div>
        <DataTable
          rows={filtered}
          selectedId={selected?.action_id}
          onRowClick={chooseAction}
          columns={[
            { key: "queue", label: "Queue", render: (row) => <span className={`queue-chip queue-${inferredQueue(row).toLowerCase().replaceAll(" ", "-")}`}>{inferredQueue(row)}</span> },
            { key: "priority", label: "Priority" },
            { key: "issue_type", label: "Issue" },
            { key: "recommendation", label: "Recommendation" },
            { key: "owner", label: "Owner" },
            { key: "confidence", label: "Confidence" },
            { key: "status", label: "Status" },
            {
              key: "action",
              label: "Action",
              render: (row) => (
                <button
                  className="small-button"
                  onClick={(event) => {
                    event.stopPropagation();
                    chooseAction(row);
                  }}
                >
                  Work item
                </button>
              )
            }
          ]}
        />
      </div>

      <div className="panel full detail-panel">
        <div>
          <h2>Selected Action</h2>
          {selected ? (
            <>
              <p className="recommendation">{selected.recommendation}</p>
              <div className="next-action">
                <span className={`queue-chip queue-${selectedQueue.toLowerCase().replaceAll(" ", "-")}`}>{selectedQueue}</span>
                <h3>Next step</h3>
                <p>{selected.next_step || "Review the evidence and save a decision."}</p>
              </div>
              <dl>
                <dt>Assignee</dt>
                <dd>{selected.assignee || selected.owner}</dd>
                <dt>Evidence</dt>
                <dd>{selected.evidence}</dd>
                <dt>Confidence</dt>
                <dd>{selected.confidence}</dd>
                <dt>Lift</dt>
                <dd>{selected.lift_points} pts</dd>
              </dl>
            </>
          ) : (
            <p>Select an action to review evidence.</p>
          )}
        </div>
        <div>
          <h2>Decision Note</h2>
          <textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add the proof/reject rationale, source preference, or reviewer tag..." />
          {decisionError ? <div className="form-error">{decisionError}</div> : null}
          {decisionSaved ? <div className="success-note">{decisionSaved}</div> : null}
          <div className="button-row">
            {decisionButtons.map((button) => (
              <button
                key={button.status}
                className={button.tone === "primary" ? "primary" : ""}
                disabled={!selected || Boolean(decisionBusy)}
                onClick={() => decide(button)}
              >
                {decisionBusy === button.status ? "Saving..." : button.label}
              </button>
            ))}
          </div>
          <p className="helper-text">Decisions persist to the current result state and become audit events in Unity Catalog mode.</p>
        </div>
      </div>
    </section>
  );
}

function RiskRecommendations({ state, onActionJump }) {
  const risks = state.run.risks || [];
  const [selected, setSelected] = useState(risks[0] || null);
  const [confidence, setConfidence] = useState("All");
  const [planningNote, setPlanningNote] = useState("");
  const [noteSaved, setNoteSaved] = useState("");
  const riskRows = useMemo(
    () => risks.filter((risk) => confidence === "All" || risk.confidence === confidence),
    [risks, confidence]
  );

  function openRelatedQueue() {
    onActionJump({ queue: "All", issue: "Location quality", status: "All", owner: "All" });
  }

  return (
    <section className="page-grid">
      <div className="panel full">
        <div className="panel-head">
          <div>
            <h2>Risk Recommendations</h2>
            <p>Planning output generated after dedupe, evidence scoring, and uncertainty penalties.</p>
          </div>
          <select value={confidence} onChange={(event) => setConfidence(event.target.value)}>
            <option>All</option>
            {[...new Set(risks.map((risk) => risk.confidence))].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </div>
        <DataTable
          rows={riskRows}
          selectedId={selected?.location}
          onRowClick={(row) => setSelected(row)}
          columns={[
            { key: "priority", label: "Priority" },
            { key: "state", label: "State" },
            { key: "location", label: "Location" },
            { key: "care_need", label: "Care need" },
            { key: "risk", label: "Risk" },
            { key: "confidence", label: "Confidence" },
            { key: "why", label: "Why" }
          ]}
        />
      </div>
      <div className="panel full detail-panel">
        <div>
          <h2>Recommendation Detail</h2>
          {selected ? (
            <>
              <p className="recommendation">{selected.risk} in {selected.location}, {selected.state}</p>
              <p>{selected.why}</p>
              <p>{selected.look_at}</p>
              <div className="button-row">
                <button className="primary" onClick={openRelatedQueue}>Open cleanup actions</button>
                <button onClick={() => onActionJump({ queue: "Evidence review", issue: "All", status: "All", owner: "All" })}>Open evidence queue</button>
              </div>
            </>
          ) : (
            <p>Select a risk row to inspect.</p>
          )}
        </div>
        <div>
          <h2>Planning Note</h2>
          <textarea value={planningNote} onChange={(event) => setPlanningNote(event.target.value)} placeholder="Save a note for the planning team..." />
          {noteSaved ? <div className="success-note">{noteSaved}</div> : null}
          <button onClick={() => setNoteSaved("Planning note staged for this demo session.")}>Save planning note</button>
        </div>
      </div>
    </section>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const [actionFocus, setActionFocus] = useState(null);
  const [state, setState] = useState(null);
  const [config, setConfig] = useState(null);
  const [scratchpad, setScratchpad] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pipeline, setPipeline] = useState(null);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const pipelinePollerRef = React.useRef(null);

  async function refresh() {
    const next = await api("/api/state", {}, 25000);
    setState(next);
    setScratchpad(next.scratchpad);
  }

  function startPipelinePoller(pipelineId) {
    stopPipelinePoller();
    const poll = async () => {
      try {
        const s = await api(`/api/pipeline/status/${pipelineId}`, {}, 10000);
        setPipeline(s);
        if (s.status === "running") {
          pipelinePollerRef.current = setTimeout(poll, 3000);
        }
      } catch {
        pipelinePollerRef.current = setTimeout(poll, 5000);
      }
    };
    pipelinePollerRef.current = setTimeout(poll, 1000);
  }

  function stopPipelinePoller() {
    if (pipelinePollerRef.current) {
      clearTimeout(pipelinePollerRef.current);
      pipelinePollerRef.current = null;
    }
  }

  async function startPipeline(incomingRecords = null) {
    setPipelineBusy(true);
    try {
      const body = incomingRecords ? { incoming_records: incomingRecords } : {};
      const res = await api("/api/pipeline/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setPipeline({ pipeline_id: res.pipeline_id, status: "running", agents: {}, mode: incomingRecords ? "ingest" : "analysis" });
      startPipelinePoller(res.pipeline_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setPipelineBusy(false);
    }
  }

  useEffect(() => {
    api("/api/config", {}, 8000)
      .then(setConfig)
      .catch(() => setConfig(null));
    refresh().catch((err) => {
      setError(err.name === "AbortError" ? "Timed out loading app state. Check Unity Catalog access and SQL warehouse config." : err.message);
    });
    // Load any existing pipeline status
    api("/api/pipeline/status", {}, 5000)
      .then((s) => {
        if (s?.pipeline_id) {
          setPipeline(s);
          if (s.status === "running") startPipelinePoller(s.pipeline_id);
        }
      })
      .catch(() => {});
    return () => stopPipelinePoller();
  }, []);

  async function saveScratchpad() {
    await api("/api/scratchpad", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: scratchpad })
    });
  }

  async function reparse() {
    setBusy(true);
    setError("");
    try {
      const next = await api("/api/reparse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ markdown: scratchpad })
      });
      setState({ ...state, ...next });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function actionDecision(actionId, status, note) {
    await api(`/api/actions/${actionId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note })
    });
    await refresh();
  }

  function jumpToActions(focus) {
    setActionFocus({ queue: "All", priority: "All", issue: "All", owner: "All", status: "All", ...focus });
    setActiveTab("Actions");
  }

  if (error) {
    return (
      <main className="app-shell">
        <div className="error">
          <h2>Could not load Data Readiness Desk</h2>
          <p>{error}</p>
          {config ? (
            <div className="debug-grid">
              {Object.entries(config).map(([key, value]) => (
                <div key={key}>
                  <span>{key}</span>
                  <b>{String(value || "not set")}</b>
                </div>
              ))}
            </div>
          ) : (
            <p>Could not read `/api/config`. Check the app logs and deployment environment variables.</p>
          )}
          <div className="button-row">
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        </div>
      </main>
    );
  }

  if (!state) {
    return <main className="app-shell"><div className="loading">Loading Data Readiness Desk...</div></main>;
  }

  const backendStatus = state.run.backend_status || (state.run.fallback ? "warming" : "live");
  const backendStatusLabel =
    backendStatus === "live" ? "Live data" : backendStatus === "refreshing" ? "Refreshing cache" : "Warming cache";
  const badges = tabBadgeCounts(state, pipeline);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Data Readiness Desk</h1>
          <p>Track 4 cleanup workflow to Track 2 risk planning output</p>
        </div>
        <div className="run-meta">
          <span>{state.catalog}</span>
          <span>Last parse: {state.run.ran_at || "draft"}</span>
          <span>Run ID: {state.run.run_id || "none"}</span>
          <span className={`backend-pill backend-${backendStatus}`}>{backendStatusLabel}</span>
        </div>
      </header>

      <nav className="tabs">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            <span>{tab}</span>
            <span className={`tab-badge ${badges[tab] ? "" : "tab-badge-empty"}`} title={`${badges[tab].toLocaleString()} items`}>
              {formatBadgeValue(badges[tab])}
            </span>
          </button>
        ))}
      </nav>

      {activeTab === "Current State" ? (
        <CurrentState
          state={state}
          onActionJump={jumpToActions}
        />
      ) : null}
      {activeTab === "Import + Pipeline" ? (
        <ImportPipeline
          scratchpad={scratchpad}
          setScratchpad={setScratchpad}
          onSaveScratchpad={saveScratchpad}
          onReparse={reparse}
          busy={busy}
          pipeline={pipeline}
          onPipelineStart={startPipeline}
          pipelineBusy={pipelineBusy}
        />
      ) : null}
      {activeTab === "Actions" ? <ActionsQueue state={state} onDecision={actionDecision} focus={actionFocus} /> : null}
      {activeTab === "Risk Recommendations" ? <RiskRecommendations state={state} onActionJump={jumpToActions} /> : null}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
