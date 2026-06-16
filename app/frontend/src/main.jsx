import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const tabs = ["Current State", "NGO Planner", "Import + Pipeline", "Actions", "Risk Recommendations"];

const SCORE_DEFINITIONS = {
  "Data consistency":
    "Weighted readiness score for the current resulting state. Formula: 25% completeness, 20% dedupe health, 20% contradiction safety, 15% location quality, 10% evidence quality, 10% provenance. Higher means safer to use for planning.",
  Completeness:
    "Percent of records with the minimum planning fields populated: facility name, at least city or state, and description. Gaps here mean the row is hard to use.",
  "Dedupe health":
    "Percent of rows not sitting inside duplicate clusters. Lower means duplicate facilities may inflate coverage and make regions look better served than they are.",
  Contradictions:
    "Estimated share of records without suspicious capability conflicts. Lower means claims like ICU/NICU/emergency may disagree with the evidence and need review.",
  "Location quality":
    "Percent of records with city, state, and PIN populated. Lower means geography-based planning may confuse real care gaps with missing location data.",
  "Evidence quality":
    "Percent of records with both descriptive text and capability/specialty evidence. Lower means clinical claims are weakly supported.",
  Provenance:
    "Percent of records with a source value. Lower means reviewers have less traceability when deciding whether to trust the record.",
  "Import readiness":
    "Percent of uploaded rows that have enough required fields to enter the agent pipeline without manual column mapping first.",
  "QA quality":
    "Average completeness score across identity, location, capability, provenance, and metadata groups in the QA agent output.",
  "Data readiness":
    "Risk agent roll-up of whether the dataset is clean enough to trust after dedupe, evidence, geo, shortage, and review checks.",
  "Planning readiness":
    "Risk agent estimate of whether the resulting state is safe enough to use for allocation or medical desert planning.",
};

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

function InfoTip({ text }) {
  if (!text) return null;
  return (
    <span className="info-tip" title={text} aria-label={text} tabIndex={0}>
      i
    </span>
  );
}

function Metric({ label, value, detail, tone = "neutral", onClick, tooltip }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      className={`metric metric-${tone} ${onClick ? "metric-clickable" : ""}`}
      onClick={onClick}
      title={tooltip}
      aria-label={tooltip ? `${label}: ${value}. ${tooltip}` : undefined}
    >
      <div className="metric-label">
        <span>{label}</span>
        <InfoTip text={tooltip} />
      </div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </Tag>
  );
}

function ScoreBar({ label, value }) {
  const tooltip = SCORE_DEFINITIONS[label];
  return (
    <div className="score-row" title={tooltip} aria-label={`${label}: ${value}%. ${tooltip || ""}`}>
      <div className="score-label">
        <span>
          {label}
          <InfoTip text={tooltip} />
        </span>
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
  const actions = state.run.actions || [];
  const components = profile.score_components || {};
  const reviewQueueCount = actions.filter((action) => (
    action.decision_required !== false &&
    ["Human review", "Evidence review", "Steward triage"].includes(inferredQueue(action))
  )).length;
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

  const ctaCards = [
    {
      key: "human",
      title: `Work ${reviewQueueCount.toLocaleString()} priority review item${reviewQueueCount === 1 ? "" : "s"}`,
      detail: "Curated proof/reject actions only. Raw candidate counts stay behind the agent workflow.",
      button: "Open review queue",
      tone: "risk",
      filters: { issue: "All", status: "All", owner: "Human" },
      show: reviewQueueCount > 0,
    },
    {
      key: "dedupe",
      title: `Resolve ${profile.duplicate_clusters.toLocaleString()} duplicate cluster${profile.duplicate_clusters === 1 ? "" : "s"}`,
      detail: "Merge or reject duplicates before facility counts are used for coverage.",
      button: "Open dedupe queue",
      tone: "warn",
      filters: { issue: "Duplicate cluster", status: "All", owner: "All" },
      show: profile.duplicate_clusters > 0,
    },
    {
      key: "location",
      title: `Repair ${profile.sparse_locations.toLocaleString()} sparse location${profile.sparse_locations === 1 ? "" : "s"}`,
      detail: "Fix missing PIN/city/state before geography turns into a false care gap.",
      button: "Open location fixes",
      tone: "neutral",
      filters: { issue: "Location quality", status: "All", owner: "All" },
      show: profile.sparse_locations > 0,
    },
    {
      key: "contradictions",
      title: `Review ${Math.max(0, 100 - Number(components.Contradictions || 100))} pts of contradiction risk`,
      detail: "Check facility claims where structured fields and evidence may disagree.",
      button: "Open evidence review",
      tone: "risk",
      filters: { issue: "Capability evidence", status: "All", owner: "Human" },
      show: Number(components.Contradictions || 100) < 95,
    },
    {
      key: "evidence",
      title: `Verify ${Math.max(0, 100 - Number(components["Evidence quality"] || 100))} pts of weak evidence`,
      detail: "Confirm planning-critical claims like ICU, NICU, emergency, maternity, and oncology.",
      button: "Open claim review",
      tone: "neutral",
      filters: { issue: "NICU review", status: "All", owner: "Human" },
      show: Number(components["Evidence quality"] || 100) < 95,
    },
  ].filter((card) => card.show).slice(0, 4);

  return (
    <section className="page-grid">
      <div className="full">
        <div className="metric-grid">
          <Metric
            label="Data consistency"
            value={`${profile.consistency_score}%`}
            detail={`+${profile.expected_lift} pts possible · open all actions`}
            tone="warn"
            tooltip={SCORE_DEFINITIONS["Data consistency"]}
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
            label="Review queue"
            value={reviewQueueCount.toLocaleString()}
            detail="curated action items"
            tone="risk"
            onClick={() => onActionJump({ issue: "All", status: "All", owner: "Human" })}
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
        <p className="score-explainer">
          Scores are triage signals. Use the next actions below to move from diagnosis to proof/reject work.
        </p>
        <div className="mission-actions" aria-label="Mission Control next actions">
          {ctaCards.length ? ctaCards.map((card, index) => (
            <button
              key={card.key}
              className={`mission-action mission-action-${card.tone} ${index === 0 ? "mission-action-primary" : ""}`}
              onClick={() => onActionJump(card.filters)}
            >
              <span className="mission-action-label">{card.button}</span>
              <strong>{card.title}</strong>
              <span>{card.detail}</span>
            </button>
          )) : (
            <button className="mission-action mission-action-primary" onClick={() => onActionJump({ issue: "All", status: "All", owner: "All" })}>
              <span className="mission-action-label">Inspect actions</span>
              <strong>No urgent CTA from current scores</strong>
              <span>Open the action queue to review lower-priority recommendations and audit state.</span>
            </button>
          )}
        </div>
        <div className="tag-line">
          {(profile.tags || []).length ? profile.tags.map((tag) => <span key={tag}>#{tag}</span>) : <span>No tags yet</span>}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>Recommended Queues</h2>
            <p>Fast paths into the cleanup work behind the readiness scores.</p>
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

const AGENT_NAMES = ["ingestion", "qa", "pincode", "nfhs", "dedup", "evidence", "geo", "shortage", "review", "risk"];
const AGENT_LABELS = {
  ingestion: "Ingest",
  qa: "QA profile",
  pincode: "PIN lookup",
  nfhs: "NFHS survey",
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
  const ruleFamilies = Array.isArray(result.rule_families) ? result.rule_families.slice(0, 4) : [];
  return (
    <div className={`agent-card agent-${tone}`}>
      <div className="agent-header">
        <b>{AGENT_LABELS[name]}</b>
        <span className={`badge badge-${tone}`}>{status}</span>
      </div>
      {ruleFamilies.length ? (
        <div className="agent-rules" aria-label={`${AGENT_LABELS[name]} workflow rules`}>
          {ruleFamilies.map((rule) => (
            <span key={rule}>{rule}</span>
          ))}
        </div>
      ) : null}
      {agentState?.error ? <p className="agent-error">{agentState.error}</p> : null}
      {status === "completed" && name === "ingestion" && result.summary ? (
        <p className="agent-detail">
          {result.incoming_count ?? 0} incoming · route: {result.route || "qa_ready"}
        </p>
      ) : null}
      {status === "completed" && name === "qa" && result.summary ? (
        <p className="agent-detail" title={SCORE_DEFINITIONS["QA quality"]}>
          Quality: {result.overall_quality_score ?? "—"}% · {result.summary.flag_count ?? 0} flags
          <InfoTip text={SCORE_DEFINITIONS["QA quality"]} />
        </p>
      ) : null}
      {status === "completed" && name === "pincode" && result.summary ? (
        <p className="agent-detail" title={result.guardrail}>
          {result.summary.valid_facility_pin_rows ?? 0} valid PIN rows · {result.summary.review_item_count ?? 0} review
          <InfoTip text={result.guardrail} />
        </p>
      ) : null}
      {status === "completed" && name === "nfhs" && result.summary ? (
        <p className="agent-detail" title={result.guardrail}>
          {result.summary.expected_nfhs_source_rows ?? 0} district rows · {result.summary.baseline_suppressed_cell_count ?? 0} suppressed cells
          <InfoTip text={result.guardrail} />
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
        <p className="agent-detail" title={`${SCORE_DEFINITIONS["Data readiness"]} ${SCORE_DEFINITIONS["Planning readiness"]}`}>
          Data readiness: {result.data_readiness_score ?? "—"}% · Planning: {result.planning_readiness_score ?? "—"}%
          <InfoTip text={`${SCORE_DEFINITIONS["Data readiness"]} ${SCORE_DEFINITIONS["Planning readiness"]}`} />
        </p>
      ) : null}
    </div>
  );
}

function PipelinePanel({ pipeline, onStart, busy, ingestRecords, className = "" }) {
  const status = pipeline?.status || "idle";
  const agents = pipeline?.agents || {};
  const riskResult = agents.risk?.result || {};
  const reviewSummary = agents.review?.result?.summary || {};
  const pincodeSummary = agents.pincode?.result?.summary || {};
  const evidenceSummary = agents.evidence?.result?.summary || {};
  const completedAgents = AGENT_NAMES.filter((name) => agents[name]?.status === "completed").length;
  const openPipelineNotifications = [
    {
      label: "Review gate",
      value: reviewSummary.review_count || 0,
      detail: "proof/reject items from dedupe, PIN, evidence, geo, and shortage signals"
    },
    {
      label: "PIN enrichment",
      value: pincodeSummary.review_item_count || 0,
      detail: "postal rows that need review before automatic geography enrichment"
    },
    {
      label: "Evidence checks",
      value: evidenceSummary.review_claims || 0,
      detail: "weak or suspicious capability claims"
    }
  ].filter((item) => Number(item.value || 0) > 0);
  const tone = STATUS_TONE[status] || "neutral";
  const isRunning = status === "running";
  const pipelineMode = pipeline?.mode || "analysis";

  return (
    <div className={`panel ${className}`.trim()}>
      <div className="panel-head">
        <div>
          <h2>AI Pipeline</h2>
          <p>
            {ingestRecords
              ? `Ingest mode: ${ingestRecords.length} incoming records → QA → PIN/NFHS context → Dedupe/Evidence/Geo → Shortage → Review → Risk.`
              : "Analysis mode: Ingest → QA → PIN/NFHS context → Dedupe/Evidence/Geo → Shortage → Review → Risk."}
            {pipeline?.pipeline_id ? <span className="run-id"> Run: {pipeline.pipeline_id}</span> : null}
            {pipeline?.mode ? <span className="run-id"> [{pipeline.mode}]</span> : null}
          </p>
          {status === "completed" ? (
            <p className="pipeline-steady">
              {completedAgents}/{AGENT_NAMES.length} agents completed. Green means the last run finished cleanly; notifications below are review work, not failed tasks.
            </p>
          ) : null}
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

      {status === "completed" && openPipelineNotifications.length ? (
        <div className="pipeline-notifications" aria-label="Pipeline review notifications">
          {openPipelineNotifications.map((item) => (
            <div className="pipeline-notice" key={item.label} title={item.detail}>
              <span>{item.label}</span>
              <b>{Number(item.value || 0).toLocaleString()}</b>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
      ) : null}

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
    <section className="import-pipeline-layout">
      <div className="panel import-strip">
        <div className="panel-head">
          <div>
            <h2>Import</h2>
            <p>Stage XLS, XLSX, or CSV before it touches trusted tables.</p>
          </div>
        </div>
        <label
          className="dropzone import-dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            previewUpload(event.dataTransfer.files?.[0] || null);
          }}
        >
          <input type="file" accept=".csv,.xls,.xlsx" onChange={(event) => previewUpload(event.target.files?.[0] || null)} />
          <span>{upload ? upload.name : "Drop or choose a facility file"}</span>
        </label>
        {uploadError ? <div className="error">{uploadError}</div> : null}
        {uploadPreview ? (
          <div className="import-summary">
            <Metric label="Parsed rows" value={uploadPreview.row_count.toLocaleString()} />
            <Metric label="Import readiness" value={`${uploadPreview.import_readiness}%`} tooltip={SCORE_DEFINITIONS["Import readiness"]} />
            <Metric label="Columns" value={uploadPreview.columns.length.toLocaleString()} />
          </div>
        ) : null}
      </div>

      <div className="import-workspace-grid">
        <div className="panel scratchpad">
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

        <PipelinePanel
          className="pipeline-column"
          pipeline={pipeline}
          onStart={onPipelineStart}
          busy={pipelineBusy}
          ingestRecords={uploadPreview?.preview || null}
        />
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

function ActionEvidenceGrid({ items = [] }) {
  if (!items.length) return null;
  return (
    <div className="evidence-grid">
      {items.map((item, index) => (
        <div className={`evidence-card evidence-${item.tone || "medium"}`} key={`${item.label}-${index}`}>
          <span>{item.label}</span>
          <b>{item.value}</b>
        </div>
      ))}
    </div>
  );
}

function RecordsComparison({ records = [] }) {
  if (!records.length) return <p className="helper-text">No row-level records were attached to this action.</p>;
  const fields = ["name", "address_city", "address_stateOrRegion", "address_zipOrPostcode", "organization_type", "specialties", "source"];
  return (
    <div className="comparison-table">
      <div className="comparison-head">
        <b>Field</b>
        {records.map((record, index) => <b key={index}>Record {index + 1}</b>)}
      </div>
      {fields.map((field) => (
        <div className="comparison-row" key={field}>
          <span>{field}</span>
          {records.map((record, index) => (
            <div key={`${field}-${index}`}>{record[field] || <em>blank</em>}</div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ProposedResult({ result }) {
  if (!result || Object.keys(result).length === 0) return null;
  return (
    <div className="proposed-result">
      {Object.entries(result).map(([key, value]) => (
        <div key={key}>
          <span>{key.replaceAll("_", " ")}</span>
          <b>{Array.isArray(value) ? value.join(", ") : String(value || "blank")}</b>
        </div>
      ))}
    </div>
  );
}

function SafeRules({ rules = [] }) {
  if (!rules.length) return null;
  return (
    <div className="rule-list">
      {rules.map((rule, index) => (
        <div className="rule-row" key={`${rule.rule}-${index}`}>
          <b>{rule.rule}</b>
          <span>{rule.effect}</span>
        </div>
      ))}
    </div>
  );
}

function DuplicateMergeWorkspace({ action, note, setNote }) {
  const [choices, setChoices] = useState(() => {
    const initial = {};
    (action.field_choices || []).forEach((choice) => {
      initial[choice.field] = choice.recommended_value || "";
    });
    return initial;
  });

  useEffect(() => {
    const next = {};
    (action.field_choices || []).forEach((choice) => {
      next[choice.field] = choice.recommended_value || "";
    });
    setChoices(next);
  }, [action.action_id]);

  function recordChoice(field, value) {
    const next = { ...choices, [field]: value };
    setChoices(next);
    const compact = Object.entries(next)
      .map(([key, chosen]) => `${key}=${chosen || "blank"}`)
      .join("; ");
    setNote(`Merge approved with canonical fields: ${compact}`);
  }

  return (
    <div className="action-workspace">
      <div>
        <h3>Merge Resolver</h3>
        <p>Compare the candidate records, choose canonical field values, then approve or reject the merge.</p>
      </div>
      <ActionEvidenceGrid items={action.evidence_items} />
      <RecordsComparison records={action.records} />
      <div className="field-choice-grid">
        {(action.field_choices || []).map((choice) => (
          <label key={choice.field}>
            <span>{choice.field.replaceAll("_", " ")}</span>
            <select value={choices[choice.field] || ""} onChange={(event) => recordChoice(choice.field, event.target.value)}>
              <option value={choice.recommended_value || ""}>{choice.recommended_value || "blank"} · recommended</option>
              {(choice.alternates || []).map((alternate) => <option key={alternate}>{alternate}</option>)}
              <option value="">blank / unknown</option>
            </select>
          </label>
        ))}
      </div>
      <h3>Proposed Canonical Facility</h3>
      <ProposedResult result={{ ...(action.proposed_result || {}), ...choices }} />
    </div>
  );
}

function LocationCleanupWorkspace({ action }) {
  return (
    <div className="action-workspace">
      <div>
        <h3>Geo Cleanup Agent</h3>
        <p>Safe deterministic rules can be applied immediately; ambiguous geography stays in review.</p>
      </div>
      <ActionEvidenceGrid items={action.evidence_items} />
      <SafeRules rules={action.safe_rules} />
      <RecordsComparison records={action.records} />
      <ProposedResult result={action.proposed_result} />
    </div>
  );
}

function CapabilityReviewWorkspace({ action }) {
  return (
    <div className="action-workspace">
      <div>
        <h3>Evidence Gate</h3>
        <p>Clinical claims only count for planning after the evidence tests pass.</p>
      </div>
      <ActionEvidenceGrid items={action.evidence_items} />
      <div className="rule-list">
        {(action.claim_tests || []).map((test, index) => (
          <div className="rule-row" key={`${test.test}-${index}`}>
            <b>{test.test}</b>
            <span>{test.required ? "required for approval" : "optional"}</span>
          </div>
        ))}
      </div>
      <RecordsComparison records={action.records} />
    </div>
  );
}

function TagTriageWorkspace({ action }) {
  return (
    <div className="action-workspace">
      <div>
        <h3>Review Slice Builder</h3>
        <p>Scratchpad tags become steward queues and filters for the next parse run.</p>
      </div>
      <ActionEvidenceGrid items={action.evidence_items} />
      <div className="tag-strip">
        {(action.tags || []).length ? action.tags.map((tag) => <span className="inline-tag" key={tag}>#{tag}</span>) : <span className="muted-pill">No tags yet</span>}
      </div>
      <ProposedResult result={action.proposed_result} />
    </div>
  );
}

function AutoAppliedWorkspace({ action }) {
  return (
    <div className="action-workspace auto-applied-workspace">
      <div>
        <h3>Auto-Applied Agent Action</h3>
        <p>{action.agent_result || "This action already applied safe derived metadata."}</p>
      </div>
      <ActionEvidenceGrid items={action.evidence_items} />
      <SafeRules rules={action.safe_rules} />
      <ProposedResult result={action.proposed_result} />
    </div>
  );
}

function GenericActionWorkspace({ action }) {
  return (
    <div className="action-workspace">
      <ActionEvidenceGrid items={action.evidence_items} />
      <ProposedResult result={action.proposed_result} />
    </div>
  );
}

function ActionWorkspace({ action, note, setNote }) {
  if (!action) return <p>Select an action to review evidence.</p>;
  if (action.action_kind === "duplicate_merge") {
    return <DuplicateMergeWorkspace action={action} note={note} setNote={setNote} />;
  }
  if (action.action_kind === "location_cleanup") return <LocationCleanupWorkspace action={action} />;
  if (action.action_kind === "capability_review") return <CapabilityReviewWorkspace action={action} />;
  if (action.action_kind === "tag_triage") return <TagTriageWorkspace action={action} />;
  if (action.action_kind === "auto_applied") return <AutoAppliedWorkspace action={action} />;
  return <GenericActionWorkspace action={action} />;
}

function priorityWeight(priority) {
  const normalized = String(priority || "").toLowerCase();
  if (normalized.includes("critical")) return 4;
  if (normalized.includes("high")) return 3;
  if (normalized.includes("medium")) return 2;
  if (normalized.includes("low")) return 1;
  return 0;
}

function confidenceLabel(score) {
  const value = Number(score || 0);
  if (value >= 80) return "High";
  if (value >= 65) return "Medium";
  return "Low";
}

function plannerTaskLabel(action) {
  const issue = String(action.issue_type || "").toLowerCase();
  if (issue.includes("duplicate")) return "Confirm facility count before coverage planning";
  if (issue.includes("location")) return "Verify location before assigning field outreach";
  if (issue.includes("nicu") || issue.includes("capability") || issue.includes("evidence")) {
    return "Verify clinical capability before routing referrals";
  }
  if (issue.includes("tag")) return "Route this review slice to the right field owner";
  return action.primary_action || "Review evidence and decide next step";
}

function aggregatePlannerGeography(rows = []) {
  const groups = new Map();
  rows.forEach((row) => {
    const state = row.address_stateOrRegion || "Unknown state";
    const city = row.address_city || "Unknown city";
    const key = `${state}||${city}`;
    const current = groups.get(key) || {
      state,
      city,
      facilities: 0,
      sparse: 0,
      clustered: 0,
      flags: new Set(),
    };
    const flags = String(row.readiness_flags || "").toLowerCase();
    current.facilities += 1;
    if (flags.includes("missing") || flags.includes("sparse")) current.sparse += 1;
    if (flags.includes("cluster")) current.clustered += 1;
    String(row.readiness_flags || "")
      .split(",")
      .map((flag) => flag.trim())
      .filter(Boolean)
      .forEach((flag) => current.flags.add(flag));
    groups.set(key, current);
  });

  return [...groups.values()]
    .map((group) => ({
      ...group,
      riskSignal: group.sparse + group.clustered,
      flags: [...group.flags].slice(0, 3).join(", ") || "ok",
    }))
    .sort((left, right) => right.riskSignal - left.riskSignal || right.facilities - left.facilities)
    .slice(0, 6);
}

function NGOPlanner({ state, onActionJump }) {
  const profile = state.run.profile || {};
  const actions = state.run.actions || [];
  const risks = state.run.risks || [];
  const components = profile.score_components || {};
  const openActions = actions.filter((action) => !["Approved", "Applied", "Rejected"].includes(action.status));
  const humanReviewCount = openActions.filter((action) => inferredQueue(action) === "Human review").length;
  const evidenceCount = openActions.filter((action) => inferredQueue(action) === "Evidence review" || String(action.issue_type || "").toLowerCase().includes("evidence")).length;
  const locationCount = openActions.filter((action) => String(action.issue_type || "").toLowerCase().includes("location")).length;
  const duplicateCount = openActions.filter((action) => String(action.issue_type || "").toLowerCase().includes("duplicate")).length;
  const planningConfidence = confidenceLabel(profile.consistency_score);
  const missionFocus = (profile.tags || []).slice(0, 2).join(" + ") || "Maternal + emergency access";
  const priorityRisks = [...risks]
    .sort((left, right) => priorityWeight(right.priority) - priorityWeight(left.priority))
    .slice(0, 5);
  const fieldTasks = [...openActions]
    .sort((left, right) => priorityWeight(right.priority) - priorityWeight(left.priority))
    .slice(0, 6)
    .map((action) => ({
      ...action,
      field_task: plannerTaskLabel(action),
      planner_queue: inferredQueue(action),
    }));
  const geographyRows = aggregatePlannerGeography(state.preview || []);

  return (
    <section className="ngo-planner">
      <div className="planner-hero">
        <div>
          <span className="planner-kicker">NGO field planning view</span>
          <h2>Where should the team act next?</h2>
          <p>
            Prioritize districts, field verification, and outreach decisions while keeping data trust visible before resources move.
          </p>
        </div>
        <div className="planner-mission">
          <span>Mission focus</span>
          <b>{missionFocus}</b>
          <small>{state.catalog}.{state.schema}.{state.table}</small>
        </div>
      </div>

      <div className="metric-grid planner-metrics">
        <Metric label="Planning confidence" value={planningConfidence} detail={`${profile.consistency_score}% data consistency`} tone={planningConfidence === "Low" ? "risk" : "warn"} />
        <Metric label="Field actions" value={openActions.length.toLocaleString()} detail="open planner tasks" onClick={() => onActionJump({ queue: "All", status: "All", owner: "All" })} />
        <Metric label="Review blockers" value={humanReviewCount.toLocaleString()} detail="human proof/reject" tone="risk" onClick={() => onActionJump({ queue: "Human review", status: "All", owner: "Human" })} />
        <Metric label="Priority risks" value={risks.length.toLocaleString()} detail="trusted-state planning signals" />
      </div>

      <div className="planner-grid">
        <div className="panel planner-priorities">
          <div className="panel-head">
            <div>
              <h2>Priority Locations</h2>
              <p>Coverage and care-gap signals to inspect before deploying field capacity.</p>
            </div>
          </div>
          {priorityRisks.length ? (
            <div className="priority-stack">
              {priorityRisks.map((risk) => (
                <div className="priority-card" key={`${risk.location}-${risk.care_need}`}>
                  <div>
                    <span className={`queue-chip priority-${String(risk.priority || "medium").toLowerCase()}`}>{risk.priority || "Priority"}</span>
                    <h3>{risk.location}, {risk.state}</h3>
                    <p>{risk.care_need}</p>
                  </div>
                  <p>{risk.why}</p>
                  <small>{risk.look_at}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="helper-text">No risk recommendations yet. Run analysis or inspect the current geography signals below.</p>
          )}
        </div>

        <div className="panel planner-trust">
          <div className="panel-head">
            <div>
              <h2>Trust Before Deployment</h2>
              <p>Data issues translated into planning consequences.</p>
            </div>
          </div>
          <div className="trust-list">
            <button onClick={() => onActionJump({ issue: "Duplicate cluster", status: "All", owner: "All" })}>
              <b>{duplicateCount.toLocaleString()}</b>
              <span>Duplicate reviews may change facility counts.</span>
            </button>
            <button onClick={() => onActionJump({ issue: "Location quality", status: "All", owner: "All" })}>
              <b>{locationCount.toLocaleString()}</b>
              <span>Location fixes prevent false medical-desert signals.</span>
            </button>
            <button onClick={() => onActionJump({ queue: "Evidence review", status: "All", owner: "All" })}>
              <b>{evidenceCount.toLocaleString()}</b>
              <span>Capability claims need proof before referrals.</span>
            </button>
          </div>
          <div className="score-list planner-score-list">
            {["Completeness", "Location quality", "Evidence quality", "Dedupe health"].map((label) => (
              <ScoreBar key={label} label={label} value={components[label] || 0} />
            ))}
          </div>
        </div>

        <div className="panel full">
          <div className="panel-head">
            <div>
              <h2>Field Actions</h2>
              <p>Planner-language tasks generated from the current proof/reject queue.</p>
            </div>
            <button className="primary" onClick={() => onActionJump({ queue: "All", status: "All", owner: "All" })}>Open full queue</button>
          </div>
          <DataTable
            rows={fieldTasks}
            columns={[
              { key: "priority", label: "Priority" },
              { key: "planner_queue", label: "Queue" },
              { key: "field_task", label: "Field task" },
              { key: "recommendation", label: "Evidence source" },
              { key: "assignee", label: "Assignee", render: (row) => row.assignee || row.owner || "Planner" },
              { key: "confidence", label: "Confidence" },
            ]}
          />
        </div>

        <div className="panel full">
          <div className="panel-head">
            <div>
              <h2>Geography Watchlist</h2>
              <p>Preview locations where sparse fields or duplicate clusters may distort outreach planning.</p>
            </div>
          </div>
          <DataTable
            rows={geographyRows}
            columns={[
              { key: "state", label: "State" },
              { key: "city", label: "City" },
              { key: "facilities", label: "Preview facilities" },
              { key: "sparse", label: "Sparse rows" },
              { key: "clustered", label: "Clustered rows" },
              { key: "flags", label: "Signals" },
            ]}
          />
        </div>
      </div>
    </section>
  );
}

function tabBadgeCounts(state, pipeline) {
  const profile = state.run.profile || {};
  const actions = state.run.actions || [];
  const risks = state.run.risks || [];
  const openActions = actions.filter((action) => !["Approved", "Applied", "Rejected"].includes(action.status)).length;
  const reviewQueueCount = actions.filter((action) => (
    action.decision_required !== false &&
    ["Human review", "Evidence review", "Steward triage"].includes(inferredQueue(action))
  )).length;
  const driverCount = [
    profile.expected_lift,
    profile.duplicate_clusters,
    profile.sparse_locations,
    profile.suspicious_claims,
    reviewQueueCount
  ].filter((value) => Number(value || 0) > 0).length;
  const agents = pipeline?.agents || {};
  const runningAgents = Object.values(agents).filter((agent) => ["running", "pending"].includes(agent?.status)).length;
  const completedAgents = AGENT_NAMES.filter((name) => agents[name]?.status === "completed").length;
  const importPipelineCount =
    pipeline?.status === "running"
      ? runningAgents || 1
      : pipeline?.status === "completed"
        ? completedAgents || AGENT_NAMES.length
        : 0;

  return {
    "Current State": driverCount,
    "NGO Planner": risks.length || reviewQueueCount,
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
  const detailRef = React.useRef(null);

  useEffect(() => {
    if (focus) {
      setFilters((current) => ({ ...current, ...focus }));
    }
  }, [focus]);

  const queueOrder = ["All", "Human review", "Agent ready", "Evidence review", "Steward triage", "Open queue", "Closed"];
  const filterActions = (overrides = {}) => {
    const active = { ...filters, ...overrides };
    return actions.filter((action) => {
    const queue = inferredQueue(action);
    return (
        (active.queue === "All" || queue === active.queue) &&
        (active.priority === "All" || action.priority === active.priority) &&
        (active.owner === "All" || action.owner === active.owner) &&
        (active.status === "All" || action.status === active.status) &&
        (active.issue === "All" || action.issue_type === active.issue)
    );
    });
  };
  const filtered = useMemo(() => filterActions(), [actions, filters]);

  useEffect(() => {
    if (!selected || !filtered.some((action) => action.action_id === selected.action_id)) {
      chooseAction(filtered[0] || null);
    }
  }, [filtered, selected]);

  function chooseAction(action, scrollToDetail = false) {
    setSelected(action);
    setNote(action?.review_note || "");
    setDecisionError("");
    setDecisionSaved("");
    if (scrollToDetail) {
      window.requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        detailRef.current?.focus?.({ preventScroll: true });
      });
    }
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
      setSelected({ ...selected, status: button.status, review_note: trimmed });
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
    count: filterActions({ queue }).length
  }));
  const visibleAllActionsCount = filterActions({ queue: "All" }).length;
  const visibleNeedsReviewCount = filterActions({ queue: "Human review" }).length;
  const visibleAgentReadyCount = filterActions({ queue: "Agent ready" }).length;
  const visibleDecisionRequiredCount = filtered.filter((a) => a.decision_required !== false && inferredQueue(a) !== "Closed").length;
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
              <label className="filter-field" key={key}>
                <span>{key === "issue" ? "Issue" : key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <select value={filters[key]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })}>
                  <option>All</option>
                  {[...new Set(actions.map((action) => (key === "issue" ? action.issue_type : action[key])).filter(Boolean))].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </div>
        <div className="queue-lanes">
          <button className={filters.queue === "All" ? "queue-lane active" : "queue-lane"} onClick={() => applyFilter({ queue: "All" })}>
            <span>All actions</span>
            <b>{visibleAllActionsCount.toLocaleString()}</b>
            <small>{filters.priority === "All" && filters.issue === "All" && filters.owner === "All" && filters.status === "All" ? "full queue" : "with current filters"}</small>
          </button>
            {queueCounts.map(({ queue, count }) => (
              <button key={queue} className={filters.queue === queue ? "queue-lane active" : "queue-lane"} onClick={() => applyFilter({ queue })}>
                <span>{queue}</span>
                <b>{count.toLocaleString()}</b>
                <small>{filters.priority === "All" && filters.issue === "All" && filters.owner === "All" && filters.status === "All" ? "full queue" : "with current filters"}</small>
              </button>
            ))}
        </div>
        <div className="queue-summary">
          <Metric
            label="Visible actions"
            value={filtered.length.toLocaleString()}
            detail="current filters"
            onClick={() => applyFilter({ queue: "All", status: "All" })}
          />
          <Metric
            label="Needs review"
            value={visibleNeedsReviewCount.toLocaleString()}
            detail="visible human queue"
            tone="risk"
            onClick={() => applyFilter({ queue: "Human review", status: "Needs review", owner: "Human" })}
          />
          <Metric
            label="Agent ready"
            value={visibleAgentReadyCount.toLocaleString()}
            detail="visible safe fixes"
            onClick={() => applyFilter({ queue: "Agent ready", status: "Ready", owner: "AI agent" })}
          />
          <Metric
            label="Decision required"
            value={visibleDecisionRequiredCount.toLocaleString()}
            detail="visible proof/reject items"
            tone="warn"
            onClick={() => applyFilter({ queue: "All", status: "All" })}
          />
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
              label: "",
              render: (row) => <span className="row-detail-hint">{selected?.action_id === row.action_id ? "Selected" : "Select row"}</span>
            }
          ]}
        />
      </div>

      <div className="panel full detail-panel" ref={detailRef} tabIndex="-1">
        <div className="selected-action-column">
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
                <dt>Audit effect</dt>
                <dd>{selected.audit_effect || "Decision is saved to the action audit log."}</dd>
              </dl>
              <ActionWorkspace action={selected} note={note} setNote={setNote} />
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
                className={[
                  button.tone === "primary" ? "primary" : "",
                  button.status === "Approved" ? "approve" : ""
                ].filter(Boolean).join(" ")}
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
    const result = await api(`/api/actions/${actionId}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note })
    });
    setState((current) => ({
      ...current,
      run: {
        ...current.run,
        actions: (current.run.actions || []).map((action) =>
          action.action_id === actionId
            ? { ...action, status, review_note: note || "", persisted: result.persisted, cache_updated: result.cache_updated }
            : action
        ),
      },
    }));
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
      {activeTab === "NGO Planner" ? <NGOPlanner state={state} onActionJump={jumpToActions} /> : null}
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

const rootElement = document.getElementById("root");
const root = window.__DATA_READINESS_ROOT__ || createRoot(rootElement);
window.__DATA_READINESS_ROOT__ = root;
root.render(<App />);
