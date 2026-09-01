import { useEffect, useMemo, useState, type ReactNode } from "react";
import { BarChart3, FlaskConical, GitBranch, Plus, Save, ShieldAlert, Workflow } from "lucide-react";
import { api } from "../api";
import type { ExperimentCondition, ExperimentStudy, ExperimentStudyDetail, ExperimentTrial, MetricTemplate, Project, RobotProfile } from "../types";
import { ui } from "../i18n";
import { friendlyError } from "../utils";

const STATUS = ["Planning", "Running", "Completed", "Failed", "Archived"];
const HYPOTHESIS = ["Supported", "Partially Supported", "Rejected", "Inconclusive"];
const CONDITION_TYPES = ["Baseline", "Proposed", "Ablation", "Generalization"];
const COMPONENTS = ["LLM Planning", "Behavior Tree Validation", "Execution Feedback", "Failure Detection", "Replanning", "Memory", "Visual Re-grounding"];
const FAILURE_LAYERS = ["Perception", "Grounding", "Task Planning", "Action Selection", "Motion Planning", "IK", "Grasp", "Execution", "Alignment", "Insertion", "Verification", "Recovery", "LLM Hallucination", "Invalid Action", "Timeout", "Hardware", "Unknown"];
const TRACE_TYPES = ["instruction", "planner_output", "action", "execution_result", "feedback", "replan", "recovery", "verification"];
const ARTIFACT_TYPES = ["video", "image", "screenshot", "plot", "log", "rosbag", "TensorBoard"];
const GENERALIZATION = ["New Object", "New Arrangement", "New Instruction", "New Task Length", "New Scene", "New Robot"];

type ExperimentsText = typeof ui.zh.experiments;

type Props = {
  t: ExperimentsText;
  projects: Project[];
  refresh: () => Promise<void>;
};

export function Experiments({ t, projects, refresh }: Props) {
  const [studies, setStudies] = useState<ExperimentStudy[]>([]);
  const [detail, setDetail] = useState<ExperimentStudyDetail | null>(null);
  const [robots, setRobots] = useState<RobotProfile[]>([]);
  const [metricTemplates, setMetricTemplates] = useState<MetricTemplate[]>([]);
  const [tab, setTab] = useState("overview");
  const [message, setMessage] = useState("");
  const [studyForm, setStudyForm] = useState({ study_code: "EXP-STUDY-001", name: t.defaultStudyName, project_id: "", environment: "Simulation" });
  const [robotForm, setRobotForm] = useState({ name: t.defaultRobotName, robot_type: "Manipulator", arms: "", sensors: "", compute: "", ros_version: "ROS2 Humble", moveit_version: "", notes: "" });
  const [conditionForm, setConditionForm] = useState({ name: t.baselineName, condition_type: "Baseline", description: "", enabled_components: COMPONENTS.slice(0, 2).join("\n"), disabled_components: "", config_path: "", prompt_version: "", prompt_path: "", model_name: "", llm: "", retry_policy: "max_retry=3", timeout_seconds: "120", generalization_dimension: "", seen_unseen: "Seen" });
  const [trialForm, setTrialForm] = useState({ condition_id: "", trial_id: "T-001", scene: "assembly_scene_01", seed: "42", duration_seconds: "", result: "Success", steps: "", plan_length: "", replan_count: "0", human_intervention: false, failure_layer: "", failure_category: "", note: "" });
  const [traceForm, setTraceForm] = useState({ trial_id: "", event_type: "instruction", title: "", content: "", order_index: "0" });
  const [metricForm, setMetricForm] = useState({ condition_id: "", metric_key: "task_success_rate", mean: "", std: "", count: "", p_value: "", effect_size: "", confidence_interval: "", statistical_test: "", is_primary: true });
  const [artifactForm, setArtifactForm] = useState({ study_id: "", condition_id: "", trial_id: "", artifact_type: "video", path: "", description: "" });

  async function load(selectedId?: number) {
    const [studyRows, robotRows, templates] = await Promise.all([api.experimentStudies(), api.robotProfiles(), api.experimentMetricTemplates()]);
    setStudies(studyRows);
    setRobots(robotRows);
    setMetricTemplates(templates.templates);
    const id = selectedId ?? detail?.study.id ?? studyRows[0]?.id;
    if (id) {
      const next = await api.experimentStudyDetail(id);
      setDetail(next);
      setArtifactForm((current) => ({ ...current, study_id: String(id) }));
    }
  }

  useEffect(() => {
    void load().catch((error) => setMessage(friendlyError(error)));
  }, []);

  const trialsByCondition = useMemo(() => {
    const grouped: Record<number, ExperimentTrial[]> = {};
    detail?.trials.forEach((trial) => {
      grouped[trial.condition_id] = [...(grouped[trial.condition_id] ?? []), trial];
    });
    return grouped;
  }, [detail]);

  const selectedTrial = detail?.trials.find((trial) => trial.id === Number(traceForm.trial_id));
  const selectedCondition = detail?.conditions.find((condition) => condition.id === Number(trialForm.condition_id));

  async function createStudy() {
    setMessage("");
    try {
      const payload = {
      ...studyForm,
      project_id: studyForm.project_id ? Number(studyForm.project_id) : null,
      task_type: "Robot Task Planning",
      status: "Planning",
      current_stage: "Task & Benchmark Design",
      conclusion_status: "Inconclusive",
      hypothesis_status: "Inconclusive",
    };
      const created = await api.createExperimentStudy(payload);
      setDetail(created);
      await load(created.study.id);
      await refresh();
      setMessage(t.studyCreated);
    } catch (error) {
      setMessage(friendlyError(error));
    }
  }

  async function createRobotProfile() {
    await api.createRobotProfile(robotForm);
    await load(detail?.study.id);
  }

  async function saveStudy(payload: Partial<ExperimentStudy>) {
    if (!detail) return;
    const saved = await api.updateExperimentStudy(detail.study.id, payload);
    setDetail(saved);
    await load(saved.study.id);
  }

  async function saveTaskProfile() {
    if (!detail) return;
    const form = detail.task_profile ?? {};
    const saved = await api.updateTaskProfile(detail.study.id, form);
    setDetail(saved);
  }

  async function saveProtocol() {
    if (!detail) return;
    const form = detail.protocol ?? {};
    const saved = await api.updateExperimentProtocol(detail.study.id, form);
    setDetail(saved);
  }

  async function createCondition() {
    if (!detail) return;
    const saved = await api.createExperimentCondition({
      ...conditionForm,
      study_id: detail.study.id,
      project_id: detail.study.project_id ?? null,
      timeout_seconds: numberOrNull(conditionForm.timeout_seconds),
    });
    setDetail(saved);
    await load(saved.study.id);
  }

  async function createTrial() {
    const saved = await api.createExperimentTrial({
      ...trialForm,
      condition_id: Number(trialForm.condition_id),
      seed: numberOrNull(trialForm.seed),
      duration_seconds: numberOrNull(trialForm.duration_seconds),
      steps: numberOrNull(trialForm.steps),
      plan_length: numberOrNull(trialForm.plan_length),
      replan_count: numberOrNull(trialForm.replan_count),
    });
    setDetail(saved);
    setTraceForm((current) => ({ ...current, trial_id: String(saved.trials[saved.trials.length - 1]?.id ?? "") }));
  }

  async function createTrace() {
    const saved = await api.createPlanningTraceEvent({ ...traceForm, trial_id: Number(traceForm.trial_id), order_index: Number(traceForm.order_index || 0) });
    setDetail(saved);
  }

  async function createMetric() {
    if (!detail) return;
    const saved = await api.createMetricValue({
      study_id: detail.study.id,
      condition_id: metricForm.condition_id ? Number(metricForm.condition_id) : null,
      metric_key: metricForm.metric_key,
      mean: numberOrNull(metricForm.mean),
      std: numberOrNull(metricForm.std),
      count: numberOrNull(metricForm.count),
      p_value: numberOrNull(metricForm.p_value),
      effect_size: metricForm.effect_size,
      confidence_interval: metricForm.confidence_interval,
      statistical_test: metricForm.statistical_test,
      is_primary: metricForm.is_primary,
    });
    setDetail(saved);
  }

  async function createArtifact() {
    if (!detail) return;
    const saved = await api.createArtifactReference({
      study_id: artifactForm.study_id ? Number(artifactForm.study_id) : detail.study.id,
      condition_id: artifactForm.condition_id ? Number(artifactForm.condition_id) : null,
      trial_id: artifactForm.trial_id ? Number(artifactForm.trial_id) : null,
      artifact_type: artifactForm.artifact_type,
      path: artifactForm.path,
      description: artifactForm.description,
    });
    setDetail(saved);
  }

  function updateTaskProfile(key: string, value: any) {
    if (!detail) return;
    setDetail({ ...detail, task_profile: { ...(detail.task_profile ?? {}), [key]: value } });
  }

  function updateProtocol(key: string, value: any) {
    if (!detail) return;
    setDetail({ ...detail, protocol: { ...(detail.protocol ?? {}), [key]: value } });
  }

  return (
    <section className="experiment-workbench">
      <div className="panel experiment-sidebar">
        <div className="panel-heading"><h2>{t.newStudy}</h2></div>
        <div className="form-grid">
          <label><span>{t.studyCode}</span><input value={studyForm.study_code} onChange={(event) => setStudyForm({ ...studyForm, study_code: event.target.value })} /></label>
          <label><span>{t.studyName}</span><input value={studyForm.name} onChange={(event) => setStudyForm({ ...studyForm, name: event.target.value })} /></label>
          <label><span>{t.project}</span><select value={studyForm.project_id} onChange={(event) => setStudyForm({ ...studyForm, project_id: event.target.value })}><option value="">{t.noProject}</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
          <label><span>{t.environment}</span><select value={studyForm.environment} onChange={(event) => setStudyForm({ ...studyForm, environment: event.target.value })}><option>Simulation</option><option>Real Robot</option><option>Hybrid</option></select></label>
          <button className="primary" onClick={() => void createStudy()}><Plus size={16} />{t.createStudy}</button>
          {message && <p className="notice">{message}</p>}
        </div>

        <h3>{t.studyList}</h3>
        <div className="experiment-list">
          {studies.map((study) => <button key={study.id} className={`list-item ${detail?.study.id === study.id ? "selected" : ""}`} onClick={() => void load(study.id)}><strong>{study.study_code}</strong><span>{study.name}</span><span>{label(t.statusLabels, study.status)} · {study.trials_count ?? 0} {t.trials}</span></button>)}
          {!studies.length && <p className="muted">{t.noStudies}</p>}
        </div>
      </div>

      <div className="panel experiment-main">
        {!detail ? <p className="muted">{message || t.noStudies}</p> : <>
          <div className="experiment-hero">
            <div><span className="muted">{detail.study.study_code}</span><h2>{detail.study.name}</h2><p>{detail.study.claim || t.noClaim}</p></div>
            <div className="metric-row experiment-kpis"><Metric label={t.conditions} value={detail.conditions.length} /><Metric label={t.trials} value={detail.trials.length} /><Metric label={t.hypothesisStatus} value={label(t.hypothesisLabels, detail.study.hypothesis_status)} /><Metric label={t.primaryMetric} value={detail.study.primary_metric || "-"} /></div>
          </div>
          <div className="tabs">{["overview", "task", "methods", "protocol", "runs", "results", "failures", "ablation", "media", "analysis"].map((key) => <button key={key} className={tab === key ? "active-pill" : ""} onClick={() => setTab(key)}>{label(t.tabs, key)}</button>)}</div>

          {tab === "overview" && <div className="experiment-section-grid">
            <Section title={t.overview} icon={<FlaskConical size={16} />}>
              <div className="form-grid two-col">
                <label><span>{t.status}</span><select value={detail.study.status} onChange={(event) => void saveStudy({ status: event.target.value })}>{STATUS.map((item) => <option key={item}>{item}</option>)}</select></label>
                <label><span>{t.currentStage}</span><input value={detail.study.current_stage ?? ""} onChange={(event) => setDetail({ ...detail, study: { ...detail.study, current_stage: event.target.value } })} onBlur={(event) => void saveStudy({ current_stage: event.target.value })} /></label>
                <label><span>{t.robotProfile}</span><select value={detail.study.robot_profile_id ?? ""} onChange={(event) => void saveStudy({ robot_profile_id: event.target.value ? Number(event.target.value) : null })}><option value="">{t.noRobot}</option>{robots.map((robot) => <option key={robot.id} value={robot.id}>{robot.name}</option>)}</select></label>
                <label><span>{t.hypothesisStatus}</span><select value={detail.study.hypothesis_status} onChange={(event) => void saveStudy({ hypothesis_status: event.target.value, conclusion_status: event.target.value })}>{HYPOTHESIS.map((item) => <option key={item}>{item}</option>)}</select></label>
              </div>
              <EditableText t={t} label={t.researchQuestion} value={detail.study.research_question} onChange={(value) => setDetail({ ...detail, study: { ...detail.study, research_question: value } })} onSave={() => void saveStudy({ research_question: detail.study.research_question })} />
              <EditableText t={t} label={t.hypothesis} value={detail.study.hypothesis} onChange={(value) => setDetail({ ...detail, study: { ...detail.study, hypothesis: value } })} onSave={() => void saveStudy({ hypothesis: detail.study.hypothesis })} />
              <EditableText t={t} label={t.claim} value={detail.study.claim} onChange={(value) => setDetail({ ...detail, study: { ...detail.study, claim: value } })} onSave={() => void saveStudy({ claim: detail.study.claim })} />
            </Section>
            <Section title={t.robotProfiles} icon={<Workflow size={16} />}>
              <div className="form-grid two-col">{(["name", "robot_type", "arms", "sensors", "compute", "ros_version", "moveit_version"] as const).map((key) => <label key={key}><span>{label(t.robotFields, key)}</span><input value={robotForm[key]} onChange={(event) => setRobotForm({ ...robotForm, [key]: event.target.value })} /></label>)}</div>
              <button onClick={() => void createRobotProfile()}><Plus size={16} />{t.createRobot}</button>
            </Section>
          </div>}

          {tab === "task" && detail.task_profile && <Section title={t.taskSetup} icon={<Workflow size={16} />}>
            <div className="form-grid two-col">
              <label><span>{t.taskName}</span><input value={detail.task_profile.task_name ?? ""} onChange={(event) => updateTaskProfile("task_name", event.target.value)} /></label>
              <label><span>{t.taskComplexity}</span><select value={detail.task_profile.task_complexity ?? ""} onChange={(event) => updateTaskProfile("task_complexity", event.target.value)}><option value="">-</option><option>Short Horizon</option><option>Medium Horizon</option><option>Long Horizon</option></select></label>
              <label><span>{t.sceneComplexity}</span><input value={detail.task_profile.scene_complexity ?? ""} onChange={(event) => updateTaskProfile("scene_complexity", event.target.value)} /></label>
              <label><span>{t.objectCount}</span><input type="number" value={detail.task_profile.object_count ?? ""} onChange={(event) => updateTaskProfile("object_count", numberOrNull(event.target.value))} /></label>
              <label><span>{t.perceptionUncertainty}</span><select value={detail.task_profile.perception_uncertainty ?? ""} onChange={(event) => updateTaskProfile("perception_uncertainty", event.target.value)}><option value="">-</option><option>Low</option><option>Medium</option><option>High</option></select></label>
              <label><span>{t.executionUncertainty}</span><select value={detail.task_profile.execution_uncertainty ?? ""} onChange={(event) => updateTaskProfile("execution_uncertainty", event.target.value)}><option value="">-</option><option>Low</option><option>Medium</option><option>High</option></select></label>
              <label><span>{t.positionThreshold}</span><input value={detail.task_profile.position_error_threshold ?? ""} onChange={(event) => updateTaskProfile("position_error_threshold", event.target.value)} /></label>
              <label><span>{t.orientationThreshold}</span><input value={detail.task_profile.orientation_error_threshold ?? ""} onChange={(event) => updateTaskProfile("orientation_error_threshold", event.target.value)} /></label>
            </div>
            <div className="form-grid two-col text-fields">
              <label><span>{t.instruction}</span><textarea value={detail.task_profile.instruction ?? ""} onChange={(event) => updateTaskProfile("instruction", event.target.value)} /></label>
              <label><span>{t.taskSteps}</span><textarea value={detail.task_profile.task_steps ?? ""} onChange={(event) => updateTaskProfile("task_steps", event.target.value)} /></label>
              <label><span>{t.initialState}</span><textarea value={detail.task_profile.initial_state ?? ""} onChange={(event) => updateTaskProfile("initial_state", event.target.value)} /></label>
              <label><span>{t.goalState}</span><textarea value={detail.task_profile.goal_state ?? ""} onChange={(event) => updateTaskProfile("goal_state", event.target.value)} /></label>
              <label><span>{t.constraints}</span><textarea value={detail.task_profile.constraints ?? ""} onChange={(event) => updateTaskProfile("constraints", event.target.value)} /></label>
              <label><span>{t.successCriteria}</span><textarea value={detail.task_profile.success_criteria ?? ""} onChange={(event) => updateTaskProfile("success_criteria", event.target.value)} /></label>
            </div>
            <div className="toolbar"><label className="select-row"><input type="checkbox" checked={detail.task_profile.no_collision_required ?? true} onChange={(event) => updateTaskProfile("no_collision_required", event.target.checked)} />{t.noCollision}</label><label className="select-row"><input type="checkbox" checked={detail.task_profile.timeout_required ?? true} onChange={(event) => updateTaskProfile("timeout_required", event.target.checked)} />{t.timeoutRequired}</label><label className="select-row"><input type="checkbox" checked={detail.task_profile.human_intervention_allowed ?? false} onChange={(event) => updateTaskProfile("human_intervention_allowed", event.target.checked)} />{t.humanInterventionAllowed}</label></div>
            <button className="primary" onClick={() => void saveTaskProfile()}><Save size={16} />{t.save}</button>
          </Section>}

          {tab === "methods" && <Section title={t.methods} icon={<GitBranch size={16} />}>
            <div className="form-grid two-col">
              <label><span>{t.conditionName}</span><input value={conditionForm.name} onChange={(event) => setConditionForm({ ...conditionForm, name: event.target.value })} /></label>
              <label><span>{t.conditionType}</span><select value={conditionForm.condition_type} onChange={(event) => setConditionForm({ ...conditionForm, condition_type: event.target.value })}>{CONDITION_TYPES.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label><span>{t.configPath}</span><input value={conditionForm.config_path} onChange={(event) => setConditionForm({ ...conditionForm, config_path: event.target.value })} /></label>
              <label><span>{t.promptVersion}</span><input value={conditionForm.prompt_version} onChange={(event) => setConditionForm({ ...conditionForm, prompt_version: event.target.value })} /></label>
              <label><span>{t.promptPath}</span><input value={conditionForm.prompt_path} onChange={(event) => setConditionForm({ ...conditionForm, prompt_path: event.target.value })} /></label>
              <label><span>{t.modelLlm}</span><input value={conditionForm.llm} onChange={(event) => setConditionForm({ ...conditionForm, llm: event.target.value })} /></label>
              <label><span>{t.generalization}</span><select value={conditionForm.generalization_dimension} onChange={(event) => setConditionForm({ ...conditionForm, generalization_dimension: event.target.value })}><option value="">-</option>{GENERALIZATION.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label><span>{t.seenUnseen}</span><select value={conditionForm.seen_unseen} onChange={(event) => setConditionForm({ ...conditionForm, seen_unseen: event.target.value })}><option>Seen</option><option>Unseen</option></select></label>
              <label><span>{t.enabledComponents}</span><textarea value={conditionForm.enabled_components} onChange={(event) => setConditionForm({ ...conditionForm, enabled_components: event.target.value })} /></label>
              <label><span>{t.disabledComponents}</span><textarea value={conditionForm.disabled_components} onChange={(event) => setConditionForm({ ...conditionForm, disabled_components: event.target.value })} /></label>
            </div>
            <button className="primary" onClick={() => void createCondition()}><Plus size={16} />{t.createCondition}</button>
            <div className="condition-grid">{detail.conditions.map((condition) => <div className="paper-card" key={condition.id}><strong>{condition.name}</strong><span>{label(t.conditionLabels, condition.condition_type)} · {condition.trials_count ?? 0} {t.trials}</span>{condition.git_dirty && <span className="notice"><ShieldAlert size={14} /> {t.gitDirty}</span>}<code>{condition.git_commit_hash || t.noCommit}</code><span>{t.components}: {condition.enabled_components || "-"}</span></div>)}</div>
          </Section>}

          {tab === "protocol" && detail.protocol && <Section title={t.protocol} icon={<ShieldAlert size={16} />}>
            <div className="form-grid two-col">
              <label><span>{t.trialsPerCondition}</span><input type="number" value={detail.protocol.trials_per_condition ?? ""} onChange={(event) => updateProtocol("trials_per_condition", numberOrNull(event.target.value))} /></label>
              <label><span>{t.randomSeeds}</span><input value={detail.protocol.random_seeds ?? ""} onChange={(event) => updateProtocol("random_seeds", event.target.value)} /></label>
              <label><span>{t.seedStrategy}</span><input value={detail.protocol.seed_strategy ?? ""} onChange={(event) => updateProtocol("seed_strategy", event.target.value)} /></label>
              <label><span>{t.timeoutSeconds}</span><input type="number" value={detail.protocol.timeout_seconds ?? ""} onChange={(event) => updateProtocol("timeout_seconds", numberOrNull(event.target.value))} /></label>
              <label><span>{t.maxRetries}</span><input type="number" value={detail.protocol.max_retries ?? ""} onChange={(event) => updateProtocol("max_retries", numberOrNull(event.target.value))} /></label>
              <label><span>{t.sceneCount}</span><input type="number" value={detail.protocol.scene_count ?? ""} onChange={(event) => updateProtocol("scene_count", numberOrNull(event.target.value))} /></label>
              <label><span>{t.taskRepetitions}</span><input type="number" value={detail.protocol.task_repetitions ?? ""} onChange={(event) => updateProtocol("task_repetitions", numberOrNull(event.target.value))} /></label>
              <label className="select-row"><input type="checkbox" checked={detail.protocol.human_intervention_allowed ?? false} onChange={(event) => updateProtocol("human_intervention_allowed", event.target.checked)} />{t.humanInterventionAllowed}</label>
              <label><span>{t.resetPolicy}</span><textarea value={detail.protocol.reset_policy ?? ""} onChange={(event) => updateProtocol("reset_policy", event.target.value)} /></label>
              <label><span>{t.objectResetPolicy}</span><textarea value={detail.protocol.object_reset_policy ?? ""} onChange={(event) => updateProtocol("object_reset_policy", event.target.value)} /></label>
            </div>
            <button className="primary" onClick={() => void saveProtocol()}><Save size={16} />{t.save}</button>
          </Section>}

          {tab === "runs" && <Section title={t.runsTrials} icon={<Workflow size={16} />}>
            <div className="form-grid two-col">
              <label><span>{t.condition}</span><select value={trialForm.condition_id} onChange={(event) => setTrialForm({ ...trialForm, condition_id: event.target.value })}><option value="">{t.chooseCondition}</option>{detail.conditions.map((condition) => <option key={condition.id} value={condition.id}>{condition.name}</option>)}</select></label>
              <label><span>{t.trialId}</span><input value={trialForm.trial_id} onChange={(event) => setTrialForm({ ...trialForm, trial_id: event.target.value })} /></label>
              <label><span>{t.scene}</span><input value={trialForm.scene} onChange={(event) => setTrialForm({ ...trialForm, scene: event.target.value })} /></label>
              <label><span>{t.seed}</span><input type="number" value={trialForm.seed} onChange={(event) => setTrialForm({ ...trialForm, seed: event.target.value })} /></label>
              <label><span>{t.result}</span><select value={trialForm.result} onChange={(event) => setTrialForm({ ...trialForm, result: event.target.value })}><option>Success</option><option>Failed</option><option>Aborted</option></select></label>
              <label><span>{t.duration}</span><input type="number" value={trialForm.duration_seconds} onChange={(event) => setTrialForm({ ...trialForm, duration_seconds: event.target.value })} /></label>
              <label><span>{t.planLength}</span><input type="number" value={trialForm.plan_length} onChange={(event) => setTrialForm({ ...trialForm, plan_length: event.target.value })} /></label>
              <label><span>{t.replanCount}</span><input type="number" value={trialForm.replan_count} onChange={(event) => setTrialForm({ ...trialForm, replan_count: event.target.value })} /></label>
              <label><span>{t.failureLayer}</span><select value={trialForm.failure_layer} onChange={(event) => setTrialForm({ ...trialForm, failure_layer: event.target.value })}><option value="">-</option>{FAILURE_LAYERS.map((item) => <option key={item}>{item}</option>)}</select></label>
              <label className="select-row"><input type="checkbox" checked={trialForm.human_intervention} onChange={(event) => setTrialForm({ ...trialForm, human_intervention: event.target.checked })} />{t.humanIntervention}</label>
              <label className="full-field"><span>{t.note}</span><textarea value={trialForm.note} onChange={(event) => setTrialForm({ ...trialForm, note: event.target.value })} /></label>
            </div>
            <button className="primary" disabled={!trialForm.condition_id} onClick={() => void createTrial()}><Plus size={16} />{t.addTrial}</button>
            <TrialTable t={t} detail={detail} trialsByCondition={trialsByCondition} />
            <div className="trace-editor">
              <h3>{t.planningTrace}</h3>
              <div className="form-grid two-col"><label><span>{t.trial}</span><select value={traceForm.trial_id} onChange={(event) => setTraceForm({ ...traceForm, trial_id: event.target.value })}><option value="">{t.chooseTrial}</option>{detail.trials.map((trial) => <option key={trial.id} value={trial.id}>{trial.trial_id}</option>)}</select></label><label><span>{t.traceType}</span><select value={traceForm.event_type} onChange={(event) => setTraceForm({ ...traceForm, event_type: event.target.value })}>{TRACE_TYPES.map((item) => <option key={item}>{item}</option>)}</select></label><label><span>{t.traceTitle}</span><input value={traceForm.title} onChange={(event) => setTraceForm({ ...traceForm, title: event.target.value })} /></label><label><span>{t.traceOrder}</span><input type="number" value={traceForm.order_index} onChange={(event) => setTraceForm({ ...traceForm, order_index: event.target.value })} /></label><label className="full-field"><span>{t.traceContent}</span><textarea value={traceForm.content} onChange={(event) => setTraceForm({ ...traceForm, content: event.target.value })} /></label></div>
              <button disabled={!traceForm.trial_id} onClick={() => void createTrace()}><Plus size={16} />{t.addTrace}</button>
              {selectedTrial && <TraceList t={t} events={detail.trace_events.filter((event) => event.trial_id === selectedTrial.id)} />}
            </div>
          </Section>}

          {tab === "results" && <Section title={t.results} icon={<BarChart3 size={16} />}>
            <div className="form-grid two-col"><label><span>{t.condition}</span><select value={metricForm.condition_id} onChange={(event) => setMetricForm({ ...metricForm, condition_id: event.target.value })}><option value="">{t.studyLevel}</option>{detail.conditions.map((condition) => <option key={condition.id} value={condition.id}>{condition.name}</option>)}</select></label><label><span>{t.metric}</span><select value={metricForm.metric_key} onChange={(event) => setMetricForm({ ...metricForm, metric_key: event.target.value })}>{metricTemplates.map((metric) => <option key={metric.key} value={metric.key}>{metric.name_zh || metric.name}</option>)}</select></label><label><span>{t.mean}</span><input type="number" value={metricForm.mean} onChange={(event) => setMetricForm({ ...metricForm, mean: event.target.value })} /></label><label><span>{t.std}</span><input type="number" value={metricForm.std} onChange={(event) => setMetricForm({ ...metricForm, std: event.target.value })} /></label><label><span>{t.count}</span><input type="number" value={metricForm.count} onChange={(event) => setMetricForm({ ...metricForm, count: event.target.value })} /></label><label><span>{t.pValue}</span><input type="number" value={metricForm.p_value} onChange={(event) => setMetricForm({ ...metricForm, p_value: event.target.value })} /></label><label><span>{t.effectSize}</span><input value={metricForm.effect_size} onChange={(event) => setMetricForm({ ...metricForm, effect_size: event.target.value })} /></label><label><span>{t.confidenceInterval}</span><input value={metricForm.confidence_interval} onChange={(event) => setMetricForm({ ...metricForm, confidence_interval: event.target.value })} /></label><label><span>{t.statisticalTest}</span><input value={metricForm.statistical_test} onChange={(event) => setMetricForm({ ...metricForm, statistical_test: event.target.value })} /></label><label className="select-row"><input type="checkbox" checked={metricForm.is_primary} onChange={(event) => setMetricForm({ ...metricForm, is_primary: event.target.checked })} />{t.primaryMetric}</label></div>
            <button className="primary" onClick={() => void createMetric()}><Plus size={16} />{t.addMetric}</button>
            <div className="condition-grid">{detail.metrics.map((metric) => <div className="paper-card" key={metric.id}><strong>{metricLabel(metricTemplates, metric.metric_key)}</strong><span>{t.mean}: {metric.mean ?? metric.value ?? "-"} · {t.std}: {metric.std ?? "-"} · n={metric.count ?? "-"}</span><span>{t.statistics}: {metric.statistical_test || "-"} p={metric.p_value ?? "-"} {metric.confidence_interval || ""}</span></div>)}</div>
          </Section>}

          {tab === "failures" && <Section title={t.failureAnalysis} icon={<ShieldAlert size={16} />}><div className="condition-grid">{Object.entries(detail.failure_summary).map(([key, value]) => <div className="metric" key={key}><span>{key}</span><strong>{value}</strong></div>)}{!Object.keys(detail.failure_summary).length && <p className="muted">{t.noFailures}</p>}</div><TrialTable t={t} detail={detail} trialsByCondition={trialsByCondition} onlyFailures /></Section>}

          {tab === "ablation" && <Section title={t.ablationGeneralization} icon={<BarChart3 size={16} />}><div className="condition-grid">{detail.conditions.map((condition) => <div className="paper-card" key={condition.id}><strong>{condition.name}</strong><span>{label(t.conditionLabels, condition.condition_type)}</span><span>{t.enabledComponents}: {condition.enabled_components || "-"}</span><span>{t.generalization}: {condition.generalization_dimension || "-"} · {condition.seen_unseen || "-"}</span><span>{t.successRate}: {condition.success_rate ?? "-"}%</span></div>)}</div></Section>}

          {tab === "media" && <Section title={t.mediaArtifacts} icon={<Workflow size={16} />}><div className="form-grid two-col"><label><span>{t.artifactType}</span><select value={artifactForm.artifact_type} onChange={(event) => setArtifactForm({ ...artifactForm, artifact_type: event.target.value })}>{ARTIFACT_TYPES.map((item) => <option key={item}>{item}</option>)}</select></label><label><span>{t.condition}</span><select value={artifactForm.condition_id} onChange={(event) => setArtifactForm({ ...artifactForm, condition_id: event.target.value })}><option value="">{t.studyLevel}</option>{detail.conditions.map((condition) => <option key={condition.id} value={condition.id}>{condition.name}</option>)}</select></label><label><span>{t.trial}</span><select value={artifactForm.trial_id} onChange={(event) => setArtifactForm({ ...artifactForm, trial_id: event.target.value })}><option value="">-</option>{detail.trials.map((trial) => <option key={trial.id} value={trial.id}>{trial.trial_id}</option>)}</select></label><label><span>{t.artifactPath}</span><input value={artifactForm.path} onChange={(event) => setArtifactForm({ ...artifactForm, path: event.target.value })} placeholder={t.artifactPathPlaceholder} /></label><label className="full-field"><span>{t.description}</span><textarea value={artifactForm.description} onChange={(event) => setArtifactForm({ ...artifactForm, description: event.target.value })} /></label></div><button className="primary" disabled={!artifactForm.path} onClick={() => void createArtifact()}><Plus size={16} />{t.addArtifact}</button><div className="condition-grid">{detail.artifacts.map((artifact) => <div className="paper-card" key={artifact.id}><strong>{artifact.artifact_type}</strong><code>{artifact.path}</code><span>{artifact.description || "-"}</span></div>)}</div></Section>}

          {tab === "analysis" && <Section title={t.analysisConclusion} icon={<BarChart3 size={16} />}><div className="form-grid two-col text-fields">{(["analysis_key_findings", "analysis_unexpected_findings", "analysis_failure_summary", "analysis_why_worked", "analysis_why_failed", "analysis_limitations", "analysis_threats_to_validity", "evidence_summary", "key_metric_improvements", "next_step"] as const).map((key) => <label key={key}><span>{label(t.analysisFields, key)}</span><textarea value={(detail.study[key] as string | null) ?? ""} onChange={(event) => setDetail({ ...detail, study: { ...detail.study, [key]: event.target.value } })} /></label>)}</div><button className="primary" onClick={() => void saveStudy(detail.study)}><Save size={16} />{t.saveAnalysis}</button></Section>}
        </>}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function Section({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return <div className="experiment-section"><h3>{icon}{title}</h3>{children}</div>;
}

function EditableText({ t, label: title, value, onChange, onSave }: { t: ExperimentsText; label: string; value?: string | null; onChange: (value: string) => void; onSave: () => void }) {
  return <label className="full-field"><span>{title}</span><textarea value={value ?? ""} onChange={(event) => onChange(event.target.value)} /><button onClick={onSave}><Save size={16} />{t.save}</button></label>;
}

function TrialTable({ t, detail, trialsByCondition, onlyFailures = false }: { t: ExperimentsText; detail: ExperimentStudyDetail; trialsByCondition: Record<number, ExperimentTrial[]>; onlyFailures?: boolean }) {
  return <div className="trial-table">{detail.conditions.map((condition) => {
    const rows = (trialsByCondition[condition.id] ?? []).filter((trial) => !onlyFailures || trial.result !== "Success");
    if (!rows.length && onlyFailures) return null;
    return <div key={condition.id} className="paper-card"><strong>{condition.name}</strong><div className="table compact-table">{rows.map((trial) => <div className="row trial-row" key={trial.id}><strong>{trial.trial_id}</strong><span>{trial.scene || "-"}</span><span>{label(t.resultLabels, trial.result)} · {trial.duration_seconds ?? "-"}s</span><span>{trial.failure_layer || trial.note || "-"}</span></div>)}</div>{!rows.length && <span className="muted">{t.noTrials}</span>}</div>;
  })}</div>;
}

function TraceList({ t, events }: { t: ExperimentsText; events: any[] }) {
  return <div className="trace-list">{events.map((event) => <div className="record" key={event.id}><strong>{event.order_index}. {label(t.traceLabels, event.event_type)} {event.title ? `- ${event.title}` : ""}</strong><span>{event.content}</span></div>)}{!events.length && <p className="muted">{t.noTrace}</p>}</div>;
}

function numberOrNull(value: string | number | null | undefined) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function label(labels: Record<string, string>, key?: string | null) {
  return (key && labels[key]) || key || "-";
}

function metricLabel(templates: MetricTemplate[], key: string) {
  const template = templates.find((item) => item.key === key);
  return template?.name_zh || template?.name || key;
}
