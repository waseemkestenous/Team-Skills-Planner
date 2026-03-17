from decimal import Decimal
from django.db.models import Prefetch
from .models import RoleSkill, Evaluation, ProjectRoleConstraint, ProjectShiftConstraint, ProjectBuildingConstraint


def normalize_score(scoring_type, value, status=None):
    value = float(value or 0)
    if scoring_type == 'Pass/Fail checklist':
        return 100.0 if status == 'Pass' else 0.0
    if scoring_type == 'Scored rubric (1-5)':
        return max(0.0, min(100.0, (value / 5.0) * 100.0))
    return value


def raw_value_by_type(scoring_type, value, status=None):
    value = float(value or 0)
    if scoring_type == 'Pass/Fail checklist':
        return 1.0 if status == 'Pass' else 0.0
    return value


def employee_role_map():
    return {rs.role_id: [] for rs in RoleSkill.objects.all()}


def latest_evaluation(employee):
    return employee.evaluations.order_by('date', 'code').last()


def evaluation_score(evaluation):
    if not evaluation:
        return 0.0
    rows = []
    for result in evaluation.results.select_related('skill').all():
        role_skill = RoleSkill.objects.filter(role=evaluation.employee.role, skill=result.skill).first()
        weight = float(role_skill.effective_weight() if role_skill else result.skill.default_weight)
        score = normalize_score(result.skill.scoring_type, result.value, result.status)
        if weight > 0:
            rows.append((weight, score))
    total_weight = sum(w for w, _ in rows)
    if not total_weight:
        return 0.0
    return round(sum(w * s for w, s in rows) / total_weight, 2)


def employee_level(employee):
    latest = latest_evaluation(employee)
    score = evaluation_score(latest)
    role = employee.role
    if score >= role.over_threshold:
        return 'Over Qualified'
    if score >= role.qualified_threshold:
        return 'Qualified'
    if score >= role.improve_threshold:
        return 'Needs Improvement'
    return 'Not Qualified'


def project_allows_role(project, role_name):
    allowed = set(project.allowed_roles.values_list('name', flat=True))
    return role_name in allowed if allowed else True


def project_candidate(project, employee):
    latest = latest_evaluation(employee)
    if not project_allows_role(project, employee.role.name):
        return {'fit': 0, 'status': 'Role Blocked', 'gaps': ['Role not allowed']}
    if not latest:
        return {'fit': 0, 'status': 'Not Ready', 'gaps': ['No evaluation']}
    results = {r.skill_id: r for r in latest.results.select_related('skill').all()}
    reqs = list(project.required_skills.select_related('skill').all())
    met = 0
    gaps = []
    for req in reqs:
        result = results.get(req.skill_id)
        if not result:
            gaps.append(f'{req.skill.name} missing')
            continue
        raw = raw_value_by_type(req.skill.scoring_type, result.value, result.status)
        if raw >= float(req.min_value):
            met += 1
        else:
            gaps.append(f'{req.skill.name} below min')
    fit = round((met / len(reqs)) * 100) if reqs else 100
    if gaps and met == 0:
        status = 'Not Ready'
    elif gaps:
        status = 'Partial'
    else:
        status = 'Ready'
    return {'fit': fit, 'status': status, 'gaps': gaps}


def summarize_constraint(constraint, assigned_count):
    status = 'Balanced'
    if assigned_count < constraint.min_required:
        status = 'Under Staffed'
    elif constraint.max_allowed and assigned_count > constraint.max_allowed:
        status = 'Over Staffed'
    return status
