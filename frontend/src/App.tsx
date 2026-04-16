import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  ChevronRight,
  ChevronsUpDown,
  CheckCircle2,
  FlaskConical,
  FolderKanban,
  History,
  LayoutDashboard,
  LoaderCircle,
  Network,
  CircleDashed,
  Search,
  Server,
  Settings,
  ShieldAlert,
  Sparkles,
  Upload,
} from 'lucide-react';
import {motion} from 'motion/react';
import React, {startTransition, useDeferredValue, useEffect, useRef, useState} from 'react';

import {
  fetchHealth,
  fetchRuntimeStatus,
  fetchS3Buckets,
  fetchS3Objects,
  getApiBase,
  parseS3,
  parseUpload,
} from './api';
import type {
  HealthResponse,
  ParseResponse,
  RepairPatchProposal,
  S3BucketOption,
  RuntimeParserStatus,
  S3ObjectOption,
  TraceEvent,
} from './types';

const STAGE_ORDER = ['ingest', 'inspection', 'routing', 'parsing', 'normalization', 'validation', 'repair', 'rendering', 'export'];

const NAV_ITEMS = [
  {label: 'Parse Workspace', icon: LayoutDashboard, active: true},
  {label: 'Run History', icon: History, active: false},
  {label: 'Runtime Status', icon: Activity, active: false},
  {label: 'Parser Lab', icon: FlaskConical, active: false},
  {label: 'Validation Review', icon: ShieldAlert, active: false},
  {label: 'Settings', icon: Settings, active: false},
] as const;

type SourceMode = 'upload' | 's3';
type AsyncStatus = 'idle' | 'loading' | 'succeeded' | 'failed';
const DEFAULT_TEST_BUCKET = 'rag-580075786326-ap-northeast-2';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [runtime, setRuntime] = useState<RuntimeParserStatus[]>([]);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const [sourceMode, setSourceMode] = useState<SourceMode>('s3');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [bucket, setBucket] = useState('');
  const [bucketQuery, setBucketQuery] = useState('');
  const [bucketOptions, setBucketOptions] = useState<S3BucketOption[]>([]);
  const [bucketDropdownOpen, setBucketDropdownOpen] = useState(false);
  const [prefix, setPrefix] = useState('');
  const [s3Search, setS3Search] = useState('');
  const [s3Objects, setS3Objects] = useState<S3ObjectOption[]>([]);
  const [selectedS3Uri, setSelectedS3Uri] = useState('');
  const [s3DropdownOpen, setS3DropdownOpen] = useState(false);
  const [s3Status, setS3Status] = useState<AsyncStatus>('idle');
  const [s3Error, setS3Error] = useState<string | null>(null);

  const [llmRequested, setLlmRequested] = useState(false);
  const [parserHint, setParserHint] = useState('');
  const [parseStatus, setParseStatus] = useState<AsyncStatus>('idle');
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<ParseResponse | null>(null);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const sourcePanelRef = useRef<HTMLDivElement | null>(null);

  const deferredSearch = useDeferredValue(s3Search);
  const filteredObjects = s3Objects.filter((item) => {
    if (!deferredSearch.trim()) {
      return true;
    }
    const query = deferredSearch.toLowerCase();
    return item.label.toLowerCase().includes(query) || item.key.toLowerCase().includes(query);
  });
  const filteredBuckets = bucketOptions.filter((item) => {
    if (!bucketQuery.trim()) {
      return true;
    }
    const query = bucketQuery.toLowerCase();
    return item.label.toLowerCase().includes(query) || item.name.toLowerCase().includes(query);
  });

  const enabledParsers = runtime.filter((item) => item.enabled);
  const selectedObject = s3Objects.find((item) => item.s3_uri === selectedS3Uri) || null;
  const effectiveS3Uri = selectedS3Uri;
  const canParse = sourceMode === 'upload' ? selectedFile !== null : effectiveS3Uri.length > 0;

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const [healthResponse, runtimeResponse, bucketResponse] = await Promise.all([
          fetchHealth(),
          fetchRuntimeStatus(),
          fetchS3Buckets(),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthResponse);
        setRuntime(runtimeResponse.parsers);
        setBucketOptions(bucketResponse.buckets);
        const preferredBucket =
          bucketResponse.buckets.find((item) => item.name === DEFAULT_TEST_BUCKET)?.name
          || bucketResponse.buckets[0]?.name
          || '';
        if (preferredBucket) {
          setBucket(preferredBucket);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setBootstrapError(asErrorMessage(error));
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (sourceMode !== 's3' || !bucket.trim()) {
      return;
    }
    handleBrowseS3();
  }, [bucket, prefix, sourceMode]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!sourcePanelRef.current) {
        return;
      }
      if (sourcePanelRef.current.contains(event.target as Node)) {
        return;
      }
      setBucketDropdownOpen(false);
      setS3DropdownOpen(false);
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') {
        return;
      }
      setBucketDropdownOpen(false);
      setS3DropdownOpen(false);
    }

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  async function handleBrowseS3() {
    if (!bucket.trim()) {
      setS3Error('S3 bucket is required.');
      return;
    }
    setS3Status('loading');
    setS3Error(null);
    try {
      const response = await fetchS3Objects({bucket: bucket.trim(), prefix: prefix.trim(), limit: 40});
      setS3Objects(response.objects);
      setSelectedS3Uri((current) => (response.objects.some((item) => item.s3_uri === current) ? current : ''));
      setS3DropdownOpen(false);
      setS3Status('succeeded');
    } catch (error) {
      setS3Status('failed');
      setS3Error(asErrorMessage(error));
    }
  }

  async function handleParse() {
    if (!canParse) {
      return;
    }
    setParseStatus('loading');
    setParseError(null);
    setParseResult(null);
    setSelectedIssueId(null);
    try {
      const response =
        sourceMode === 'upload' && selectedFile
          ? await parseUpload({file: selectedFile, llmRequested, parserHint: parserHint || null})
          : await parseS3({s3_uri: effectiveS3Uri, llm_requested: llmRequested, parser_hint: parserHint || null});
      startTransition(() => {
        setParseResult(response);
      });
      setParseStatus('succeeded');
    } catch (error) {
      setParseStatus('failed');
      setParseError(asErrorMessage(error));
    }
  }

  const currentStage = getCurrentStage(parseStatus, parseResult);
  const issueCounts = summarizeIssues(parseResult);
  const timelineEvents = buildTimeline(parseResult?.trace.events || []);
  const progressStages = buildStageProgress(parseResult?.trace.events || [], parseStatus);
  const llmSummary = summarizeLlm(parseResult);

  return (
    <div className="app-shell">
      <Sidebar runtime={runtime} apiBase={getApiBase()} />
      <main className="workspace-shell">
        <Header
          health={health}
          bootstrapError={bootstrapError}
          enabledParsers={enabledParsers.length}
          currentStage={currentStage}
        />

        <div className="workspace-grid">
          <div className="source-row">
            <SourceSelectionCard
              rootRef={sourcePanelRef}
              sourceMode={sourceMode}
              setSourceMode={setSourceMode}
              selectedFile={selectedFile}
              onFileSelected={setSelectedFile}
              parserHint={parserHint}
              setParserHint={setParserHint}
              llmRequested={llmRequested}
              setLlmRequested={setLlmRequested}
              health={health}
              parseStatus={parseStatus}
              parseError={parseError}
              canParse={canParse}
              onParse={handleParse}
              enabledParsers={enabledParsers}
              currentStage={currentStage}
              bucket={bucket}
              bucketOptions={filteredBuckets}
              bucketDropdownOpen={bucketDropdownOpen}
              setBucketDropdownOpen={setBucketDropdownOpen}
              bucketQuery={bucketQuery}
              setBucketQuery={setBucketQuery}
              onSelectBucket={(name, label) => {
                setBucket(name);
                setBucketQuery('');
                setBucketDropdownOpen(false);
              }}
              setBucket={setBucket}
              prefix={prefix}
              setPrefix={setPrefix}
              s3Search={s3Search}
              setS3Search={setS3Search}
              s3Status={s3Status}
              s3Error={s3Error}
              objects={filteredObjects}
              selectedObject={selectedObject}
              selectedS3Uri={selectedS3Uri}
              onSelectS3Uri={setSelectedS3Uri}
              s3DropdownOpen={s3DropdownOpen}
              setS3DropdownOpen={setS3DropdownOpen}
            />
          </div>

          <div className="center-column">
            <ArtifactSummary parseResult={parseResult} issueCounts={issueCounts} llmSummary={llmSummary} />
            <EvaluationPanel parseResult={parseResult} />
            <MarkdownPreview parseResult={parseResult} selectedIssueId={selectedIssueId} />
          </div>

          <div className="right-rail">
            <TracePanel
              parseResult={parseResult}
              events={timelineEvents}
              progressStages={progressStages}
              currentStage={currentStage}
              parseStatus={parseStatus}
              llmSummary={llmSummary}
            />
            <IssuePanel parseResult={parseResult} selectedIssueId={selectedIssueId} onSelectIssue={setSelectedIssueId} />
          </div>
        </div>
      </main>
    </div>
  );
}

function Sidebar(props: {runtime: RuntimeParserStatus[]; apiBase: string}) {
  return (
    <aside className="sidebar">
      <div className="brand-lockup">
        <div className="brand-mark">
          <Network size={18} />
        </div>
        <div>
          <div className="brand-title">MarkBridge</div>
          <div className="brand-subtitle">Parsing workspace</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button key={item.label} className={item.active ? 'nav-item nav-item-active' : 'nav-item'} type="button">
            <item.icon size={18} />
            <span>{item.label}</span>
            {item.active ? <ChevronRight size={14} className="nav-chevron" /> : null}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="sidebar-note">Future-ready navigation is fixed now so later history, runtime, and validation screens can expand without relayout.</div>
        <RuntimePanel runtime={props.runtime} apiBase={props.apiBase} compact />
      </div>
    </aside>
  );
}

function Header(props: {
  health: HealthResponse | null;
  bootstrapError: string | null;
  enabledParsers: number;
  currentStage: string;
}) {
  return (
    <header className="topbar">
      <div>
        <h1>Source-faithful parsing monitor</h1>
        <p>Run upload or S3-backed parses, inspect trace events, and review handoff quality before downstream RAG processing.</p>
      </div>

      <div className="status-cluster">
        <StatusPill icon={Server} label={props.bootstrapError ? 'Backend unreachable' : props.health?.status || 'Connecting'} tone={props.bootstrapError ? 'error' : 'success'} />
        <StatusPill icon={Sparkles} label={props.health?.llm_configured ? `LLM ${props.health.azure_model}` : 'LLM not configured'} tone={props.health?.llm_configured ? 'accent' : 'neutral'} />
        <StatusPill icon={Activity} label={`${props.enabledParsers} parsers enabled`} tone="neutral" />
        <StatusPill icon={FolderKanban} label={`Stage: ${props.currentStage}`} tone="neutral" />
      </div>
    </header>
  );
}

function StatusPill(props: {
  icon: React.ComponentType<{size?: number; className?: string}>;
  label: string;
  tone: 'success' | 'accent' | 'neutral' | 'error';
}) {
  return (
    <span className={`status-pill status-${props.tone}`}>
      <props.icon size={14} />
      {props.label}
    </span>
  );
}

function SourceSelectionCard(props: {
  rootRef: React.RefObject<HTMLDivElement | null>;
  sourceMode: SourceMode;
  setSourceMode: (mode: SourceMode) => void;
  selectedFile: File | null;
  onFileSelected: (file: File | null) => void;
  parserHint: string;
  setParserHint: (value: string) => void;
  llmRequested: boolean;
  setLlmRequested: (value: boolean) => void;
  health: HealthResponse | null;
  parseStatus: AsyncStatus;
  parseError: string | null;
  canParse: boolean;
  onParse: () => void;
  enabledParsers: RuntimeParserStatus[];
  currentStage: string;
  bucket: string;
  bucketOptions: S3BucketOption[];
  bucketDropdownOpen: boolean;
  setBucketDropdownOpen: (value: boolean) => void;
  bucketQuery: string;
  setBucketQuery: (value: string) => void;
  onSelectBucket: (name: string, label: string) => void;
  setBucket: (value: string) => void;
  prefix: string;
  setPrefix: (value: string) => void;
  s3Search: string;
  setS3Search: (value: string) => void;
  s3Status: AsyncStatus;
  s3Error: string | null;
  objects: S3ObjectOption[];
  selectedObject: S3ObjectOption | null;
  selectedS3Uri: string;
  onSelectS3Uri: (uri: string) => void;
  s3DropdownOpen: boolean;
  setS3DropdownOpen: (value: boolean) => void;
}) {
  return (
    <section className="panel panel-elevated source-card" ref={props.rootRef}>
      <div className="panel-header">
        <div>
          <div className="panel-eyebrow">Source selection</div>
          <h2>Choose a document input</h2>
        </div>
        <div className="segmented">
          <button className={props.sourceMode === 'upload' ? 'segmented-active' : ''} type="button" onClick={() => props.setSourceMode('upload')}>
            Local
          </button>
          <button className={props.sourceMode === 's3' ? 'segmented-active' : ''} type="button" onClick={() => props.setSourceMode('s3')}>
            S3
          </button>
        </div>
      </div>

      {props.sourceMode === 'upload' ? (
        <label className="upload-dropzone">
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.doc,.hwp"
            onChange={(event) => props.onFileSelected(event.target.files?.[0] || null)}
          />
          <Upload size={18} />
          <div>
            <strong>{props.selectedFile ? props.selectedFile.name : 'Drop a file or browse locally'}</strong>
            <span>PDF, DOCX, XLSX, DOC, HWP</span>
          </div>
        </label>
      ) : (
        <div className="stack">
          <div className="field-grid">
            <Field label="Bucket / source group">
              <div className="combo-shell combo-shell-top">
                <button
                  className={props.bucketDropdownOpen ? 'combo-trigger combo-trigger-open' : 'combo-trigger'}
                  type="button"
                  onClick={() => {
                    props.setBucketDropdownOpen(!props.bucketDropdownOpen);
                    props.setBucketQuery('');
                  }}
                >
                  <div className="combo-selected">
                    <strong>{props.bucket || 'Select a bucket'}</strong>
                    <span>{props.bucket || 'Choose a bucket before loading S3 objects'}</span>
                  </div>
                  <ChevronsUpDown size={16} />
                </button>

                {props.bucketDropdownOpen ? (
                  <div className="combo-dropdown combo-dropdown-tight">
                    <div className="search-box">
                      <Search size={15} />
                      <input
                        value={props.bucketQuery}
                        onChange={(event) => {
                          props.setBucketQuery(event.target.value);
                          props.setBucketDropdownOpen(true);
                        }}
                        placeholder="Search available buckets"
                      />
                    </div>
                    <div className="bucket-list">
                      {props.bucketOptions.length === 0 ? (
                        <div className="empty-state">No buckets available.</div>
                      ) : (
                        props.bucketOptions.map((item) => (
                          <button
                            key={item.name}
                            className={item.name === props.bucket ? 'bucket-option bucket-option-active' : 'bucket-option'}
                            type="button"
                            onClick={() => props.onSelectBucket(item.name, item.label)}
                          >
                            <strong>{item.label}</strong>
                            <span>{item.name}</span>
                          </button>
                        ))
                      )}
                    </div>
                  </div>
                ) : null}
              </div>
            </Field>
            <Field label="Prefix">
              <input value={props.prefix} onChange={(event) => props.setPrefix(event.target.value)} placeholder="incoming/2026/" />
            </Field>
          </div>

          <div className="inline-actions">
            <span className="muted-copy">
              {props.s3Status === 'loading'
                ? 'Loading S3 files...'
                : props.objects.length > 0
                  ? `${props.objects.length} supported files loaded`
                  : 'Select a bucket to load available files automatically'}
            </span>
          </div>

          <Field label="Search available files">
            <div className="combo-shell">
              <button
                className={props.s3DropdownOpen ? 'combo-trigger combo-trigger-open' : 'combo-trigger'}
                type="button"
                onClick={() => props.setS3DropdownOpen(!props.s3DropdownOpen)}
              >
                <div className="combo-selected">
                  <strong>{props.selectedObject?.label || 'Select an S3 file'}</strong>
                  <span>{props.selectedObject?.key || 'Load objects, then search and choose a document'}</span>
                </div>
                <ChevronsUpDown size={16} />
              </button>

              {props.s3DropdownOpen ? (
                <div className="combo-dropdown" onMouseLeave={() => props.setS3DropdownOpen(false)}>
                  <div className="search-box">
                    <Search size={15} />
                    <input
                      value={props.s3Search}
                      onChange={(event) => props.setS3Search(event.target.value)}
                      placeholder="Search file names or keys"
                    />
                  </div>

                  <div className="s3-combobox">
                    {props.objects.length === 0 ? (
                      <div className="empty-state">No S3 objects loaded yet.</div>
                    ) : (
                      props.objects.map((item) => (
                        <button
                          key={item.s3_uri}
                          className={item.s3_uri === props.selectedS3Uri ? 's3-option s3-option-active' : 's3-option'}
                          type="button"
                          onClick={() => {
                            props.onSelectS3Uri(item.s3_uri);
                            props.setS3DropdownOpen(false);
                          }}
                        >
                          <div>
                            <strong>{item.label}</strong>
                            <span>{item.key}</span>
                          </div>
                          <div className="s3-meta">
                            <span>{item.document_format || 'unknown'}</span>
                            <span>{formatBytes(item.size_bytes)}</span>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                </div>
                ) : null}
            </div>
          </Field>

          {props.s3Error ? <div className="message message-error">{props.s3Error}</div> : null}
        </div>
      )}

      <div className="source-controls">
        <div className="field-grid field-grid-controls">
          <Field label="Parser hint">
            <select value={props.parserHint} onChange={(event) => props.setParserHint(event.target.value)}>
              <option value="">Automatic</option>
              {props.enabledParsers.map((item) => (
                <option key={item.parser_id} value={item.parser_id}>
                  {item.parser_id}
                </option>
              ))}
            </select>
          </Field>

          <Field label="LLM assist">
            <div className="field-stack">
              <button
                type="button"
                className={props.llmRequested ? 'toggle toggle-on' : 'toggle'}
                onClick={() => props.setLlmRequested(!props.llmRequested)}
              >
                <span>{props.llmRequested ? 'Enabled' : 'Disabled'}</span>
                <span className="toggle-knob" />
              </button>
            </div>
          </Field>

          <div className="run-strip run-strip-inline">
            <div>
              <div className="run-label">Current stage</div>
              <div className="run-value">{props.currentStage}</div>
            </div>
            <button className="button button-ink" type="button" onClick={props.onParse} disabled={!props.canParse || props.parseStatus === 'loading'}>
              {props.parseStatus === 'loading' ? <LoaderCircle size={16} className="spin" /> : <ArrowUpRight size={16} />}
              {props.parseStatus === 'loading' ? 'Running parse' : 'Start parse'}
            </button>
          </div>
        </div>

        {props.parseError ? <div className="message message-error">{props.parseError}</div> : null}
      </div>
    </section>
  );
}

function RuntimePanel(props: {runtime: RuntimeParserStatus[]; apiBase: string; compact?: boolean}) {
  return (
    <section className={props.compact ? 'panel panel-dark panel-dark-compact' : 'panel panel-dark'}>
      <div className="panel-header">
        <div>
          <div className="panel-eyebrow panel-eyebrow-dark">Runtime surface</div>
          <h2>Backend connectivity</h2>
        </div>
      </div>

      <div className="runtime-meta">
        <div>
          <span>API base</span>
          <strong>{props.apiBase}</strong>
        </div>
        <div>
          <span>Enabled parsers</span>
          <strong>{props.runtime.filter((item) => item.enabled).length}</strong>
        </div>
      </div>

      <div className="runtime-list">
        {props.runtime.map((item) => (
          <div key={item.parser_id} className="runtime-row">
            <div>
              <strong>{item.parser_id}</strong>
              <span>{item.reason || 'available'}</span>
            </div>
            <span className={item.enabled ? 'runtime-badge runtime-badge-on' : 'runtime-badge'}>{item.enabled ? 'enabled' : 'off'}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ArtifactSummary(props: {
  parseResult: ParseResponse | null;
  issueCounts: ReturnType<typeof summarizeIssues>;
  llmSummary: ReturnType<typeof summarizeLlm>;
}) {
  const summaryItems = [
    {label: 'Selected parser', value: props.parseResult?.routing.primary_parser || 'Not run yet'},
    {label: 'Document format', value: props.parseResult?.source.document_format || 'Pending'},
    {label: 'Handoff', value: props.parseResult?.handoff.decision || 'Pending', tone: props.parseResult?.handoff.decision || 'neutral'},
    {label: 'Issues', value: `${props.issueCounts.total}`, tone: props.issueCounts.errors > 0 ? 'error' : props.issueCounts.warnings > 0 ? 'warning' : 'success'},
    {label: 'LLM status', value: props.llmSummary.badge, tone: props.llmSummary.summaryTone},
    {
      label: 'Evaluation',
      value: props.parseResult ? `${humanizeEvaluationLabel(props.parseResult.evaluation.readiness_label)} ${props.parseResult.evaluation.readiness_score}` : '대기 중',
      tone: props.parseResult ? summarizeEvaluationTone(props.parseResult.evaluation.readiness_label) : 'neutral',
    },
  ];

  return (
    <section className="summary-grid">
      {summaryItems.map((item) => (
        <motion.article key={item.label} className="summary-card" initial={{opacity: 0, y: 12}} animate={{opacity: 1, y: 0}}>
          <span>{item.label}</span>
          <strong className={`summary-${item.tone || 'neutral'}`}>{item.value}</strong>
        </motion.article>
      ))}
    </section>
  );
}

function EvaluationPanel(props: {parseResult: ParseResponse | null}) {
  const evaluation = props.parseResult?.evaluation;
  const resolutionSummary = props.parseResult?.resolution_summary;
  const downstream = props.parseResult?.downstream_handoff;
  if (!evaluation) {
    return null;
  }

  const unresolvedClassEntries = resolutionSummary
    ? Object.entries(resolutionSummary.unresolved_by_class).sort((left, right) => right[1] - left[1])
    : [];
  const unresolvedReasonEntries = resolutionSummary
    ? Object.entries(resolutionSummary.unresolved_by_reason).sort((left, right) => right[1] - left[1])
    : [];
  const unresolvedIssues = resolutionSummary
    ? resolutionSummary.issues.filter((item) => !item.resolved).slice(0, 6)
    : [];

  return (
    <section className="panel evaluation-panel">
      <div className="panel-header">
        <div>
          <div className="panel-eyebrow">파싱 평가</div>
          <h2>복원 및 검토 상태</h2>
        </div>
        <span className={`chip chip-${summarizeEvaluationTone(evaluation.readiness_label)}`}>{humanizeEvaluationLabel(evaluation.readiness_label)}</span>
      </div>

      <div className="evaluation-score-row">
        <strong>{evaluation.readiness_score}</strong>
        <span>/100 준비도</span>
      </div>

      <div className="evaluation-grid">
        <div className="evaluation-metric">
          <span>복원 후보</span>
          <strong>{evaluation.repair_candidate_count}</strong>
        </div>
        <div className="evaluation-metric">
          <span>규칙 기반</span>
          <strong>{evaluation.deterministic_candidate_count}</strong>
        </div>
        <div className="evaluation-metric">
          <span>LLM</span>
          <strong>{evaluation.llm_candidate_count}</strong>
        </div>
        <div className="evaluation-metric">
          <span>적용된 패치</span>
          <strong>{evaluation.suggested_patch_count}</strong>
        </div>
        <div className="evaluation-metric">
          <span>Resolved issue</span>
          <strong>{resolutionSummary?.resolved_issue_count ?? 0}</strong>
        </div>
        <div className="evaluation-metric">
          <span>미해결</span>
          <strong>{resolutionSummary?.unresolved_repair_issue_count ?? evaluation.unresolved_repair_issue_count}</strong>
        </div>
      </div>

      {downstream ? (
        <div className="evaluation-status-strip">
          <div className="evaluation-status-card">
            <span>실제 downstream 기준</span>
            <strong>{humanizePreferredMarkdownKind(downstream.preferred_markdown_kind)}</strong>
          </div>
          <div className="evaluation-status-card">
            <span>handoff 정책</span>
            <strong>{humanizeHandoffPolicy(downstream.policy)}</strong>
          </div>
          <div className="evaluation-status-card">
            <span>검토 상태</span>
            <strong>{downstream.review_required ? '검토 필요' : '바로 전달 가능'}</strong>
          </div>
        </div>
      ) : null}

      <div className="evaluation-next-step">
        <span>다음 단계</span>
        <p>{humanizeEvaluationNextStep(evaluation.recommended_next_step)}</p>
      </div>

      {resolutionSummary && (unresolvedClassEntries.length > 0 || unresolvedReasonEntries.length > 0) ? (
        <div className="resolution-breakdown-grid">
          <div className="resolution-breakdown-card">
            <span>미해결 클래스</span>
            {unresolvedClassEntries.length > 0 ? (
              <div className="resolution-pill-list">
                {unresolvedClassEntries.map(([key, value]) => (
                  <div key={key} className="resolution-pill">
                    <strong>{value}</strong>
                    <span>{humanizeCorruptionClass(key)}</span>
                  </div>
                ))}
              </div>
            ) : <p>남은 미해결 클래스가 없습니다.</p>}
          </div>
          <div className="resolution-breakdown-card">
            <span>미해결 사유</span>
            {unresolvedReasonEntries.length > 0 ? (
              <div className="resolution-pill-list">
                {unresolvedReasonEntries.map(([key, value]) => (
                  <div key={key} className="resolution-pill">
                    <strong>{value}</strong>
                    <span>{humanizeUnresolvedReason(key)}</span>
                  </div>
                ))}
              </div>
            ) : <p>남은 미해결 사유가 없습니다.</p>}
          </div>
        </div>
      ) : null}

      {unresolvedIssues.length > 0 ? (
        <div className="resolution-issue-list">
          {unresolvedIssues.map((item) => (
            <article key={item.issue_id} className="resolution-issue-card">
              <div className="resolution-issue-head">
                <strong>{item.issue_id}</strong>
                <span>{item.corruption_class ? humanizeCorruptionClass(item.corruption_class) : 'unknown class'}</span>
              </div>
              <div className="resolution-issue-meta">
                <span>{item.llm_attempted ? 'LLM attempted' : item.llm_requested ? 'LLM requested' : 'LLM not requested'}</span>
                <span>{item.unresolved_reason ? humanizeUnresolvedReason(item.unresolved_reason) : 'resolved'}</span>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      <div className="llm-detail-list">
        {evaluation.rationale.map((detail) => (
          <div key={detail} className="llm-detail-row">
            {humanizeEvaluationRationale(detail)}
          </div>
        ))}
      </div>
    </section>
  );
}

function MarkdownPreview(props: {parseResult: ParseResponse | null; selectedIssueId: string | null}) {
  const [viewMode, setViewMode] = useState<'source' | 'resolved'>('source');
  const resolvedMarkdown = props.parseResult?.final_resolved_markdown || props.parseResult?.suggested_resolved_markdown || '';
  const resolvedPatches = props.parseResult?.final_resolved_patches || props.parseResult?.suggested_resolved_patches || [];
  const downstream = props.parseResult?.downstream_handoff || null;
  const canShowResolved = Boolean(resolvedMarkdown);
  const markdown = viewMode === 'resolved' && canShowResolved
    ? resolvedMarkdown
    : props.parseResult?.markdown || '';
  const lines = markdown.length > 0 ? markdown.split('\n') : [];
  const highlightMap = buildMarkdownHighlightMap(props.parseResult);
  const resolvedPatchOriginByLine = buildResolvedPatchOriginByLine(resolvedPatches);
  const patchOriginCounts = countPatchOrigins(resolvedPatches);
  const lineRefs = useRef(new Map<number, HTMLDivElement>());

  useEffect(() => {
    if (!canShowResolved && viewMode === 'resolved') {
      setViewMode('source');
    }
  }, [canShowResolved, viewMode]);

  useEffect(() => {
    if (!props.selectedIssueId) {
      return;
    }
    const targetLine = Array.from(highlightMap.entries()).find(([, value]) => value.issueIds.includes(props.selectedIssueId))?.[0];
    if (!targetLine) {
      return;
    }
    const element = lineRefs.current.get(targetLine);
    element?.scrollIntoView({block: 'center', behavior: 'smooth'});
  }, [highlightMap, props.selectedIssueId]);

  function handleDownloadMarkdown() {
    if (!markdown) {
      return;
    }
    const filename = buildMarkdownDownloadFilename(props.parseResult, viewMode);
    downloadTextFile(markdown, filename, 'text/markdown;charset=utf-8');
  }

  return (
    <section className="panel preview-panel">
      <div className="panel-header">
        <div>
          <div className="panel-eyebrow">Markdown preview</div>
          <h2>Rendered handoff content</h2>
        </div>
        <div className="preview-header-actions">
          {canShowResolved ? (
            <div className="preview-toggle">
              <button
                type="button"
                className={viewMode === 'source' ? 'preview-toggle-btn preview-toggle-btn-active' : 'preview-toggle-btn'}
                onClick={() => setViewMode('source')}
              >
                Source
              </button>
              <button
                type="button"
                className={viewMode === 'resolved' ? 'preview-toggle-btn preview-toggle-btn-active' : 'preview-toggle-btn'}
                onClick={() => setViewMode('resolved')}
              >
                Final resolved
              </button>
            </div>
          ) : null}
          <button
            type="button"
            className="button button-ink preview-download-btn"
            onClick={handleDownloadMarkdown}
            disabled={!markdown}
          >
            Markdown 다운로드
          </button>
          <span className="muted-copy">{describePreviewMode(viewMode, downstream?.preferred_markdown_kind || 'source')}</span>
        </div>
      </div>

      {downstream ? (
        <div className="preview-decision-banner">
          <span className={downstream.preferred_markdown_kind === viewMode ? 'issue-tag issue-tag-ok' : 'issue-tag issue-tag-warn'}>
            {downstream.preferred_markdown_kind === viewMode ? '현재 화면이 downstream 기준 본문입니다' : `실제 downstream은 ${humanizePreferredMarkdownKind(downstream.preferred_markdown_kind)} 기준입니다`}
          </span>
          <span className="muted-copy muted-copy-tight">
            {downstream.review_required ? '이 run은 review_required 상태입니다.' : '현재 정책상 추가 검토 없이 전달 가능한 상태입니다.'}
          </span>
        </div>
      ) : null}

      {canShowResolved ? (
        <div className="resolved-preview-summary">
          <span className="issue-tag issue-tag-accent">Final patches {resolvedPatches.length}</span>
          {patchOriginCounts.llm > 0 ? <span className="issue-tag issue-tag-accent">LLM patched {patchOriginCounts.llm}</span> : null}
          {patchOriginCounts.deterministic > 0 ? <span className="issue-tag issue-tag-ok">Deterministic patched {patchOriginCounts.deterministic}</span> : null}
          <span className="muted-copy muted-copy-tight">
            규칙 기반과 LLM 복원 결과를 반영한 최종 downstream 후보입니다. 원본 markdown은 audit과 fallback 용으로 함께 유지됩니다.
          </span>
        </div>
      ) : null}

      <div className="markdown-surface">
        {markdown ? (
          <div className="markdown-lines">
            {lines.map((line, index) => {
              const lineNumber = index + 1;
              const highlight = highlightMap.get(lineNumber);
              const resolvedPatchOrigin = viewMode === 'resolved' ? resolvedPatchOriginByLine.get(lineNumber) || null : null;
              const isResolvedPatchLine = resolvedPatchOrigin !== null;
              return (
                <div
                  key={`${lineNumber}:${line}`}
                  ref={(node) => {
                    if (node) {
                      lineRefs.current.set(lineNumber, node);
                    } else {
                      lineRefs.current.delete(lineNumber);
                    }
                  }}
                  className={
                    highlight
                      ? props.selectedIssueId && highlight.issueIds.includes(props.selectedIssueId)
                        ? `markdown-line markdown-line-alert markdown-line-selected${isResolvedPatchLine ? ' markdown-line-resolved' : ''}`
                        : `markdown-line markdown-line-alert${isResolvedPatchLine ? ' markdown-line-resolved' : ''}`
                      : isResolvedPatchLine ? 'markdown-line markdown-line-resolved' : 'markdown-line'
                  }
                >
                  <span className="markdown-line-no">{lineNumber}</span>
                  <span className="markdown-line-text">
                    {highlight ? renderHighlightedLine(line, highlight.text) : line || ' '}
                  </span>
                  {resolvedPatchOrigin ? <span className={`markdown-line-badge markdown-line-badge-${resolvedPatchOrigin}`}>{humanizePatchOriginBadge(resolvedPatchOrigin)}</span> : null}
                </div>
              );
            })}
          </div>
        ) : <div className="empty-state empty-state-large">Run a parse to populate markdown output.</div>}
      </div>
    </section>
  );
}

function downloadTextFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], {type: mimeType});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function buildMarkdownDownloadFilename(result: ParseResponse | null, viewMode: 'source' | 'resolved'): string {
  const sourceName = (result?.source.name || 'markbridge-output').replace(/\.[^.]+$/, '');
  const suffix = viewMode === 'resolved' ? 'resolved' : 'source';
  return sanitizeFilename(`${sourceName}-${suffix}.md`);
}

function sanitizeFilename(value: string): string {
  return value.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, '_');
}

function TracePanel(props: {
  parseResult: ParseResponse | null;
  events: TraceEvent[];
  progressStages: StageProgress[];
  currentStage: string;
  parseStatus: AsyncStatus;
  llmSummary: ReturnType<typeof summarizeLlm>;
}) {
  const [showRawTrace, setShowRawTrace] = useState(false);
  const activeStage = props.progressStages.find((stage) => stage.status === 'running') || null;
  const completedStages = props.progressStages.filter((stage) => stage.status === 'succeeded' || stage.status === 'degraded');
  const issueInsights = buildIssueInsights(props.parseResult);
  const hasRunState = props.parseStatus === 'loading' || props.events.length > 0;
  const showLlmCard = props.parseResult !== null;
  const showCompletedStages = completedStages.length > 0;
  const showRawTraceToggle = props.events.length > 0;
  const downstream = props.parseResult?.downstream_handoff || null;
  const recoverySummary = summarizeRecoveryFlow(props.parseResult);

  return (
    <section className="panel trace-panel">
      <div className="panel-header panel-header-inline">
        <div className="trace-title-row">
          <div className="panel-eyebrow">Pipeline progress</div>
        </div>
        <span className={`chip chip-${props.parseStatus}`}>{props.parseStatus}</span>
      </div>

      <div className="progress-strip">
        {props.progressStages.map((stage) => (
          <div key={stage.stage} className="progress-node">
            <div className={`progress-dot progress-${stage.status}`}>{renderStageIcon(stage.status)}</div>
            <div className="progress-label">{stage.stage}</div>
          </div>
        ))}
      </div>

      {!hasRunState ? (
        <div className="empty-state empty-state-soft">Start a parse run to populate active stages, issue findings, and raw trace details here.</div>
      ) : activeStage ? (
        <article className="live-stage-card">
          <div className="live-stage-header">
            <div>
              <div className="panel-eyebrow">Active stage</div>
              <strong>{activeStage.stage}</strong>
            </div>
            <span className="live-badge">Running</span>
          </div>
          <p>{activeStage.message || 'Stage is currently in progress.'}</p>
          <div className="trace-meta">
            <span>{activeStage.component || 'pipeline.orchestrator'}</span>
            <span>{activeStage.timestamp ? formatTimestamp(activeStage.timestamp) : 'live'}</span>
          </div>
        </article>
      ) : props.events.length > 0 ? (
        <article className="live-stage-card live-stage-card-idle">
          <div className="live-stage-header">
            <div>
              <div className="panel-eyebrow">Run status</div>
              <strong>{props.parseStatus === 'succeeded' ? 'Pipeline completed' : 'Waiting for next run'}</strong>
            </div>
          </div>
          <p>{props.parseStatus === 'succeeded' ? 'All stages finished and artifacts were recorded.' : 'Start a parse run to see live pipeline progress.'}</p>
        </article>
      ) : (
        <div className="empty-state">No trace events yet.</div>
      )}

      {issueInsights.length > 0 ? (
        <div className="issue-insight-list">
          <div className="panel-eyebrow">Detected issues</div>
          {issueInsights.map((insight) => (
            <article key={insight.issueId} className="issue-insight-card">
              <div className="issue-insight-head">
                <strong>{insight.title}</strong>
                <span>{insight.location}</span>
              </div>
              <div className="issue-insight-row">
                <span>What</span>
                <p>{insight.problem}</p>
              </div>
              <div className="issue-insight-row">
                <span>Evidence</span>
                <p>{insight.evidence}</p>
              </div>
              <div className="issue-insight-row">
                <span>Why</span>
                <p>{insight.cause}</p>
              </div>
              <div className="issue-insight-row">
                <span>Action</span>
                <p>{insight.action}</p>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {showLlmCard ? (
        <article className="llm-card">
          <div className="llm-card-head">
            <div>
              <div className="panel-eyebrow">LLM assist</div>
              <strong>{props.llmSummary.primaryLabel}</strong>
            </div>
            <span className={`llm-badge llm-badge-${props.llmSummary.tone}`}>{props.llmSummary.badge}</span>
          </div>
          <div className="recovery-step-grid">
            {props.llmSummary.subsystems.map((item) => (
              <div key={item.label} className="recovery-step-card">
                <span>{item.label}</span>
                <strong>{item.badge}</strong>
              </div>
            ))}
          </div>
          {props.llmSummary.details.length > 0 ? (
            <div className="llm-detail-list">
              {props.llmSummary.details.map((detail) => (
                <div key={detail} className="llm-detail-row">
                  {detail}
                </div>
              ))}
            </div>
          ) : null}
          {props.llmSummary.responsePreview.length > 0 ? (
            <div className="llm-preview-list">
              <div className="panel-eyebrow">Repair response preview</div>
              {props.llmSummary.responsePreview.map((detail) => (
                <div key={detail} className="llm-preview-row">
                  {humanizeLlmResponsePreview(detail)}
                </div>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}

      {recoverySummary ? (
        <article className="llm-card">
          <div className="llm-card-head">
            <div>
              <div className="panel-eyebrow">Recovery flow</div>
              <strong>{recoverySummary.title}</strong>
            </div>
            <span className={`llm-badge llm-badge-${recoverySummary.tone}`}>{recoverySummary.badge}</span>
          </div>
          <div className="recovery-step-grid">
            {recoverySummary.metrics.map((item) => (
              <div key={item.label} className="recovery-step-card">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
          {recoverySummary.details.length > 0 ? (
            <div className="llm-detail-list">
              {recoverySummary.details.map((detail) => (
                <div key={detail} className="llm-detail-row">
                  {detail}
                </div>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}

      {downstream ? (
        <article className="llm-card">
          <div className="llm-card-head">
            <div>
              <div className="panel-eyebrow">Downstream handoff</div>
              <strong>{humanizeHandoffPolicy(downstream.policy)}</strong>
            </div>
            <span className={`llm-badge llm-badge-${downstream.review_required ? 'warning' : 'success'}`}>
              {downstream.review_required ? '검토 필요' : '전달 준비 완료'}
            </span>
          </div>
          <div className="llm-detail-list">
            <div className="llm-detail-row">기준 markdown: {humanizePreferredMarkdownKind(downstream.preferred_markdown_kind)}</div>
            <div className="llm-detail-row">최종 resolved 사용 가능: {downstream.final_resolved_available ? '예' : '아니오'}</div>
            <div className="llm-detail-row">resolved 사본 사용 가능: {downstream.suggested_resolved_available ? '예' : '아니오'}</div>
            {downstream.rationale.map((detail) => (
              <div key={detail} className="llm-detail-row">
                {humanizeDownstreamRationale(detail)}
              </div>
            ))}
          </div>
        </article>
      ) : null}

      {showCompletedStages ? (
        <div className="completed-stage-list">
          <div className="panel-eyebrow">Completed stages</div>
          {completedStages.map((stage) => (
            <article key={stage.stage} className="completed-stage-row">
              <div className={`trace-dot trace-${stage.status}`} />
              <div className="trace-body">
                <div className="trace-head">
                  <strong>{stage.stage}</strong>
                  <span>{stage.timestamp ? formatTimestamp(stage.timestamp) : stage.status}</span>
                </div>
                <p>{stage.message}</p>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {showRawTraceToggle ? (
        <div className="raw-trace-section">
          <button className="raw-trace-toggle" type="button" onClick={() => setShowRawTrace(!showRawTrace)}>
            <span>{showRawTrace ? 'Hide raw trace events' : 'View raw trace events'}</span>
            <ChevronRight className={showRawTrace ? 'raw-trace-chevron raw-trace-chevron-open' : 'raw-trace-chevron'} size={16} />
          </button>

          {showRawTrace ? (
            <div className="trace-list">
              {props.events.map((event) => (
                <article key={event.event_id} className="trace-item">
                  <div className={`trace-dot trace-${event.status}`} />
                  <div className="trace-body">
                    <div className="trace-head">
                      <strong>{event.stage}</strong>
                      <span>{formatTimestamp(event.timestamp)}</span>
                    </div>
                    <p>{event.message}</p>
                    <div className="trace-meta">
                      <span>{event.component}</span>
                      <span>{event.status}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function IssuePanel(props: {
  parseResult: ParseResponse | null;
  selectedIssueId: string | null;
  onSelectIssue: (issueId: string) => void;
}) {
  const issues = sortIssuesForDisplay(props.parseResult);
  const corruptionIssues = issues.filter((issue) => issue.code === 'text_corruption');
  const detectorTags = summarizeCorruptionDetectors(corruptionIssues);
  const repairItems = buildRepairReviewItems(props.parseResult, props.selectedIssueId);

  return (
    <section className="panel issue-panel">
      <div className="panel-header">
        <div>
          <div className="panel-eyebrow">Validation review</div>
          <h2>Issues and evidence</h2>
        </div>
        <span className="muted-copy">{issues.length} records</span>
      </div>

      <div className="issue-list">
        {issues.length === 0 ? (
          <div className="empty-state">No validation issues yet.</div>
        ) : (
          <>
            {corruptionIssues.length > 0 ? (
              <article className="corruption-banner">
                <div className="corruption-banner-head">
                  <div>
                    <div className="panel-eyebrow">Corruption detected</div>
                    <strong>{corruptionIssues.length} text corruption findings need review</strong>
                  </div>
                  <span className="llm-badge llm-badge-warning">Review first</span>
                </div>
                <p>PDF parsing produced suspicious glyphs or undecoded formula placeholders. Review these findings before trusting chunk-ready markdown.</p>
                {detectorTags.length > 0 ? (
                  <div className="issue-tag-list">
                    {detectorTags.map((tag) => (
                      <span key={tag} className="issue-tag issue-tag-warn">
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ) : null}

            {repairItems.length > 0 ? (
              <div className="repair-review-list">
                <div className="panel-eyebrow">Repair candidates</div>
                {repairItems.map((item) => (
                  <article
                    key={`${item.issueId}:${item.locationHint || item.normalizedMath || item.candidateText || 'candidate'}`}
                    className={props.selectedIssueId === item.issueId ? 'repair-card repair-card-selected' : 'repair-card'}
                    onClick={() => props.onSelectIssue(item.issueId)}
                  >
                    <div className="repair-card-head">
                      <div>
                        <strong>{item.title}</strong>
                        <span>{item.locationLabel}</span>
                      </div>
                      <span className="repair-confidence">{item.confidenceLabel}</span>
                    </div>

                    <div className="repair-row">
                      <span>Original</span>
                      <p>{item.sourceText}</p>
                    </div>

                    {item.candidateText ? (
                      <div className="repair-row">
                        <span>Candidate</span>
                        <p>{item.candidateText}</p>
                      </div>
                    ) : null}

                    {item.normalizedMath ? (
                      <div className="repair-row">
                        <span>Math</span>
                        <code>{item.normalizedMath}</code>
                      </div>
                    ) : null}

                    <div className="repair-row">
                      <span>Why</span>
                      <p>{item.rationale}</p>
                    </div>

                    <div className="repair-chip-row">
                      <span className={item.selected ? 'issue-tag issue-tag-ok' : 'issue-tag issue-tag-warn'}>
                        {item.selected ? 'Selected winner' : 'Rejected'}
                      </span>
                      <span className={item.origin === 'llm' ? 'issue-tag issue-tag-accent' : 'issue-tag'}>
                        {item.origin === 'llm' ? 'LLM proposal' : 'Deterministic base'}
                      </span>
                      <span className="issue-tag issue-tag-warn">{item.strategyLabel}</span>
                      {!item.llmRecommended && item.origin === 'deterministic' ? (
                        <span className="issue-tag issue-tag-ok">Structured baseline</span>
                      ) : null}
                      {item.patchAction ? <span className="issue-tag">Patch: {item.patchAction}</span> : null}
                      {item.llmRecommended ? <span className="issue-tag">LLM review</span> : null}
                      {item.patchUncertain ? <span className="issue-tag issue-tag-warn">Uncertain</span> : <span className="issue-tag issue-tag-ok">Low uncertainty</span>}
                    </div>

                    <div className="repair-process-row">
                      {item.processPath.map((step) => (
                        <span key={`${item.issueId}:${step}`} className="repair-process-step">
                          {step}
                        </span>
                      ))}
                    </div>

                    <div className="repair-decision-box">
                      <div className="repair-row">
                        <span>Decision</span>
                        <p>
                          {item.selected
                            ? humanizeSelectionReason(item.selectionReason, item.selectedOrigin, item.selectedConfidence)
                            : humanizeCandidateRejectionReason(item.rejectedReason)}
                        </p>
                      </div>
                      {!item.issueResolved && item.issueUnresolvedReason ? (
                        <div className="repair-row">
                          <span>Issue state</span>
                          <p>{humanizeUnresolvedReason(item.issueUnresolvedReason)}</p>
                        </div>
                      ) : null}
                    </div>

                    {item.patchReplacementText ? (
                      <div className="repair-patch-box">
                        <div className="repair-patch-head">
                          <strong>Patch proposal</strong>
                          <span>{item.locationLabel}</span>
                        </div>

                        {item.patchTargetText ? (
                          <div className="repair-row">
                            <span>Replace</span>
                            <p>{item.patchTargetText}</p>
                          </div>
                        ) : null}

                        <div className="repair-row">
                          <span>With</span>
                          <p>{item.patchReplacementText}</p>
                        </div>
                      </div>
                    ) : null}
                  </article>
                ))}
                {props.parseResult?.repair_candidates && props.parseResult.repair_candidates.length > repairItems.length ? (
                  <div className="muted-copy muted-copy-tight">
                    Showing {repairItems.length} of {props.parseResult.repair_candidates.length} repair candidates. Select an issue to focus a specific formula.
                  </div>
                ) : null}
              </div>
            ) : null}

            {issues.map((issue) => {
              const details = getIssueDetails(issue);
              const markdownLine = findIssueMarkdownLine(props.parseResult, issue);
              const locationHint =
                issue.excerpts[0]?.location_hint
                || readNestedString(issue.metadata, ['location', 'line_hint'])
                || readNestedString(issue.metadata, ['location', 'block_ref'])
                || issue.block_ref;
              const detailTags = details.detectors.length > 0 ? details.detectors : [];
              const problemText = issue.excerpts[0]?.highlight_text || issue.excerpts[0]?.content || null;

              return (
                <article
                  key={issue.issue_id}
                  className={
                    props.selectedIssueId === issue.issue_id
                      ? `issue-card issue-${issue.severity} issue-card-selected`
                      : `issue-card issue-${issue.severity}`
                  }
                  onClick={() => props.onSelectIssue(issue.issue_id)}
                >
                  <div className="issue-head">
                    <span className="issue-code">{issue.code}</span>
                    <span className="issue-stage">{markdownLine ? `line ${markdownLine}` : issue.stage}</span>
                  </div>
                  <p>{issue.message}</p>

                  {locationHint ? <div className="issue-location">{locationHint}</div> : null}

                  {detailTags.length > 0 ? (
                    <div className="issue-tag-list">
                      {detailTags.map((tag) => (
                        <span key={tag} className={issue.code === 'text_corruption' ? 'issue-tag issue-tag-warn' : 'issue-tag'}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {problemText ? (
                    <div className="issue-problem-block">
                      <span>problem text</span>
                      <strong>{problemText}</strong>
                    </div>
                  ) : null}

                  {issue.excerpts[0] ? (
                    <pre>
                      {issue.excerpts[0].content}
                      {issue.excerpts[0].highlight_text ? `\n\nhighlight: ${issue.excerpts[0].highlight_text}` : ''}
                    </pre>
                  ) : null}
                </article>
              );
            })}
          </>
        )}
      </div>
    </section>
  );
}

function Field(props: {label: string; children: React.ReactNode}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      {props.children}
    </label>
  );
}

function buildTimeline(events: TraceEvent[]): TraceEvent[] {
  if (events.length === 0) {
    return [];
  }
  return [...events].sort((a, b) => {
    const stageDelta = STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage);
    if (stageDelta !== 0) {
      return stageDelta;
    }
    return a.timestamp.localeCompare(b.timestamp);
  });
}

type StageProgress = {
  stage: string;
  status: 'pending' | 'running' | 'succeeded' | 'degraded' | 'failed';
  message: string;
  component: string;
  timestamp: string;
};

function buildStageProgress(events: TraceEvent[], parseStatus: AsyncStatus): StageProgress[] {
  const orderedEvents = buildTimeline(events);
  return STAGE_ORDER.map((stageName) => {
    const stageEvents = orderedEvents.filter((event) => event.stage === stageName);
    const latestEvent = stageEvents[stageEvents.length - 1];
    if (!latestEvent) {
      return {
        stage: stageName,
        status: parseStatus === 'loading' && stageName === 'ingest' && orderedEvents.length === 0 ? 'running' : 'pending',
        message: '',
        component: '',
        timestamp: '',
      };
    }
    return {
      stage: stageName,
      status: latestEvent.status,
      message: latestEvent.message,
      component: latestEvent.component,
      timestamp: latestEvent.timestamp,
    };
  });
}

function renderStageIcon(status: StageProgress['status']) {
  if (status === 'succeeded' || status === 'degraded') {
    return <CheckCircle2 size={14} />;
  }
  if (status === 'running') {
    return <LoaderCircle size={14} className="spin" />;
  }
  return <CircleDashed size={14} />;
}

function summarizeIssues(result: ParseResponse | null) {
  const issues = result?.issues || [];
  return {
    total: issues.length,
    warnings: issues.filter((issue) => issue.severity === 'warning').length,
    errors: issues.filter((issue) => issue.severity === 'error').length,
  };
}

function prioritizeIssues(issues: ParseResponse['issues']) {
  return [...issues].sort((left, right) => issuePriority(right) - issuePriority(left));
}

function issuePriority(issue: ParseResponse['issues'][number]) {
  if (issue.code === 'text_corruption') {
    return 30;
  }
  if (issue.severity === 'error') {
    return 20;
  }
  if (issue.severity === 'warning') {
    return 10;
  }
  return 0;
}

function getIssueDetails(issue: ParseResponse['issues'][number]) {
  const raw = issue.metadata.details;
  const details = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
  const detectors = Array.isArray(details.detectors)
    ? details.detectors.filter((item): item is string => typeof item === 'string').map(humanizeDetector)
    : [];
  return {detectors};
}

function summarizeCorruptionDetectors(issues: ParseResponse['issues']) {
  return Array.from(new Set(issues.flatMap((issue) => getIssueDetails(issue).detectors)));
}

function sortIssuesForDisplay(result: ParseResponse | null) {
  const issues = result?.issues || [];
  return [...issues].sort((left, right) => {
    const leftLine = findIssueMarkdownLine(result, left) || Number.MAX_SAFE_INTEGER;
    const rightLine = findIssueMarkdownLine(result, right) || Number.MAX_SAFE_INTEGER;
    if (leftLine !== rightLine) {
      return leftLine - rightLine;
    }
    return issuePriority(right) - issuePriority(left);
  });
}

function findIssueMarkdownLine(result: ParseResponse | null, issue: ParseResponse['issues'][number]) {
  if (!result?.markdown) {
    return null;
  }
  const refs = issueRefs(issue);
  const lineMap = result.markdown_line_map || [];
  const mappedLine = lineMap.find((line) => line.refs.some((ref) => refs.includes(ref)));
  if (mappedLine) {
    return mappedLine.line_number;
  }
  const lines = result.markdown.split('\n');
  for (const excerpt of issue.excerpts) {
    const token = excerpt.highlight_text?.trim() || excerpt.content.trim();
    if (!token) {
      continue;
    }
    const containsLineIndex = lines.findIndex((line) => line.includes(token));
    if (containsLineIndex >= 0) {
      return containsLineIndex + 1;
    }
  }
  return null;
}

function buildMarkdownHighlightMap(result: ParseResponse | null) {
  const map = new Map<number, {text: string; issueIds: string[]}>();
  if (!result?.markdown) {
    return map;
  }
  const lineMap = result.markdown_line_map || [];

  for (const issue of result.issues.filter((item) => item.code === 'text_corruption')) {
    const highlight = issue.excerpts[0]?.highlight_text?.trim() || issue.excerpts[0]?.content.trim() || '';
    if (!highlight) {
      continue;
    }

    const refs = issueRefs(issue);
    const mappedLines = lineMap.filter((line) => line.refs.some((ref) => refs.includes(ref)));
    for (const line of mappedLines) {
      assignHighlight(map, line.line_number, highlight, issue.issue_id);
    }

    if (mappedLines.length === 0) {
      const lines = result.markdown.split('\n');
      const containsLineIndex = lines.findIndex((line) => line.includes(highlight));
      if (containsLineIndex >= 0) {
        assignHighlight(map, containsLineIndex + 1, highlight, issue.issue_id);
      }
    }
  }

  return map;
}

function assignHighlight(
  map: Map<number, {text: string; issueIds: string[]}>,
  lineNumber: number,
  highlight: string,
  issueId: string | null,
) {
  const current = map.get(lineNumber);
  if (!current) {
    map.set(lineNumber, {text: highlight, issueIds: issueId ? [issueId] : []});
    return;
  }
  if (highlight.length > current.text.length) {
    current.text = highlight;
  }
  if (issueId && !current.issueIds.includes(issueId)) {
    current.issueIds.push(issueId);
  }
}

function issueRefs(issue: ParseResponse['issues'][number]) {
  return [
    issue.block_ref,
    readNestedString(issue.metadata, ['location', 'line_hint']),
    ...issue.excerpts.map((excerpt) => excerpt.location_hint),
  ].filter((value): value is string => Boolean(value));
}

function buildRepairReviewItems(result: ParseResponse | null, selectedIssueId: string | null) {
  if (!result?.repair_candidates?.length) {
    return [];
  }

  const issueSummaryById = new Map(
    (result.resolution_summary?.issues || []).map((item) => [item.issue_id, item]),
  );
  const candidateIndicesByIssue = new Map<string, number>();
  const items = result.repair_candidates
    .map((candidate) => {
      const issue = result.issues.find((item) => item.issue_id === candidate.issue_id) || null;
      const issueSummary = issueSummaryById.get(candidate.issue_id) || null;
      const lineNumber = candidate.markdown_line_number || (issue ? findIssueMarkdownLine(result, issue) : null);
      const patchProposal = candidate.patch_proposal;
      const candidateIndex = candidateIndicesByIssue.get(candidate.issue_id) || 0;
      candidateIndicesByIssue.set(candidate.issue_id, candidateIndex + 1);
      const decision = issueSummary?.candidate_decisions.find((item) => item.candidate_index === candidateIndex) || null;
      return {
        issueId: candidate.issue_id,
        title: candidate.repair_type === 'formula_reconstruction' ? 'Formula reconstruction candidate' : candidate.repair_type,
        locationHint: candidate.location_hint,
        locationLabel: lineNumber ? `line ${lineNumber}` : candidate.location_hint || 'repair review',
        origin: candidate.origin,
        sourceText: candidate.source_text,
        candidateText: candidate.candidate_text,
        normalizedMath: candidate.normalized_math,
        confidenceLabel: `${Math.round(candidate.confidence * 100)}%`,
        rationale: candidate.rationale,
        llmRecommended: candidate.llm_recommended,
        strategyLabel: humanizeRepairStrategy(candidate.strategy),
        patchAction: patchProposal?.action || null,
        patchTargetText: patchProposal?.target_text || null,
        patchReplacementText: patchProposal?.replacement_text || null,
        patchUncertain: patchProposal?.uncertain ?? true,
        processPath: describeRepairPath(candidate, result),
        selected: decision?.selected ?? false,
        selectedOrigin: issueSummary?.selected_origin || null,
        selectedConfidence: issueSummary?.selected_confidence ?? null,
        selectionReason: issueSummary?.selection_reason || null,
        rejectedReason: decision?.rejected_reason || null,
        issueResolved: issueSummary?.resolved ?? false,
        issueUnresolvedReason: issueSummary?.unresolved_reason || null,
        lineNumber: lineNumber || Number.MAX_SAFE_INTEGER,
      };
    })
    .sort((left, right) => {
      if (selectedIssueId) {
        if (left.issueId === selectedIssueId && right.issueId !== selectedIssueId) {
          return -1;
        }
        if (right.issueId === selectedIssueId && left.issueId !== selectedIssueId) {
          return 1;
        }
      }
      return left.lineNumber - right.lineNumber;
    });

  if (selectedIssueId) {
    const selectedItems = items.filter((item) => item.issueId === selectedIssueId);
    if (selectedItems.length > 0) {
      return selectedItems;
    }
  }

  return items.slice(0, 8);
}

function renderHighlightedLine(line: string, highlight: string) {
  const index = line.indexOf(highlight);
  if (index < 0) {
    return line;
  }
  const before = line.slice(0, index);
  const matched = line.slice(index, index + highlight.length);
  const after = line.slice(index + highlight.length);
  return (
    <>
      {before}
      <mark>{matched}</mark>
      {after}
    </>
  );
}

function humanizeRepairStrategy(strategy: string) {
  if (strategy === 'llm_required') {
    return 'LLM required';
  }
  if (strategy === 'deterministic_transliteration_with_llm_review') {
    return 'Transliteration + review';
  }
  if (strategy === 'llm_formula_reconstruction') {
    return 'LLM patch proposal';
  }
  return strategy.replaceAll('_', ' ');
}

function humanizeHandoffPolicy(policy: string) {
  if (policy === 'dual_track_review') {
    return 'Dual-track review';
  }
  if (policy === 'resolved_preferred') {
    return 'Resolved preferred';
  }
  if (policy === 'resolved_with_fallback') {
    return 'Resolved with fallback';
  }
  if (policy === 'source_only') {
    return 'Source only';
  }
  return policy.replaceAll('_', ' ');
}

function summarizeEvaluationTone(label: string) {
  if (label === 'ready') {
    return 'success';
  }
  if (label === 'reviewable') {
    return 'warning';
  }
  return 'error';
}

function humanizeEvaluationLabel(label: string) {
  if (label === 'ready') {
    return '준비 완료';
  }
  if (label === 'reviewable') {
    return '검토 가능';
  }
  if (label === 'fragile') {
    return '주의 필요';
  }
  return label;
}

function humanizeEvaluationNextStep(step: string) {
  if (step === 'Proceed with final resolved markdown as canonical downstream input.') {
    return '최종 resolved markdown을 기준 본문으로 사용해 downstream으로 진행하면 됩니다.';
  }
  if (step === 'Proceed with source markdown as canonical downstream input.') {
    return '현재 source markdown을 기준 원문으로 사용해 downstream으로 진행하면 됩니다.';
  }
  if (step === 'Use final resolved markdown for downstream and keep source markdown for audit.') {
    return 'downstream에는 최종 resolved markdown을 사용하고, source markdown은 audit과 fallback 용으로 유지하면 됩니다.';
  }
  if (step === 'Use source markdown for downstream and inspect suggested repairs before canonicalization.') {
    return 'downstream에는 source markdown을 사용하고, 기준 원문으로 확정하기 전에 복원 제안을 검토해야 합니다.';
  }
  if (step === 'Inspect repair candidates before trusting the parse for downstream indexing.') {
    return '이 파싱 결과를 downstream 인덱싱에 바로 쓰기 전에 복원 후보를 먼저 확인해야 합니다.';
  }
  return step;
}

function humanizeEvaluationRationale(detail: string) {
  if (detail.startsWith('Detected issues: ')) {
    return `감지된 이슈: ${detail.replace('Detected issues: ', '')}`;
  }
  if (detail.startsWith('Repair candidates: ')) {
    return `생성된 복원 후보: ${detail.replace('Repair candidates: ', '')}`;
  }
  if (detail.startsWith('LLM reconstructions generated: ')) {
    return `LLM 복원 후보 생성: ${detail.replace('LLM reconstructions generated: ', '')}`;
  }
  if (detail.startsWith('Suggested resolved patches applied: ')) {
    return `최종 보정본에 적용된 패치: ${detail.replace('Suggested resolved patches applied: ', '')}`;
  }
  if (detail.startsWith('High-structure deterministic candidates: ')) {
    return `구조가 잘 복원된 규칙 기반 후보: ${detail.replace('High-structure deterministic candidates: ', '')}`;
  }
  if (detail.startsWith('Deterministic candidates still recommending LLM review: ')) {
    return `아직 LLM 검토가 필요한 규칙 기반 후보: ${detail.replace('Deterministic candidates still recommending LLM review: ', '')}`;
  }
  if (detail.startsWith('Deterministic repairs carried into final output: ')) {
    return `최종 출력에 반영된 규칙 기반 복원: ${detail.replace('Deterministic repairs carried into final output: ', '')}`;
  }
  if (detail.startsWith('LLM repairs carried into final output: ')) {
    return `최종 출력에 반영된 LLM 복원: ${detail.replace('LLM repairs carried into final output: ', '')}`;
  }
  if (detail.startsWith('Repairable issues still unresolved after all enabled recovery: ')) {
    return `모든 복원 단계를 거친 뒤에도 남은 미해결 이슈: ${detail.replace('Repairable issues still unresolved after all enabled recovery: ', '')}`;
  }
  if (detail.startsWith('Unresolved repair classes: ')) {
    return `미해결 클래스 분포: ${detail.replace('Unresolved repair classes: ', '')}`;
  }
  if (detail.startsWith('Unresolved repair reasons: ')) {
    return `미해결 사유 분포: ${detail.replace('Unresolved repair reasons: ', '')}`;
  }
  return detail;
}

function humanizePreferredMarkdownKind(kind: string) {
  if (kind === 'resolved') {
    return 'final resolved';
  }
  if (kind === 'source') {
    return 'source';
  }
  return kind;
}

function humanizeCorruptionClass(value: string) {
  if (value === 'inline_formula_corruption') {
    return 'inline formula corruption';
  }
  if (value === 'table_formula_corruption') {
    return 'table formula corruption';
  }
  if (value === 'formula_placeholder') {
    return 'formula placeholder';
  }
  if (value === 'structure_loss') {
    return 'structure loss';
  }
  return value.replaceAll('_', ' ');
}

function humanizeUnresolvedReason(value: string) {
  if (value === 'llm_not_requested') {
    return 'LLM이 요청되지 않아 후속 복원이 실행되지 않음';
  }
  if (value === 'llm_no_repair_generated') {
    return 'LLM 실행 후에도 적용 가능한 복원안이 생성되지 않음';
  }
  if (value === 'llm_candidate_not_selected') {
    return 'LLM 후보가 있었지만 최종 patch로 선택되지는 않음';
  }
  if (value === 'selected_patch_not_applied') {
    return '우선순위 winner는 있었지만 source markdown에 안전하게 적용되지 않음';
  }
  if (value === 'no_patch_proposal') {
    return '적용 가능한 patch proposal이 없음';
  }
  if (value === 'deterministic_candidate_not_selected') {
    return '규칙 기반 후보가 있었지만 최종 patch로 선택되지는 않음';
  }
  return value.replaceAll('_', ' ');
}

function humanizeSelectionReason(
  value: string | null,
  selectedOrigin: string | null,
  selectedConfidence: number | null,
) {
  const confidenceText = selectedConfidence !== null ? ` (${Math.round(selectedConfidence * 100)}%)` : '';
  if (value === 'only_patch_proposal') {
    return `이 issue에서 patch proposal이 하나뿐이라 그대로 winner로 채택됨${confidenceText}`;
  }
  if (value === 'llm_priority') {
    return `LLM candidate가 deterministic base보다 높은 우선순위로 선택됨${confidenceText}`;
  }
  if (value === 'highest_confidence') {
    return `동일 selection tier 안에서 confidence가 가장 높아 선택됨${confidenceText}`;
  }
  if (value === 'best_applicable_patch') {
    return `상위 rank 후보 중 일부가 apply되지 않아, 실제로 적용 가능한 최고 순위 patch가 선택됨${confidenceText}`;
  }
  if (value === 'highest_rank') {
    return `origin 우선순위와 confidence 비교 결과 최상위 candidate로 선택됨${confidenceText}`;
  }
  if (selectedOrigin) {
    return `${selectedOrigin} candidate가 winner로 선택됨${confidenceText}`;
  }
  return '최종 winner로 선택됨';
}

function humanizeCandidateRejectionReason(value: string | null) {
  if (value === 'no_patch_proposal') {
    return '적용 가능한 patch proposal이 없어 비교 대상에서 제외됨';
  }
  if (value === 'lower_priority_origin') {
    return '다른 origin이 selection policy에서 더 높은 우선순위를 가져 기각됨';
  }
  if (value === 'llm_ranked_higher') {
    return 'LLM candidate가 상위 rank를 차지해 이 후보는 기각됨';
  }
  if (value === 'lower_confidence') {
    return '같은 selection tier 안에서 confidence가 더 낮아 기각됨';
  }
  if (value === 'patch_not_applicable') {
    return 'rank는 더 높았지만 현재 markdown anchor에 안전하게 적용되지 않아 기각됨';
  }
  if (value === 'tie_not_selected') {
    return '동일 rank 후보와 경합했지만 winner로 채택되지는 않음';
  }
  if (value === 'no_issue_winner') {
    return '이 issue에서 최종 winner가 확정되지 못함';
  }
  return value ? value.replaceAll('_', ' ') : '선택되지 않음';
}

function describePreviewMode(viewMode: 'source' | 'resolved', preferredMarkdownKind: string) {
  if (viewMode === 'resolved' && preferredMarkdownKind === 'resolved') {
    return '현재 downstream에 전달될 최종 resolved 출력';
  }
  if (viewMode === 'resolved') {
    return 'resolved 후보 출력';
  }
  if (preferredMarkdownKind === 'resolved') {
    return '원본 기준 출력, 실제 downstream 기준은 resolved';
  }
  return '원본 기준 출력';
}

function humanizeDownstreamRationale(detail: string) {
  if (detail === 'A resolved markdown artifact was assembled from the highest-ranked repair patches.') {
    return '가장 우선순위가 높은 복원 패치를 반영해 resolved markdown이 조립되었습니다.';
  }
  if (detail === 'Downstream should prefer the resolved markdown while preserving the source markdown for audit and fallback.') {
    return 'downstream에는 resolved markdown을 우선 사용하고, source markdown은 audit과 fallback 용으로 함께 보존합니다.';
  }
  if (detail === 'Validation reported repairable corruption, but no resolved markdown artifact could be assembled.') {
    return '복원 가능한 이슈는 있었지만 최종 resolved markdown을 만들 수는 없었습니다.';
  }
  if (detail === 'Downstream should keep the source markdown as canonical input until more recovery is possible.') {
    return '추가 복원이 가능해질 때까지 downstream 기준 본문은 source markdown으로 유지해야 합니다.';
  }
  if (detail === 'No blocking repair proposals exist, so downstream should use the source-faithful markdown.') {
    return '막는 수준의 복원 이슈가 없어서 source markdown을 그대로 downstream에 사용하면 됩니다.';
  }
  if (detail.startsWith('Some repairable issues remain unresolved after enabled recovery steps: ')) {
    return `활성화된 복원 단계를 모두 거친 뒤에도 남은 미해결 이슈: ${detail.replace('Some repairable issues remain unresolved after enabled recovery steps: ', '').replace('.', '')}`;
  }
  if (detail === 'At least one LLM-generated repair was merged into the final resolved markdown candidate.') {
    return 'LLM이 생성한 복원 결과 중 일부가 최종 resolved markdown에 반영되었습니다.';
  }
  if (detail === 'At least one LLM-generated formula reconstruction was produced, but it did not yield a complete resolved markdown artifact.') {
    return 'LLM 복원 결과는 있었지만, 그것만으로 최종 resolved markdown을 완성하지는 못했습니다.';
  }
  return detail;
}

function describeRepairPath(candidate: ParseResponse['repair_candidates'][number], result: ParseResponse | null) {
  const steps = ['detected'];
  steps.push('deterministic');
  if (candidate.origin === 'llm') {
    steps.push('llm');
  }
  const finalPatches = result?.final_resolved_patches || result?.suggested_resolved_patches || [];
  const matchedPatch = finalPatches.find((patch) => patch.replacement_text === candidate.patch_proposal?.replacement_text);
  if (matchedPatch) {
    steps.push('final resolved');
    steps.push(matchedPatchOriginLabel(matchedPatch.origin));
  }
  if (result?.downstream_handoff) {
    steps.push(result.downstream_handoff.preferred_markdown_kind === 'source' ? 'downstream source' : 'downstream resolved');
  }
  return steps;
}

function buildResolvedPatchOriginByLine(patches: RepairPatchProposal[]) {
  const map = new Map<number, 'llm' | 'deterministic' | 'mixed'>();
  for (const patch of patches) {
    if (patch.markdown_line_number === null) {
      continue;
    }
    const current = map.get(patch.markdown_line_number);
    const next = normalizePatchOrigin(patch.origin);
    if (!current) {
      map.set(patch.markdown_line_number, next);
      continue;
    }
    if (current !== next) {
      map.set(patch.markdown_line_number, 'mixed');
    }
  }
  return map;
}

function countPatchOrigins(patches: RepairPatchProposal[]) {
  let llm = 0;
  let deterministic = 0;
  for (const patch of patches) {
    if (normalizePatchOrigin(patch.origin) === 'llm') {
      llm += 1;
    } else {
      deterministic += 1;
    }
  }
  return {llm, deterministic};
}

function normalizePatchOrigin(origin: string | null | undefined): 'llm' | 'deterministic' {
  return origin === 'llm' ? 'llm' : 'deterministic';
}

function humanizePatchOriginBadge(origin: 'llm' | 'deterministic' | 'mixed') {
  if (origin === 'llm') {
    return 'llm patch';
  }
  if (origin === 'mixed') {
    return 'mixed patch';
  }
  return 'det patch';
}

function matchedPatchOriginLabel(origin: string | null | undefined) {
  return normalizePatchOrigin(origin) === 'llm' ? 'llm patched' : 'det patched';
}

function buildIssueInsights(result: ParseResponse | null) {
  if (!result) {
    return [];
  }
  const cards: Array<{
    issueId: string;
    title: string;
    location: string;
    problem: string;
    evidence: string;
    cause: string;
    action: string;
  }> = [];

  for (const issue of prioritizeIssues(result.issues)) {
    const details = getIssueDetails(issue);
    const excerpts = issue.excerpts.length > 0 ? issue.excerpts.slice(0, 2) : [null];

    for (const excerpt of excerpts) {
      const location =
        excerpt?.location_hint
        || readNestedString(issue.metadata, ['location', 'block_ref'])
        || issue.block_ref
        || '출력 검토 필요';
      const evidence = excerpt?.content || '이 이슈에는 별도 발췌문이 첨부되지 않았습니다.';
      const highlight = excerpt?.highlight_text;

      if (issue.code === 'text_corruption' && details.detectors.includes('private use glyphs')) {
        cards.push({
          issueId: `${issue.issue_id}:${location}:${highlight || 'glyph'}`,
          title: '깨진 수식 문자 감지',
          location: `위치 ${location}`,
          problem: `문서 본문에 정상 텍스트가 아닌 글리프가 섞여 있습니다${highlight ? ` (${highlight})` : ''}.`,
          evidence,
          cause: 'PDF 텍스트 레이어가 수식이나 특수기호를 폰트 전용 코드로 저장하고 있어, 파서가 사람이 읽는 문자로 복원하지 못한 경우입니다.',
          action: '이 구간은 chunk에 바로 신뢰해서 넘기지 말고, 파서 fallback 비교나 수식 전용 보정 단계를 거친 뒤 전달하는 것이 안전합니다.',
        });
        continue;
      }

      if (issue.code === 'text_corruption' && details.detectors.includes('formula placeholders')) {
        cards.push({
          issueId: `${issue.issue_id}:${location}:${highlight || 'formula'}`,
          title: '수식 자리표시자 감지',
          location: `위치 ${location}`,
          problem: '수식 영역이 실제 식으로 렌더링되지 않고 placeholder로 남았습니다.',
          evidence,
          cause: '파서는 수식 블록이 있다는 것은 알았지만, 이를 텍스트나 수식 마크업으로 변환하지 못했습니다.',
          action: '수식이 중요한 문서면 이 구간은 별도 수식 추출 경로를 두거나 후속 보정이 들어가기 전까지 degraded 상태로 유지해야 합니다.',
        });
        continue;
      }

      if (issue.code === 'table_structure') {
        cards.push({
          issueId: `${issue.issue_id}:${location}`,
          title: '표 구조 이상 감지',
          location: `위치 ${location}`,
          problem: issue.message,
          evidence,
          cause: '병합 셀이나 행 너비 불일치 때문에 표 정규화 과정에서 구조가 흔들린 것으로 보입니다.',
          action: '이 표가 중요하면 parser fallback이나 표 전용 정규화 로직으로 다시 확인하는 편이 좋습니다.',
        });
        continue;
      }

      cards.push({
        issueId: `${issue.issue_id}:${location}`,
        title: humanizeDetector(issue.code),
        location: `위치 ${location}`,
        problem: issue.message,
        evidence,
        cause: 'validator가 원문 충실도 저하 가능성을 감지했습니다.',
        action: '다운스트림 chunk 전달 전 이 이슈를 검토하세요.',
      });
    }
  }

  return cards.slice(0, 4);
}

function humanizeDetector(value: string) {
  return value.replaceAll('_', ' ');
}

function readNestedString(value: Record<string, unknown>, path: string[]) {
  let current: unknown = value;
  for (const key of path) {
    if (typeof current !== 'object' || current === null || !(key in current)) {
      return null;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === 'string' && current.length > 0 ? current : null;
}

function summarizeLlm(result: ParseResponse | null) {
  if (!result) {
    return {
      primaryLabel: 'No run yet',
      badge: 'Pending',
      tone: 'neutral' as const,
      summaryTone: 'neutral' as const,
      description: 'Run a parse to see whether LLM assist was requested and whether it actually executed.',
      details: [] as string[],
      responsePreview: [] as string[],
      subsystems: [
        {label: 'Routing', badge: 'Pending'},
        {label: 'Repair', badge: 'Pending'},
      ],
    };
  }

  const routingRecommendation = readNoteValue(result.notes, 'llm_routing_recommendation');
  const diagnostics = result.llm_diagnostics;
  const repairAttemptedIssues = diagnostics?.repair_attempted_issues ?? Number(readNoteValue(result.notes, 'llm_repair_attempted_issues') || '0');
  const repairGeneratedCandidates = diagnostics?.repair_generated_candidates ?? Number(readNoteValue(result.notes, 'llm_repair_generated_candidates') || '0');
  const repairError = diagnostics?.repair_error ?? readNoteValue(result.notes, 'llm_repair_error');
  const repairAttemptedFromSummary = result.resolution_summary?.issues.filter((item) => item.llm_attempted).length || 0;
  const effectiveRepairAttemptedIssues = Math.max(repairAttemptedIssues, repairAttemptedFromSummary);
  const effectiveRoutingRecommendation = diagnostics?.routing_recommendation || routingRecommendation;
  const baselineParser = diagnostics?.routing_baseline_parser || null;
  const selectedParser = diagnostics?.routing_selected_parser || null;
  const routingOverrideApplied = diagnostics?.routing_override_applied ?? false;
  const routingUsed = diagnostics ? diagnostics.routing_used : Boolean(routingRecommendation);
  const repairUsed = effectiveRepairAttemptedIssues > 0 || repairGeneratedCandidates > 0;
  const responsePreview = [
    ...(diagnostics?.repair_response_preview || []),
    ...(diagnostics?.formula_probe_preview || []),
  ];
  const details: string[] = [];
  if (effectiveRoutingRecommendation && baselineParser && selectedParser) {
    if (routingOverrideApplied) {
      details.push(`Routing probe accepted ${effectiveRoutingRecommendation} over baseline ${baselineParser}.`);
    } else if (effectiveRoutingRecommendation !== selectedParser) {
      details.push(`Routing probe rejected ${effectiveRoutingRecommendation} and kept baseline ${selectedParser}.`);
    } else {
      details.push(`Routing probe confirmed parser ${selectedParser}.`);
    }
  } else if (routingUsed && effectiveRoutingRecommendation) {
    details.push(`Routing LLM selected parser ${effectiveRoutingRecommendation}.`);
  }
  for (const item of diagnostics?.routing_comparison_preview || []) {
    if (item === 'baseline_retained_after_probe' || item === 'override_applied' || item === 'baseline_parser_retained') {
      continue;
    }
    if (item === 'parser_hint_forced_selection') {
      details.push('Routing comparison skipped because parser_hint forced the parser selection.');
      continue;
    }
    details.push(`Routing probe: ${item}`);
  }
  if (repairUsed) {
    details.push(`Repair LLM attempted ${effectiveRepairAttemptedIssues} issue(s).`);
    details.push(`Repair LLM generated ${repairGeneratedCandidates} candidate(s).`);
  }
  if (repairError) {
    details.push(`Repair LLM error: ${repairError}`);
  }
  if (diagnostics?.repair_response_available && !repairError) {
    details.push('Repair LLM returned a structured response.');
  }
  if (diagnostics?.formula_probe_attempted) {
    const applyAsPatch = diagnostics.formula_probe_apply_as_patch;
    const confidence = diagnostics.formula_probe_confidence;
    if (applyAsPatch === false) {
      details.push(
        `First placeholder probe was reviewed but not auto-applied${confidence != null ? ` (confidence ${confidence.toFixed(2)})` : ''}.`,
      );
    } else if (applyAsPatch === true) {
      details.push(
        `First placeholder probe returned an auto-applicable patch${confidence != null ? ` (confidence ${confidence.toFixed(2)})` : ''}.`,
      );
    } else {
      details.push('First placeholder probe ran for unresolved formula residue.');
    }
  }
  if (diagnostics?.formula_probe_error) {
    details.push(`Formula probe error: ${diagnostics.formula_probe_error}`);
  }

  if (result.llm_used) {
    const primaryLabel = routingOverrideApplied && repairUsed
      ? 'LLM used for routing and repair review'
      : routingOverrideApplied
        ? 'LLM changed parser route'
        : repairUsed
          ? 'LLM used for repair review'
          : effectiveRoutingRecommendation
            ? 'LLM advised routing but baseline was kept'
            : 'LLM executed in this run';
    return {
      primaryLabel,
      badge: 'Used',
      tone: routingOverrideApplied ? 'success' as const : 'warning' as const,
      summaryTone: routingOverrideApplied ? 'success' as const : 'warning' as const,
      description: 'The backend used an LLM-assisted step during this run. Review the detail rows below for routing or repair outputs returned by the backend.',
      details,
      responsePreview,
      subsystems: [
        {
          label: 'Routing',
          badge: effectiveRoutingRecommendation
            ? routingOverrideApplied
              ? `Applied: ${selectedParser || effectiveRoutingRecommendation}`
              : `Kept: ${selectedParser || baselineParser || 'baseline'}`
            : 'Off',
        },
        {
          label: 'Repair',
          badge: repairUsed
            ? repairGeneratedCandidates > 0
              ? `Generated ${repairGeneratedCandidates}`
              : `Attempted ${effectiveRepairAttemptedIssues}`
            : 'Off',
        },
      ],
    };
  }

  if (result.llm_requested) {
    return {
      primaryLabel: 'LLM requested but skipped',
      badge: 'Skipped',
      tone: 'warning' as const,
      summaryTone: 'warning' as const,
      description: 'LLM assist was requested, but the backend completed this run deterministically. This usually means LLM is not configured or there was no eligible LLM decision point.',
      details: details.length > 0 ? details : ['No LLM-specific note was returned by the backend.'],
      responsePreview,
      subsystems: [
        {label: 'Routing', badge: routingUsed ? `Used${effectiveRoutingRecommendation ? `: ${effectiveRoutingRecommendation}` : ''}` : 'Skipped'},
        {label: 'Repair', badge: repairUsed ? `Attempted ${effectiveRepairAttemptedIssues}` : 'Skipped'},
      ],
    };
  }

  return {
    primaryLabel: 'Deterministic path only',
    badge: 'Off',
    tone: 'neutral' as const,
    summaryTone: 'neutral' as const,
    description: 'This run did not request LLM assist and stayed on the deterministic execution path.',
    details,
    responsePreview,
    subsystems: [
      {label: 'Routing', badge: 'Off'},
      {label: 'Repair', badge: 'Off'},
    ],
  };
}

function readNoteValue(notes: string[], key: string) {
  const prefix = `${key}=`;
  const note = notes.find((item) => item.startsWith(prefix));
  return note ? note.slice(prefix.length) : null;
}

function humanizeLlmResponsePreview(value: string) {
  if (value.startsWith('repairs=')) {
    return `LLM raw response repair count: ${value.replace('repairs=', '')}`;
  }
  if (value === 'response_present_but_no_repairs') {
    return 'LLM 응답은 있었지만 repairs 배열은 비어 있었습니다.';
  }
  if (value.startsWith('matched_page=')) {
    return `First placeholder matched page: ${value.replace('matched_page=', '')}`;
  }
  if (value.startsWith('region_bbox=')) {
    return `First placeholder crop bbox: ${value.replace('region_bbox=', '')}`;
  }
  if (value.startsWith('apply_as_patch=')) {
    return value === 'apply_as_patch=true'
      ? 'First placeholder probe judged the patch safe to apply.'
      : 'First placeholder probe judged the patch unsafe to auto-apply.';
  }
  if (value.startsWith('confidence=')) {
    return `First placeholder probe confidence: ${value.replace('confidence=', '')}`;
  }
  if (value.startsWith('reason=')) {
    return `First placeholder probe rationale: ${value.replace('reason=', '')}`;
  }
  if (value.startsWith('replacement=')) {
    return `First placeholder probe replacement preview: ${value.replace('replacement=', '')}`;
  }
  if (value.startsWith('raw=')) {
    return `First placeholder raw response preview: ${value.replace('raw=', '')}`;
  }
  return value;
}

function summarizeRecoveryFlow(result: ParseResponse | null) {
  if (!result?.resolution_summary) {
    return null;
  }

  const summary = result.resolution_summary;
  const deterministicRecovered = summary.recovered_deterministic_count;
  const llmRecovered = summary.recovered_llm_count;
  const unresolved = summary.unresolved_repair_issue_count;
  const llmAttempted = summary.issues.filter((item) => item.llm_attempted).length;
  const resolved = summary.resolved_issue_count;
  const repairIssues = summary.repair_issue_count;

  let title = 'Recovery completed with deterministic path';
  let badge = 'Deterministic';
  let tone: 'success' | 'warning' | 'neutral' = 'neutral';
  if (llmRecovered > 0 || llmAttempted > 0) {
    title = unresolved > 0 ? 'Recovery completed with mixed results' : 'Recovery completed with deterministic + LLM repair';
    badge = unresolved > 0 ? 'Mixed' : 'Recovered';
    tone = unresolved > 0 ? 'warning' : 'success';
  } else if (resolved > 0 && unresolved === 0) {
    title = 'Recovery completed with deterministic path';
    badge = 'Resolved';
    tone = 'success';
  } else if (unresolved > 0) {
    title = 'Recovery still has unresolved issues';
    badge = 'Review';
    tone = 'warning';
  }

  const unresolvedByReason = Object.entries(summary.unresolved_by_reason)
    .sort((left, right) => right[1] - left[1])
    .map(([key, value]) => `${humanizeUnresolvedReason(key)} ${value}`);
  const unresolvedByClass = Object.entries(summary.unresolved_by_class)
    .sort((left, right) => right[1] - left[1])
    .map(([key, value]) => `${humanizeCorruptionClass(key)} ${value}`);

  const details = [
    `detected ${repairIssues} repairable issue${repairIssues === 1 ? '' : 's'}`,
    `deterministic recovered ${deterministicRecovered}`,
    `LLM attempted ${llmAttempted}`,
    `LLM recovered ${llmRecovered}`,
    `unresolved ${unresolved}`,
  ];
  if (unresolvedByReason.length > 0) {
    details.push(`미해결 사유: ${unresolvedByReason.join(', ')}`);
  }
  if (unresolvedByClass.length > 0) {
    details.push(`미해결 클래스: ${unresolvedByClass.join(', ')}`);
  }

  return {
    title,
    badge,
    tone,
    metrics: [
      {label: 'Detected', value: repairIssues},
      {label: 'Deterministic', value: deterministicRecovered},
      {label: 'LLM attempted', value: llmAttempted},
      {label: 'LLM recovered', value: llmRecovered},
      {label: 'Resolved', value: resolved},
      {label: 'Unresolved', value: unresolved},
    ],
    details,
  };
}

function getCurrentStage(status: AsyncStatus, result: ParseResponse | null): string {
  if (status === 'loading') {
    return 'running';
  }
  if (!result?.trace.events.length) {
    return 'idle';
  }
  return result.trace.events[result.trace.events.length - 1]?.stage || 'idle';
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});
}

function formatBytes(value: number | null) {
  if (!value || value <= 0) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function asErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unknown error';
}
