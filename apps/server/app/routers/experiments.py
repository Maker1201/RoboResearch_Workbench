from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, object_session, selectinload

from .. import crud, git_service, models, schemas
from ..database import get_db

router = APIRouter()

METRIC_TEMPLATES = [
    {"key": "task_success_rate", "name": "Task Success Rate", "name_zh": "任务成功率", "group": "Task-level", "unit": "%"},
    {"key": "task_completion_rate", "name": "Task Completion Rate", "name_zh": "任务完成率", "group": "Task-level", "unit": "%"},
    {"key": "average_completion_time", "name": "Average Completion Time", "name_zh": "平均完成时间", "group": "Task-level", "unit": "s", "higher_is_better": False},
    {"key": "human_intervention_rate", "name": "Human Intervention Rate", "name_zh": "人工干预率", "group": "Task-level", "unit": "%", "higher_is_better": False},
    {"key": "planning_success_rate", "name": "Planning Success Rate", "name_zh": "规划成功率", "group": "Planning-level", "unit": "%"},
    {"key": "planning_latency", "name": "Planning Latency", "name_zh": "规划延迟", "group": "Planning-level", "unit": "s", "higher_is_better": False},
    {"key": "average_plan_length", "name": "Average Plan Length", "name_zh": "平均计划长度", "group": "Planning-level", "higher_is_better": False},
    {"key": "invalid_action_rate", "name": "Invalid Action Rate", "name_zh": "无效动作率", "group": "Planning-level", "unit": "%", "higher_is_better": False},
    {"key": "replanning_count", "name": "Replanning Count", "name_zh": "重规划次数", "group": "Planning-level", "higher_is_better": False},
    {"key": "action_execution_success", "name": "Action Execution Success", "name_zh": "动作执行成功率", "group": "Execution-level", "unit": "%"},
    {"key": "grasp_success", "name": "Grasp Success", "name_zh": "抓取成功率", "group": "Execution-level", "unit": "%"},
    {"key": "motion_planning_success", "name": "Motion Planning Success", "name_zh": "运动规划成功率", "group": "Execution-level", "unit": "%"},
    {"key": "insertion_success", "name": "Insertion Success", "name_zh": "插入装配成功率", "group": "Execution-level", "unit": "%"},
    {"key": "collision_rate", "name": "Collision Rate", "name_zh": "碰撞率", "group": "Execution-level", "unit": "%", "higher_is_better": False},
    {"key": "recovery_success_rate", "name": "Recovery Success Rate", "name_zh": "恢复成功率", "group": "Robustness", "unit": "%"},
    {"key": "failure_recovery_time", "name": "Failure Recovery Time", "name_zh": "失败恢复时间", "group": "Robustness", "unit": "s", "higher_is_better": False},
    {"key": "unrecoverable_failure_rate", "name": "Unrecoverable Failure Rate", "name_zh": "不可恢复失败率", "group": "Robustness", "unit": "%", "higher_is_better": False},
    {"key": "generalization_success", "name": "Generalization Success", "name_zh": "泛化成功率", "group": "Robustness", "unit": "%"},
]


def _public_study(study: models.ExperimentStudy) -> schemas.ExperimentStudyOut:
    conditions = list(study.conditions or [])
    trials = [trial for condition in conditions for trial in condition.trials]
    primary = next((metric for metric in study.metrics if metric.is_primary), None)
    primary_text = None
    if primary:
        value = primary.mean if primary.mean is not None else primary.value
        primary_text = f"{primary.metric_key}: {value if value is not None else primary.value_text or '-'}"
    data = schemas.ExperimentStudyOut.model_validate(study)
    data.conditions_count = len(conditions)
    data.trials_count = len(trials)
    data.primary_metric = primary_text
    data.project_name = study.project.name if study.project else None
    data.robot_name = study.robot_profile.name if study.robot_profile else None
    return data


def _public_condition(condition: models.ExperimentCondition) -> schemas.ExperimentConditionOut:
    data = schemas.ExperimentConditionOut.model_validate(condition)
    trials = condition.trials or []
    data.trials_count = len(trials)
    if trials:
        data.success_rate = round(100 * len([trial for trial in trials if trial.result == "Success"]) / len(trials), 2)
    return data


def _update_item(item: Any, payload: Any) -> Any:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    return item


def _detail(study: models.ExperimentStudy) -> schemas.ExperimentStudyDetailOut:
    conditions = sorted(study.conditions or [], key=lambda item: item.id)
    trials = [trial for condition in conditions for trial in sorted(condition.trials or [], key=lambda item: item.id)]
    trace_events = [event for trial in trials for event in sorted(trial.trace_events or [], key=lambda item: (item.order_index, item.id))]
    artifacts = list(study.artifacts or [])
    for condition in conditions:
        artifacts.extend(condition.artifacts or [])
    for trial in trials:
        artifacts.extend(trial.artifacts or [])
    failure_counter = Counter(filter(None, [trial.failure_layer or trial.failure_category for trial in trials if trial.result != "Success"]))
    condition_summary = {}
    for condition in conditions:
        condition_trials = condition.trials or []
        if not condition_trials:
            continue
        condition_summary[condition.name] = {
            "trials": len(condition_trials),
            "success": len([trial for trial in condition_trials if trial.result == "Success"]),
            "failed": len([trial for trial in condition_trials if trial.result == "Failed"]),
            "aborted": len([trial for trial in condition_trials if trial.result == "Aborted"]),
        }
    return schemas.ExperimentStudyDetailOut(
        study=_public_study(study),
        task_profile=study.task_profile,
        protocol=study.protocol,
        robot_profile=study.robot_profile,
        conditions=[_public_condition(condition) for condition in conditions],
        trials=trials,
        metrics=study.metrics,
        trace_events=trace_events,
        artifacts=artifacts,
        ablation_groups=study_ablation_groups(study, study.conditions),
        failure_summary=dict(failure_counter),
        result_summary=condition_summary,
    )


def study_ablation_groups(study: models.ExperimentStudy, conditions: list[models.ExperimentCondition]) -> list[models.AblationGroup]:
    ids = {condition.ablation_group_id for condition in conditions if condition.ablation_group_id}
    session = object_session(study)
    if not ids or session is None:
        return []
    return session.query(models.AblationGroup).filter(models.AblationGroup.id.in_(ids)).all()


def study_or_404(db: Session, study_id: int) -> models.ExperimentStudy:
    study = db.query(models.ExperimentStudy).options(
        selectinload(models.ExperimentStudy.project),
        selectinload(models.ExperimentStudy.robot_profile),
        selectinload(models.ExperimentStudy.task_profile),
        selectinload(models.ExperimentStudy.protocol),
        selectinload(models.ExperimentStudy.metrics),
        selectinload(models.ExperimentStudy.artifacts),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.trials).selectinload(models.ExperimentTrial.trace_events),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.metrics),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.artifacts),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.trials).selectinload(models.ExperimentTrial.metrics),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.trials).selectinload(models.ExperimentTrial.artifacts),
    ).filter(models.ExperimentStudy.id == study_id).first()
    if not study:
        raise HTTPException(status_code=404, detail="Experiment study not found")
    return study


@router.get("/robot-profiles", response_model=list[schemas.RobotProfileOut])
def list_robot_profiles(db: Session = Depends(get_db)):
    return db.query(models.RobotProfile).order_by(models.RobotProfile.id.desc()).all()


@router.post("/robot-profiles", response_model=schemas.RobotProfileOut)
def create_robot_profile(payload: schemas.RobotProfileCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.RobotProfile, payload)


@router.patch("/robot-profiles/{profile_id}", response_model=schemas.RobotProfileOut)
def update_robot_profile(profile_id: int, payload: schemas.RobotProfileUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.RobotProfile, profile_id, payload)


@router.get("/experiment-metric-templates")
def metric_templates() -> dict:
    return {"templates": METRIC_TEMPLATES}


@router.get("/experiment-studies", response_model=list[schemas.ExperimentStudyOut])
def list_experiment_studies(project_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ExperimentStudy).options(
        selectinload(models.ExperimentStudy.project),
        selectinload(models.ExperimentStudy.robot_profile),
        selectinload(models.ExperimentStudy.conditions).selectinload(models.ExperimentCondition.trials),
        selectinload(models.ExperimentStudy.metrics),
    )
    if project_id:
        query = query.filter(models.ExperimentStudy.project_id == project_id)
    if status:
        query = query.filter(models.ExperimentStudy.status == status)
    return [_public_study(study) for study in query.order_by(models.ExperimentStudy.updated_at.desc()).all()]


@router.post("/experiment-studies", response_model=schemas.ExperimentStudyDetailOut)
def create_experiment_study(payload: schemas.ExperimentStudyCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"task_profile", "protocol"})
    study = models.ExperimentStudy(**data)
    db.add(study)
    db.flush()
    if payload.task_profile:
        db.add(models.TaskProfile(study_id=study.id, **payload.task_profile.model_dump()))
    else:
        db.add(models.TaskProfile(
            study_id=study.id,
            task_name="Assembly task",
            task_steps="Detect part\nLocalize part\nGrasp part\nMove to assembly area\nAlign\nInsert\nVerify assembly",
            no_collision_required=True,
            timeout_required=True,
            human_intervention_allowed=False,
        ))
    if payload.protocol:
        db.add(models.ExperimentProtocol(study_id=study.id, **payload.protocol.model_dump()))
    else:
        db.add(models.ExperimentProtocol(study_id=study.id, trials_per_condition=30, timeout_seconds=120, max_retries=3, human_intervention_allowed=False))
    db.commit()
    return _detail(study_or_404(db, study.id))


@router.get("/experiment-studies/{study_id}", response_model=schemas.ExperimentStudyDetailOut)
def get_experiment_study(study_id: int, db: Session = Depends(get_db)):
    return _detail(study_or_404(db, study_id))


@router.patch("/experiment-studies/{study_id}", response_model=schemas.ExperimentStudyDetailOut)
def update_experiment_study(study_id: int, payload: schemas.ExperimentStudyUpdate, db: Session = Depends(get_db)):
    study = study_or_404(db, study_id)
    _update_item(study, payload)
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.patch("/experiment-studies/{study_id}/task-profile", response_model=schemas.ExperimentStudyDetailOut)
def upsert_task_profile(study_id: int, payload: schemas.TaskProfileUpdate, db: Session = Depends(get_db)):
    study = study_or_404(db, study_id)
    if study.task_profile:
        _update_item(study.task_profile, payload)
    else:
        db.add(models.TaskProfile(study_id=study.id, **payload.model_dump()))
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.patch("/experiment-studies/{study_id}/protocol", response_model=schemas.ExperimentStudyDetailOut)
def upsert_protocol(study_id: int, payload: schemas.ExperimentProtocolUpdate, db: Session = Depends(get_db)):
    study = study_or_404(db, study_id)
    if study.protocol:
        _update_item(study.protocol, payload)
    else:
        db.add(models.ExperimentProtocol(study_id=study.id, **payload.model_dump()))
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/experiment-conditions", response_model=schemas.ExperimentStudyDetailOut)
def create_condition(payload: schemas.ExperimentConditionCreate, db: Session = Depends(get_db)):
    study = study_or_404(db, payload.study_id)
    data = payload.model_dump()
    project_id = data.get("project_id") or study.project_id
    if project_id and not data.get("git_commit_hash"):
        project = db.get(models.Project, project_id)
        if project and project.path:
            try:
                status = git_service.status(project.path)
                data["project_id"] = project_id
                data["git_branch"] = data.get("git_branch") or status.get("branch")
                last_commit = status.get("last_commit") or ""
                data["git_commit_hash"] = last_commit.split(" ", 1)[0] if last_commit else None
                data["git_dirty"] = bool(status.get("changes"))
            except Exception:
                data["git_dirty"] = False
    db.add(models.ExperimentCondition(**data))
    db.commit()
    return _detail(study_or_404(db, payload.study_id))


@router.patch("/experiment-conditions/{condition_id}", response_model=schemas.ExperimentStudyDetailOut)
def update_condition(condition_id: int, payload: schemas.ExperimentConditionUpdate, db: Session = Depends(get_db)):
    condition = crud.get_item(db, models.ExperimentCondition, condition_id)
    study_id = condition.study_id
    _update_item(condition, payload)
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/experiment-trials", response_model=schemas.ExperimentStudyDetailOut)
def create_trial(payload: schemas.ExperimentTrialCreate, db: Session = Depends(get_db)):
    condition = crud.get_item(db, models.ExperimentCondition, payload.condition_id)
    db.add(models.ExperimentTrial(**payload.model_dump()))
    db.commit()
    return _detail(study_or_404(db, condition.study_id))


@router.patch("/experiment-trials/{trial_pk}", response_model=schemas.ExperimentStudyDetailOut)
def update_trial(trial_pk: int, payload: schemas.ExperimentTrialUpdate, db: Session = Depends(get_db)):
    trial = crud.get_item(db, models.ExperimentTrial, trial_pk)
    study_id = trial.condition.study_id
    _update_item(trial, payload)
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/planning-trace-events", response_model=schemas.ExperimentStudyDetailOut)
def create_trace_event(payload: schemas.PlanningTraceEventCreate, db: Session = Depends(get_db)):
    trial = crud.get_item(db, models.ExperimentTrial, payload.trial_id)
    study_id = trial.condition.study_id
    db.add(models.PlanningTraceEvent(**payload.model_dump()))
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/metric-values", response_model=schemas.ExperimentStudyDetailOut)
def create_metric_value(payload: schemas.MetricValueCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    study_id = data.get("study_id")
    if not study_id and data.get("condition_id"):
        study_id = crud.get_item(db, models.ExperimentCondition, data["condition_id"]).study_id
    if not study_id and data.get("trial_id"):
        study_id = crud.get_item(db, models.ExperimentTrial, data["trial_id"]).condition.study_id
    if not study_id:
        raise HTTPException(status_code=400, detail="Metric must be linked to a study, condition, or trial")
    db.add(models.MetricValue(**data))
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/artifact-references", response_model=schemas.ExperimentStudyDetailOut)
def create_artifact_reference(payload: schemas.ArtifactReferenceCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    study_id = data.get("study_id")
    if not study_id and data.get("condition_id"):
        study_id = crud.get_item(db, models.ExperimentCondition, data["condition_id"]).study_id
    if not study_id and data.get("trial_id"):
        study_id = crud.get_item(db, models.ExperimentTrial, data["trial_id"]).condition.study_id
    if not study_id:
        raise HTTPException(status_code=400, detail="Artifact must be linked to a study, condition, or trial")
    db.add(models.ArtifactReference(**data))
    db.commit()
    return _detail(study_or_404(db, study_id))


@router.post("/ablation-groups", response_model=schemas.ExperimentStudyDetailOut)
def create_ablation_group(payload: schemas.AblationGroupCreate, db: Session = Depends(get_db)):
    study_or_404(db, payload.study_id)
    db.add(models.AblationGroup(**payload.model_dump()))
    db.commit()
    return _detail(study_or_404(db, payload.study_id))
