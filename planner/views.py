import json
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    AvailabilityForm,
    EmployeeForm,
    EvaluationForm,
    EvaluationResultFormSet,
    LoginForm,
    ProjectBuildingConstraintFormSet,
    ProjectForm,
    ProjectRequiredSkillFormSet,
    ProjectRoleConstraintFormSet,
    ProjectShiftConstraintFormSet,
    RoleProfileForm,
    RoleSkillForm,
    SkillForm,
    TrainingForm,
)
from .models import (
    Employee,
    Evaluation,
    Project,
    RoleProfile,
    RoleSkill,
    Skill,
    Training,
)
from .utils import evaluation_score, employee_level, latest_evaluation, project_candidate, summarize_constraint


# ---------- shared helpers ----------
def navbar_items():
    return [
        ('dashboard', 'Dashboard'),
        ('team', 'Employees'),
        ('matrix', 'Skill Matrix'),
        ('projects', 'Projects'),
        ('training', 'Training'),
        ('admin_portal', 'Admin Portal'),
    ]


def admin_sections():
    return [
        ('admin_portal', 'Overview'),
        ('crud_roles', 'Roles'),
        ('crud_role_skills', 'Role Skills'),
        ('crud_skills', 'Skills'),
        ('crud_employees', 'Employees'),
        ('crud_projects', 'Projects'),
        ('crud_trainings', 'Trainings'),
        ('crud_evaluations', 'Evaluations'),
    ]


def base_context(active='dashboard'):
    return {'nav_items': navbar_items(), 'active_nav': active}


def admin_context(section='admin_portal'):
    ctx = base_context('admin_portal')
    ctx['admin_sections'] = admin_sections()
    ctx['active_admin_section'] = section
    return ctx


def crud_meta(title, subtitle, create_url=None, search_placeholder='Search...'):
    return {
        'title': title,
        'subtitle': subtitle,
        'create_url': create_url,
        'search_placeholder': search_placeholder,
    }


def list_filter(request, queryset, fields):
    q = request.GET.get('q', '').strip()
    if q:
        query = Q()
        for field in fields:
            query |= Q(**{f'{field}__icontains': q})
        queryset = queryset.filter(query)
    return queryset, q


def admin_only(request):
    if not request.user.is_staff:
        messages.error(request, 'Only staff users can access the CRUD UI.')
        return False
    return True


# ---------- auth ----------


def build_training_recommendation_map(employees, trainings):
    """Return recommendation and coverage data for training pages."""
    recommendation_counts = defaultdict(int)
    recommendation_employees = defaultdict(set)
    role_recommendation_counts = defaultdict(int)
    role_coverage = defaultdict(lambda: {'assigned': 0, 'recommended': 0})
    employee_gap_rows = []

    for emp in employees:
        latest = latest_evaluation(emp)
        gap_skill_ids = []
        gap_details = []
        if latest:
            for result in latest.results.select_related('skill').all():
                raw_value = result.value
                threshold = result.skill.min_value
                role_skill = RoleSkill.objects.filter(role=emp.role, skill=result.skill).first()
                if role_skill:
                    threshold = role_skill.effective_min_value()
                is_gap = result.status in ('Below Min', 'Fail')
                if not is_gap:
                    try:
                        is_gap = float(raw_value) < float(threshold)
                    except Exception:
                        is_gap = False
                if is_gap:
                    gap_skill_ids.append(result.skill_id)
                    gap_details.append({
                        'skill': result.skill,
                        'value': raw_value,
                        'threshold': threshold,
                        'status': result.status,
                        'notes': result.notes,
                    })

        assigned_ids = set(emp.trainings.values_list('id', flat=True))
        role_coverage[emp.role.name]['assigned'] += len(assigned_ids)

        recommended_ids = set()
        recommended_titles = []
        for training in trainings:
            linked_ids = set(training.linked_skills.values_list('id', flat=True))
            if linked_ids.intersection(gap_skill_ids):
                recommendation_counts[training.id] += 1
                recommendation_employees[training.id].add(emp.id)
                recommended_ids.add(training.id)
                recommended_titles.append(training.title)

        role_recommendation_counts[emp.role.name] += len(recommended_ids)
        role_coverage[emp.role.name]['recommended'] += len(recommended_ids)

        if gap_skill_ids:
            employee_gap_rows.append({
                'employee': emp,
                'score': evaluation_score(latest),
                'level': employee_level(emp),
                'recommended_titles': recommended_titles,
                'gap_skill_ids': gap_skill_ids,
                'gap_details': gap_details,
                'latest': latest,
            })

    return {
        'recommendation_counts': recommendation_counts,
        'recommendation_employees': recommendation_employees,
        'role_recommendation_counts': role_recommendation_counts,
        'role_coverage': role_coverage,
        'employee_gap_rows': employee_gap_rows,
    }

# ---------- auth ----------
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'planner/login.html', {'form': form})


# ---------- report views ----------
@login_required
def dashboard(request):
    employees = list(Employee.objects.select_related('role').prefetch_related('evaluations__results__skill', 'assigned_projects', 'availability'))
    projects = list(Project.objects.prefetch_related('allowed_roles', 'required_skills__skill', 'assigned_employees__role', 'role_constraints__role', 'shift_constraints__role', 'building_constraints__role'))

    def project_allows(project, employee):
        allowed = set(project.allowed_roles.values_list('id', flat=True))
        return employee.role_id in allowed if allowed else True

    project_rows = []
    under_staffed_rules = 0
    shift_issues = []
    building_issues = []
    ready_pool = 0
    role_names = sorted({e.role.name for e in employees})
    heatmap = defaultdict(dict)
    action_queue = []
    role_readiness = defaultdict(list)
    shift_readiness = defaultdict(list)
    building_readiness = defaultdict(list)

    for project in projects:
        candidates = [project_candidate(project, emp) for emp in employees]
        ready = sum(1 for c in candidates if c['status'] == 'Ready')
        partial = sum(1 for c in candidates if c['status'] == 'Partial')
        blocked = len(candidates) - ready - partial
        ready_pool += ready

        assigned = list(project.assigned_employees.select_related('role').all())
        role_issue_count = 0
        project_shift_issue_count = 0
        project_building_issue_count = 0
        for rc in project.role_constraints.select_related('role').all():
            assigned_count = sum(1 for a in assigned if a.role_id == rc.role_id)
            status = summarize_constraint(rc, assigned_count)
            if status != 'Balanced':
                role_issue_count += 1
                if status == 'Under Staffed':
                    under_staffed_rules += 1
                action_queue.append({'title': project.name, 'detail': f'{rc.role.name} is {status.lower()}', 'url': reverse('projects') + f'#project-{project.code}'})
            pct = int((assigned_count / rc.min_required) * 100) if rc.min_required else (100 if assigned_count else 0)
            heatmap[rc.role.name][project.code] = pct

        for sc in project.shift_constraints.select_related('role').all():
            assigned_count = sum(1 for a in assigned if a.shift == sc.shift and a.role_id == sc.role_id)
            status = summarize_constraint(sc, assigned_count)
            if status != 'Balanced':
                project_shift_issue_count += 1
                shift_issues.append({'project': project, 'constraint': sc, 'assigned': assigned_count, 'status': status})
        for bc in project.building_constraints.select_related('role').all():
            assigned_count = sum(1 for a in assigned if a.building == bc.building and a.role_id == bc.role_id)
            status = summarize_constraint(bc, assigned_count)
            if status != 'Balanced':
                project_building_issue_count += 1
                building_issues.append({'project': project, 'constraint': bc, 'assigned': assigned_count, 'status': status})

        health = round((ready / max(1, len(candidates))) * 60 + max(0, 40 - role_issue_count * 10 - project_shift_issue_count * 5 - project_building_issue_count * 5))
        project_rows.append({'project': project, 'ready': ready, 'partial': partial, 'blocked': blocked, 'role_issue_count': role_issue_count, 'shift_issue_count': project_shift_issue_count, 'building_issue_count': project_building_issue_count, 'health': max(0, min(100, health))})

        for role in project.allowed_roles.all():
            vals = [project_candidate(project, e)['fit'] for e in employees if e.role_id == role.id]
            if vals:
                role_readiness[role.name].append(sum(vals) / len(vals))
        for shift in {e.shift for e in employees}:
            vals = [project_candidate(project, e)['fit'] for e in employees if e.shift == shift and project_allows(project, e)]
            if vals:
                shift_readiness[shift].append(sum(vals) / len(vals))
        for building in {e.building for e in employees}:
            vals = [project_candidate(project, e)['fit'] for e in employees if e.building == building and project_allows(project, e)]
            if vals:
                building_readiness[building].append(sum(vals) / len(vals))

    def avg_map(d):
        return {k: round(sum(v) / len(v), 2) for k, v in d.items() if v}

    avg_health = round(sum(p['health'] for p in project_rows) / len(project_rows), 2) if project_rows else 0

    employees_with_eval = []
    employees_with_availability = 0
    overloaded_employees = 0
    assignable_employees = 0
    role_supply = defaultdict(lambda: {'employees': 0, 'assigned': 0})
    for emp in employees:
        latest = latest_evaluation(emp)
        if latest:
            employees_with_eval.append(evaluation_score(latest))
        availability = getattr(emp, 'availability', None)
        if availability:
            employees_with_availability += 1
        assigned_count = emp.assigned_projects.count()
        if availability and availability.max_concurrent_projects and assigned_count > availability.max_concurrent_projects:
            overloaded_employees += 1
        if assigned_count == 0:
            assignable_employees += 1
        role_supply[emp.role.name]['employees'] += 1
        role_supply[emp.role.name]['assigned'] += assigned_count

    project_status_counts = defaultdict(int)
    for project in projects:
        project_status_counts[project.status or 'Unknown'] += 1

    top_role_pressure = [
        {'role': role, 'employees': vals['employees'], 'assigned': vals['assigned']}
        for role, vals in sorted(role_supply.items(), key=lambda item: (-item[1]['assigned'], item[0]))
    ][:6]

    kpis = {
        'projects': Project.objects.filter(status='Active').count(),
        'avg_health': avg_health,
        'under_staffed': under_staffed_rules,
        'shift_issues': len(shift_issues),
        'building_issues': len(building_issues),
        'ready_pool': ready_pool,
        'employees': len(employees),
        'avg_employee_score': round(sum(employees_with_eval) / len(employees_with_eval), 2) if employees_with_eval else 0,
        'availability_profiles': employees_with_availability,
        'overloaded_employees': overloaded_employees,
        'assignable_employees': assignable_employees,
    }
    context = base_context('dashboard')
    context.update({
        'kpis': kpis,
        'project_rows': sorted(project_rows, key=lambda x: x['health']),
        'heatmap_roles': role_names,
        'heatmap_projects': [p.code for p in projects],
        'heatmap': dict(heatmap),
        'shift_issues': shift_issues[:10],
        'building_issues': building_issues[:10],
        'action_queue': action_queue[:8],
        'role_readiness': json.dumps(avg_map(role_readiness)),
        'shift_readiness': json.dumps(avg_map(shift_readiness)),
        'building_readiness': json.dumps(avg_map(building_readiness)),
        'constraint_pressure': json.dumps([
            {'label': p['project'].name, 'role': p['role_issue_count'], 'shift': p['shift_issue_count'], 'building': p['building_issue_count']}
            for p in project_rows
        ]),
        'project_status_counts': json.dumps(dict(project_status_counts)),
        'top_role_pressure': top_role_pressure,
        'health_bands': {
            'healthy': sum(1 for p in project_rows if p['health'] >= 85),
            'watch': sum(1 for p in project_rows if 70 <= p['health'] < 85),
            'risk': sum(1 for p in project_rows if p['health'] < 70),
        },
    })
    return render(request, 'planner/dashboard.html', context)


@login_required
def team(request):
    q = request.GET.get('q', '').strip()
    role_id = request.GET.get('role', '').strip()
    shift = request.GET.get('shift', '').strip()
    building = request.GET.get('building', '').strip()
    status = request.GET.get('status', '').strip()
    project_code = request.GET.get('project', '').strip()

    employees_qs = Employee.objects.select_related('role').prefetch_related(
        'evaluations__results__skill', 'assigned_projects', 'availability'
    )
    if role_id:
        employees_qs = employees_qs.filter(role_id=role_id)
    if shift:
        employees_qs = employees_qs.filter(shift=shift)
    if building:
        employees_qs = employees_qs.filter(building=building)
    if status:
        employees_qs = employees_qs.filter(status=status)
    if q:
        employees_qs = employees_qs.filter(
            Q(code__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q) | Q(role__name__icontains=q)
        )

    all_projects = list(Project.objects.prefetch_related('allowed_roles', 'required_skills__skill', 'assigned_employees'))
    projects = all_projects
    selected_project = None
    if project_code:
        projects = [p for p in all_projects if p.code == project_code]
        selected_project = projects[0] if projects else None

    rows = []
    for emp in employees_qs:
        latest = latest_evaluation(emp)
        assigned_projects = list(emp.assigned_projects.all())
        availability = getattr(emp, 'availability', None)
        readiness = {'Ready': 0, 'Partial': 0, 'Not Ready': 0, 'Role Blocked': 0}
        best_fit = 0
        selected_project_candidate = None
        for project in projects:
            cand = project_candidate(project, emp)
            readiness[cand['status']] = readiness.get(cand['status'], 0) + 1
            best_fit = max(best_fit, cand['fit'])
            if selected_project and project.code == selected_project.code:
                selected_project_candidate = cand
        max_concurrent = availability.max_concurrent_projects if availability else 0
        overbooked = bool(max_concurrent and len(assigned_projects) > max_concurrent)
        rows.append({
            'employee': emp,
            'score': evaluation_score(latest),
            'level': employee_level(emp),
            'latest_date': latest.date if latest else None,
            'eval_count': emp.evaluations.count(),
            'availability': availability,
            'assigned_projects': assigned_projects,
            'assigned_count': len(assigned_projects),
            'overbooked': overbooked,
            'ready_count': readiness.get('Ready', 0),
            'partial_count': readiness.get('Partial', 0),
            'blocked_count': readiness.get('Not Ready', 0) + readiness.get('Role Blocked', 0),
            'best_fit': best_fit,
            'selected_project_candidate': selected_project_candidate,
            'is_assigned_to_selected_project': bool(selected_project and any(p.code == selected_project.code for p in assigned_projects)),
        })

    role_options = list(RoleProfile.objects.order_by('name'))
    shift_options = sorted(Employee.objects.values_list('shift', flat=True).distinct())
    building_options = sorted(Employee.objects.values_list('building', flat=True).distinct())
    project_options = list(Project.objects.order_by('code'))

    kpis = {
        'employees': len(rows),
        'avg_score': round(sum(r['score'] for r in rows) / len(rows), 2) if rows else 0,
        'with_availability': sum(1 for r in rows if r['availability']),
        'overbooked': sum(1 for r in rows if r['overbooked']),
        'ready_for_any': sum(1 for r in rows if r['ready_count'] > 0),
        'assigned_projects': sum(r['assigned_count'] for r in rows),
    }

    context = base_context('team')
    context.update({
        'rows': rows,
        'roles': role_options,
        'shift_options': shift_options,
        'building_options': building_options,
        'project_options': project_options,
        'selected_project_obj': selected_project,
        'q': q,
        'selected_role': role_id,
        'selected_shift': shift,
        'selected_building': building,
        'selected_status': status,
        'selected_project': project_code,
        'kpis': kpis,
    })
    return render(request, 'planner/team.html', context)


@login_required
def workforce(request):
    return redirect('team')


@login_required
def employee_detail(request, code):
    emp = get_object_or_404(
        Employee.objects.select_related('role').prefetch_related(
            'evaluations__results__skill', 'assigned_projects__allowed_roles', 'assigned_projects__required_skills__skill', 'trainings', 'availability'
        ),
        code=code
    )
    latest = latest_evaluation(emp)
    latest_score = evaluation_score(latest)
    assigned_projects = list(emp.assigned_projects.all())
    trainings = list(emp.trainings.all())
    availability = getattr(emp, 'availability', None)

    eval_rows = []
    trend_labels = []
    trend_values = []
    score_deltas = []
    previous_score = None
    for ev in emp.evaluations.order_by('date'):
        score = evaluation_score(ev)
        eval_rows.append({'ev': ev, 'score': score, 'delta': None if previous_score is None else round(score - previous_score, 2)})
        trend_labels.append(ev.date.isoformat())
        trend_values.append(score)
        if previous_score is not None:
            score_deltas.append(score - previous_score)
        previous_score = score

    readiness_rows = []
    for project in Project.objects.prefetch_related('allowed_roles', 'required_skills__skill').all()[:8]:
        cand = project_candidate(project, emp)
        readiness_rows.append({'project': project, **cand})
    readiness_rows = sorted(readiness_rows, key=lambda x: (-x['fit'], x['project'].name))

    kpis = {
        'latest_score': latest_score,
        'level': employee_level(emp),
        'evaluations': len(eval_rows),
        'assigned_projects': len(assigned_projects),
        'trainings': len(trainings),
        'availability': 'Configured' if availability else 'Missing',
    }

    context = base_context('team')
    context.update({
        'emp': emp,
        'latest': latest,
        'level': employee_level(emp),
        'latest_score': latest_score,
        'eval_rows': list(reversed(eval_rows)),
        'trend_labels': json.dumps(trend_labels),
        'trend_values': json.dumps(trend_values),
        'assigned_projects': assigned_projects,
        'trainings': trainings,
        'availability': availability,
        'readiness_rows': readiness_rows[:6],
        'kpis': kpis,
    })
    return render(request, 'planner/employee_detail.html', context)


@login_required
def evaluation_detail(request, code):
    ev = get_object_or_404(Evaluation.objects.select_related('employee__role', 'project').prefetch_related('results__skill__trainings'), code=code)
    results = list(ev.results.select_related('skill').all())
    radar_labels = [r.skill.name for r in results[:8]]
    radar_values = [float(r.value) for r in results[:8]]
    score = evaluation_score(ev)
    role = ev.employee.role
    if score >= role.over_threshold:
        level = 'Over Qualified'
    elif score >= role.qualified_threshold:
        level = 'Qualified'
    elif score >= role.improve_threshold:
        level = 'Needs Improvement'
    else:
        level = 'Not Qualified'

    role_skill_map = {rs.skill_id: rs for rs in RoleSkill.objects.filter(role=role, skill__in=[r.skill for r in results]).select_related('skill')}
    detail_rows = []
    below_count = 0
    recommended_training_map = {}
    for result in results:
        role_skill = role_skill_map.get(result.skill_id)
        threshold = float(role_skill.effective_min_value() if role_skill else result.skill.min_value)
        raw_value = float(result.value or 0)
        if result.skill.scoring_type == 'Pass/Fail checklist':
            compare_value = 1.0 if result.status == 'Pass' else 0.0
        else:
            compare_value = raw_value
        gap = round(compare_value - threshold, 2)
        near_min = compare_value >= threshold and compare_value < threshold + 5
        state = 'ok' if compare_value >= threshold else ('near' if near_min else 'gap')
        if compare_value < threshold:
            below_count += 1
            for tr in result.skill.trainings.all():
                recommended_training_map[tr.id] = tr
        detail_rows.append({
            'result': result,
            'threshold': threshold,
            'gap': gap,
            'state': state,
        })

    project_fit = None
    if ev.project_id:
        project_fit = project_candidate(ev.project, ev.employee)

    context = base_context('crud_evaluations')
    context.update({
        'ev': ev, 'score': score, 'level': level, 'results': detail_rows,
        'radar_labels': json.dumps(radar_labels), 'radar_values': json.dumps(radar_values),
        'recommended_trainings': list(recommended_training_map.values()),
        'kpis': {
            'score': score,
            'skill_count': len(results),
            'below_count': below_count,
            'scope': ev.scope_label,
        },
        'project_fit': project_fit,
    })
    return render(request, 'planner/evaluation_detail.html', context)


@login_required
def matrix(request):
    selected_role = request.GET.get('role', '').strip()
    selected_pillar = request.GET.get('pillar', '').strip()
    q = request.GET.get('q', '').strip()

    role_groups = []
    role_qs = RoleProfile.objects.prefetch_related('roleskill_set__skill').all()
    roles = list(RoleProfile.objects.all())
    all_pillars = list(Skill.objects.values_list('pillar', flat=True).distinct())
    filtered_skills_total = 0

    for role in role_qs:
        if selected_role and str(role.pk) != selected_role:
            continue

        pillar_map = defaultdict(list)
        role_skills = list(role.roleskill_set.all())
        if selected_pillar:
            role_skills = [rs for rs in role_skills if rs.skill.pillar == selected_pillar]
        if q:
            ql = q.lower()
            role_skills = [
                rs for rs in role_skills
                if ql in (rs.skill.name or '').lower()
                or ql in (rs.skill.code or '').lower()
                or ql in (rs.skill.notes or '').lower()
                or ql in (rs.skill.scoring_type or '').lower()
                or ql in (rs.skill.pillar or '').lower()
                or ql in (role.name or '').lower()
            ]

        for rs in role_skills:
            pillar_map[rs.skill.pillar].append(rs)

        skills_count = len(role_skills)
        filtered_skills_total += skills_count
        if skills_count or selected_role or selected_pillar or q:
            role_groups.append({
                'role': role,
                'pillars': dict(sorted(pillar_map.items(), key=lambda item: item[0].lower())),
                'skills_count': skills_count,
            })

    visible_roles = len([g for g in role_groups if g['skills_count']])
    visible_pillars = len({pillar for group in role_groups for pillar in group['pillars'].keys()})
    context = base_context('matrix')
    context.update({
        'role_groups': role_groups,
        'roles': roles,
        'pillars': sorted(all_pillars),
        'skills_total': filtered_skills_total if (selected_role or selected_pillar or q) else Skill.objects.count(),
        'pillars_total': visible_pillars if (selected_role or selected_pillar or q) else Skill.objects.values('pillar').distinct().count(),
        'roles_total': visible_roles if (selected_role or selected_pillar or q) else len(roles),
        'selected_role': selected_role,
        'selected_pillar': selected_pillar,
        'q': q,
        'filters_active': bool(selected_role or selected_pillar or q),
    })
    return render(request, 'planner/matrix.html', context)




def build_project_row(project, employees):
    candidates = []
    gap_counter = defaultdict(int)
    assigned_rows = []
    assigned = list(project.assigned_employees.select_related('role').all())
    assigned_ids = {e.id for e in assigned}
    for emp in employees:
        c = project_candidate(project, emp)
        for gap in c['gaps']:
            gap_counter[gap] += 1
        latest = latest_evaluation(emp)
        candidates.append({'employee': emp, **c, 'is_assigned': emp.id in assigned_ids, 'score': evaluation_score(latest), 'level': employee_level(emp)})
    candidates = sorted(candidates, key=lambda x: (-x['fit'], x['employee'].name))
    ready = sum(1 for c in candidates if c['status'] == 'Ready')
    partial = sum(1 for c in candidates if c['status'] == 'Partial')
    blocked = len(candidates) - ready - partial

    for emp in assigned:
        cand = project_candidate(project, emp)
        assigned_rows.append({'employee': emp, **cand, 'score': evaluation_score(latest_evaluation(emp)), 'level': employee_level(emp)})
    assigned_rows = sorted(assigned_rows, key=lambda x: (-x['fit'], x['employee'].name))

    role_rows = []
    role_issue_count = 0
    total_understaffed = 0
    for rc in project.role_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == rc.role_id)
        staffing_status = summarize_constraint(rc, assigned_count)
        if staffing_status != 'Balanced':
            role_issue_count += 1
            if staffing_status == 'Under Staffed':
                total_understaffed += 1
        role_rows.append({'constraint': rc, 'assigned': assigned_count, 'status': staffing_status})

    shift_rows = []
    shift_issue_count = 0
    for sc in project.shift_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == sc.role_id and a.shift == sc.shift)
        staffing_status = summarize_constraint(sc, assigned_count)
        if staffing_status != 'Balanced':
            shift_issue_count += 1
        shift_rows.append({'constraint': sc, 'assigned': assigned_count, 'status': staffing_status})

    building_rows = []
    building_issue_count = 0
    for bc in project.building_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == bc.role_id and a.building == bc.building)
        staffing_status = summarize_constraint(bc, assigned_count)
        if staffing_status != 'Balanced':
            building_issue_count += 1
        building_rows.append({'constraint': bc, 'assigned': assigned_count, 'status': staffing_status})

    health = round((ready / max(1, len(candidates))) * 60 + max(0, 40 - role_issue_count * 10 - shift_issue_count * 5 - building_issue_count * 5))
    health = max(0, min(100, health))
    recommended_rows = [c for c in candidates if not c['is_assigned']][:12]
    return {
        'project': project,
        'candidates': candidates,
        'recommended_rows': recommended_rows,
        'assigned_rows': assigned_rows,
        'ready': ready,
        'partial': partial,
        'blocked': blocked,
        'health': health,
        'role_rows': role_rows,
        'shift_rows': shift_rows,
        'building_rows': building_rows,
        'role_issue_count': role_issue_count,
        'shift_issue_count': shift_issue_count,
        'building_issue_count': building_issue_count,
        'top_gaps': sorted(gap_counter.items(), key=lambda x: (-x[1], x[0]))[:5],
        'total_understaffed': total_understaffed,
    }


def build_project_summary(project, employees):
    gap_counter = defaultdict(int)
    assigned = list(project.assigned_employees.select_related('role').all())
    assigned_ids = {e.id for e in assigned}
    ready = partial = blocked = 0
    best_fit = []
    role_issue_count = shift_issue_count = building_issue_count = 0
    total_understaffed = 0

    for emp in employees:
        c = project_candidate(project, emp)
        if c['status'] == 'Ready':
            ready += 1
        elif c['status'] == 'Partial':
            partial += 1
        else:
            blocked += 1
        for gap in c['gaps']:
            gap_counter[gap] += 1
        if emp.id not in assigned_ids:
            best_fit.append({'employee': emp, **c, 'score': evaluation_score(latest_evaluation(emp)), 'level': employee_level(emp)})

    best_fit = sorted(best_fit, key=lambda x: (-x['fit'], x['employee'].name))[:5]
    assigned_preview = []
    for emp in assigned[:5]:
        cand = project_candidate(project, emp)
        assigned_preview.append({'employee': emp, **cand, 'score': evaluation_score(latest_evaluation(emp)), 'level': employee_level(emp)})

    for rc in project.role_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == rc.role_id)
        staffing_status = summarize_constraint(rc, assigned_count)
        if staffing_status != 'Balanced':
            role_issue_count += 1
            if staffing_status == 'Under Staffed':
                total_understaffed += 1

    for sc in project.shift_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == sc.role_id and a.shift == sc.shift)
        if summarize_constraint(sc, assigned_count) != 'Balanced':
            shift_issue_count += 1

    for bc in project.building_constraints.select_related('role').all():
        assigned_count = sum(1 for a in assigned if a.role_id == bc.role_id and a.building == bc.building)
        if summarize_constraint(bc, assigned_count) != 'Balanced':
            building_issue_count += 1

    health = round((ready / max(1, ready + partial + blocked)) * 60 + max(0, 40 - role_issue_count * 10 - shift_issue_count * 5 - building_issue_count * 5))
    health = max(0, min(100, health))
    return {
        'project': project,
        'ready': ready,
        'partial': partial,
        'blocked': blocked,
        'health': health,
        'assigned_preview': assigned_preview,
        'best_fit_preview': best_fit,
        'assigned_count': len(assigned),
        'required_skills_count': project.required_skills.count(),
        'role_issue_count': role_issue_count,
        'shift_issue_count': shift_issue_count,
        'building_issue_count': building_issue_count,
        'top_gaps': sorted(gap_counter.items(), key=lambda x: (-x[1], x[0]))[:3],
        'total_understaffed': total_understaffed,
    }


@login_required
def projects(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    owner = request.GET.get('owner', '').strip()

    projects_qs = Project.objects.prefetch_related(
        'allowed_roles', 'required_skills__skill', 'assigned_employees__role',
        'role_constraints__role', 'shift_constraints__role', 'building_constraints__role'
    )
    if status:
        projects_qs = projects_qs.filter(status=status)
    if owner:
        projects_qs = projects_qs.filter(owner=owner)
    if q:
        projects_qs = projects_qs.filter(
            Q(code__icontains=q) | Q(name__icontains=q) | Q(owner__icontains=q) |
            Q(allowed_roles__name__icontains=q) | Q(required_skills__skill__name__icontains=q)
        ).distinct()

    employees = list(Employee.objects.select_related('role').prefetch_related('evaluations__results__skill', 'assigned_projects'))
    rows = []
    total_ready = total_partial = total_blocked = 0
    total_understaffed = 0
    health_values = []
    for project in projects_qs:
        row = build_project_summary(project, employees)
        total_ready += row['ready']
        total_partial += row['partial']
        total_blocked += row['blocked']
        total_understaffed += row['total_understaffed']
        health_values.append(row['health'])
        rows.append(row)

    owners = list(Project.objects.order_by('owner').values_list('owner', flat=True).distinct())
    statuses = [choice[0] for choice in Project.STATUS_CHOICES]
    kpis = {
        'projects': len(rows),
        'active': sum(1 for r in rows if r['project'].status == 'Active'),
        'avg_health': round(sum(health_values) / len(health_values), 2) if health_values else 0,
        'ready_pool': total_ready,
        'partial_pool': total_partial,
        'blocked_pool': total_blocked,
        'understaffed': total_understaffed,
    }
    context = base_context('projects')
    context.update({
        'rows': sorted(rows, key=lambda x: (x['health'], x['project'].code)),
        'q': q,
        'selected_status': status,
        'selected_owner': owner,
        'owners': owners,
        'statuses': statuses,
        'kpis': kpis,
    })
    return render(request, 'planner/projects.html', context)


@login_required
def project_detail(request, code):
    project = get_object_or_404(
        Project.objects.prefetch_related(
            'allowed_roles', 'required_skills__skill', 'assigned_employees__role',
            'role_constraints__role', 'shift_constraints__role', 'building_constraints__role'
        ),
        code=code
    )
    employees = list(Employee.objects.select_related('role').prefetch_related('evaluations__results__skill', 'assigned_projects'))
    row = build_project_row(project, employees)
    context = base_context('projects')
    context.update({
        'row': row,
        'project': project,
        'kpis': {
            'health': row['health'],
            'assigned': len(row['assigned_rows']),
            'ready': row['ready'],
            'partial': row['partial'],
            'issues': row['role_issue_count'] + row['shift_issue_count'] + row['building_issue_count'],
            'required_skills': project.required_skills.count(),
        }
    })
    return render(request, 'planner/project_detail.html', context)


@login_required
def project_assign_employee(request, code):
    project = get_object_or_404(Project, code=code)
    employee_code = request.POST.get('employee_code', '').strip()
    employee = get_object_or_404(Employee.objects.select_related('role').prefetch_related('evaluations__results__skill', 'assigned_projects'), code=employee_code)
    candidate = project_candidate(project, employee)
    if candidate['status'] == 'Role Blocked':
        messages.error(request, f'{employee.name} cannot be assigned because the role is not allowed for this project.')
    else:
        project.assigned_employees.add(employee)
        if candidate['status'] == 'Ready':
            messages.success(request, f'{employee.name} assigned to {project.name}.')
        else:
            detail = '; '.join(candidate['gaps'][:2]) if candidate['gaps'] else 'Some requirements are still below threshold.'
            messages.warning(request, f'{employee.name} assigned with partial readiness. {detail}')
    return redirect('project_detail', code=project.code)


@login_required
def project_unassign_employee(request, code):
    project = get_object_or_404(Project, code=code)
    employee_code = request.POST.get('employee_code', '').strip()
    employee = get_object_or_404(Employee, code=employee_code)
    project.assigned_employees.remove(employee)
    messages.success(request, f'{employee.name} removed from {project.name}.')
    return redirect('project_detail', code=project.code)


@login_required
def training(request):
    q = request.GET.get('q', '').strip()
    selected_type = request.GET.get('type', '').strip()
    selected_owner = request.GET.get('owner', '').strip()
    selected_skill = request.GET.get('skill', '').strip()
    selected_role = request.GET.get('role', '').strip()

    trainings_qs = Training.objects.prefetch_related('linked_skills', 'employees__role').all()
    employees = list(Employee.objects.select_related('role').prefetch_related('trainings', 'evaluations__results__skill'))
    skills = list(Skill.objects.order_by('pillar', 'name'))
    roles = list(RoleProfile.objects.order_by('name'))

    owners = list(Training.objects.order_by('owner').values_list('owner', flat=True).distinct())
    training_types = list(Training.objects.order_by('training_type').values_list('training_type', flat=True).distinct())

    if q:
        trainings_qs = trainings_qs.filter(
            Q(code__icontains=q)
            | Q(title__icontains=q)
            | Q(owner__icontains=q)
            | Q(training_type__icontains=q)
            | Q(duration__icontains=q)
            | Q(linked_skills__name__icontains=q)
            | Q(linked_skills__pillar__icontains=q)
        ).distinct()
    if selected_type:
        trainings_qs = trainings_qs.filter(training_type=selected_type)
    if selected_owner:
        trainings_qs = trainings_qs.filter(owner=selected_owner)
    if selected_skill:
        trainings_qs = trainings_qs.filter(linked_skills__id=selected_skill)
    if selected_role:
        trainings_qs = trainings_qs.filter(employees__role__id=selected_role).distinct()

    trainings = list(trainings_qs)
    filtered_training_ids = {t.id for t in trainings}

    rec = build_training_recommendation_map(employees, trainings)

    training_rows = []
    for training_obj in trainings:
        assigned_employees = list(training_obj.employees.select_related('role').all())
        assigned_roles = sorted({emp.role.name for emp in assigned_employees})
        linked_skills = list(training_obj.linked_skills.all())
        training_rows.append({
            'training': training_obj,
            'assigned_employees': assigned_employees,
            'assigned_roles': assigned_roles,
            'linked_skills': linked_skills,
            'recommended_count': rec['recommendation_counts'].get(training_obj.id, 0),
            'recommended_employees': len(rec['recommendation_employees'].get(training_obj.id, set())),
        })

    top_recommendations = [
        row for row in sorted(training_rows, key=lambda x: (x['recommended_count'], x['recommended_employees']), reverse=True)
        if row['training'].id in filtered_training_ids
    ][:6]

    role_training_counts = defaultdict(int)
    for training_obj in trainings:
        linked_role_ids = set(training_obj.employees.values_list('role_id', flat=True))
        for role_id in linked_role_ids:
            role_training_counts[role_id] += 1

    role_coverage_rows = []
    for role in roles:
        cov = rec['role_coverage'][role.name]
        role_coverage_rows.append({
            'role': role,
            'assigned': cov['assigned'],
            'recommended': rec['role_recommendation_counts'][role.name],
            'training_count': role_training_counts.get(role.id, 0),
        })

    kpis = {
        'trainings': len(trainings),
        'linked_skills_avg': round(sum(len(row['linked_skills']) for row in training_rows) / len(training_rows), 2) if training_rows else 0,
        'assignments': sum(len(row['assigned_employees']) for row in training_rows),
        'employees_with_gaps': len(rec['employee_gap_rows']),
    }

    context = base_context('training')
    context.update({
        'q': q,
        'selected_type': selected_type,
        'selected_owner': selected_owner,
        'selected_skill': selected_skill,
        'selected_role': selected_role,
        'owners': owners,
        'training_types': training_types,
        'skills': skills,
        'roles': roles,
        'kpis': kpis,
        'training_rows': training_rows,
        'top_recommendations': top_recommendations,
        'role_coverage_rows': role_coverage_rows,
        'employee_gap_rows': rec['employee_gap_rows'][:20],
    })
    return render(request, 'planner/training.html', context)


@login_required
def training_detail(request, code):
    training_obj = get_object_or_404(
        Training.objects.prefetch_related('linked_skills', 'employees__role', 'employees__assigned_projects', 'employees__evaluations__results__skill'),
        code=code,
    )
    employees = list(Employee.objects.select_related('role').prefetch_related('trainings', 'assigned_projects', 'evaluations__results__skill'))
    trainings = list(Training.objects.prefetch_related('linked_skills').all())
    rec = build_training_recommendation_map(employees, trainings)

    linked_skills = list(training_obj.linked_skills.order_by('pillar', 'name'))
    linked_skill_ids = {skill.id for skill in linked_skills}
    assigned_employees = list(training_obj.employees.select_related('role').prefetch_related('assigned_projects').all())
    assigned_employee_ids = {emp.id for emp in assigned_employees}

    assigned_role_names = sorted({emp.role.name for emp in assigned_employees})
    assigned_project_names = sorted({p.name for emp in assigned_employees for p in emp.assigned_projects.all()})

    recommended_rows = []
    for row in rec['employee_gap_rows']:
        matched_gaps = [g for g in row['gap_details'] if g['skill'].id in linked_skill_ids]
        if not matched_gaps:
            continue
        already_assigned = row['employee'].id in assigned_employee_ids
        recommended_rows.append({
            'employee': row['employee'],
            'score': row['score'],
            'level': row['level'],
            'latest': row['latest'],
            'matched_gaps': matched_gaps,
            'already_assigned': already_assigned,
            'gap_count': len(matched_gaps),
        })

    recommended_rows.sort(key=lambda x: (x['already_assigned'], -x['gap_count'], x['score']))

    skill_demand = []
    for skill in linked_skills:
        hits = []
        for row in recommended_rows:
            for gap in row['matched_gaps']:
                if gap['skill'].id == skill.id:
                    hits.append(row['employee'].id)
                    break
        skill_demand.append({'skill': skill, 'employees': len(set(hits))})

    kpis = {
        'linked_skills': len(linked_skills),
        'assigned_count': len(assigned_employees),
        'recommended_count': len(recommended_rows),
        'unassigned_recommended': sum(1 for row in recommended_rows if not row['already_assigned']),
    }

    context = base_context('training')
    context.update({
        'training': training_obj,
        'linked_skills': linked_skills,
        'assigned_employees': assigned_employees,
        'assigned_role_names': assigned_role_names,
        'assigned_project_names': assigned_project_names,
        'recommended_rows': recommended_rows,
        'recommended_unassigned_ids': [row['employee'].id for row in recommended_rows if not row['already_assigned']],
        'skill_demand': skill_demand,
        'kpis': kpis,
    })
    return render(request, 'planner/training_detail.html', context)


@login_required
def training_assign_employee(request, code):
    if request.method != 'POST':
        return redirect('training_detail', code=code)
    training_obj = get_object_or_404(Training, code=code)
    employee = get_object_or_404(Employee, pk=request.POST.get('employee_id'))
    employee.trainings.add(training_obj)
    messages.success(request, f'{employee.name} assigned to {training_obj.title}.')
    return redirect('training_detail', code=code)


@login_required
def training_unassign_employee(request, code):
    if request.method != 'POST':
        return redirect('training_detail', code=code)
    training_obj = get_object_or_404(Training, code=code)
    employee = get_object_or_404(Employee, pk=request.POST.get('employee_id'))
    employee.trainings.remove(training_obj)
    messages.success(request, f'{employee.name} unassigned from {training_obj.title}.')
    return redirect('training_detail', code=code)


@login_required
def training_bulk_assign(request, code):
    if request.method != 'POST':
        return redirect('training_detail', code=code)
    training_obj = get_object_or_404(Training.objects.prefetch_related('linked_skills'), code=code)
    selected_ids = [int(v) for v in request.POST.getlist('employee_ids') if str(v).isdigit()]
    employees = list(Employee.objects.select_related('role').prefetch_related('trainings', 'evaluations__results__skill'))
    trainings = list(Training.objects.prefetch_related('linked_skills').all())
    rec = build_training_recommendation_map(employees, trainings)
    linked_skill_ids = set(training_obj.linked_skills.values_list('id', flat=True))
    recommended_ids = set()
    for row in rec['employee_gap_rows']:
        if any(g['skill'].id in linked_skill_ids for g in row['gap_details']):
            recommended_ids.add(row['employee'].id)
    if not selected_ids:
        selected_ids = sorted(recommended_ids)
    eligible_ids = [emp_id for emp_id in selected_ids if emp_id in recommended_ids]
    already_ids = set(training_obj.employees.values_list('id', flat=True))
    assign_ids = [emp_id for emp_id in eligible_ids if emp_id not in already_ids]
    if assign_ids:
        for employee in Employee.objects.filter(id__in=assign_ids):
            employee.trainings.add(training_obj)
        messages.success(request, f'Assigned {len(assign_ids)} employee(s) to {training_obj.title}.')
    else:
        messages.info(request, 'No new recommended employees were assigned.')
    return redirect('training_detail', code=code)


@login_required
def admin_portal(request):
    if not admin_only(request):
        return redirect('dashboard')
    context = admin_context('admin_portal')
    context.update({
        'counts': {
            'roles': RoleProfile.objects.count(),
            'skills': Skill.objects.count(),
            'role skills': RoleSkill.objects.count(),
            'employees': Employee.objects.count(),
            'projects': Project.objects.count(),
            'evaluations': Evaluation.objects.count(),
            'trainings': Training.objects.count(),
        }
    })
    return render(request, 'planner/admin_portal.html', context)


@login_required
def crud_roles(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows, q = list_filter(request, RoleProfile.objects.all(), ['name'])
    context = admin_context('crud_roles')
    context.update({'rows': rows, 'q': q, 'meta': crud_meta('Roles', 'Manage role thresholds and level boundaries.', reverse('role_create'), 'Search roles...')})
    return render(request, 'planner/crud/role_list.html', context)


@login_required
def role_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = RoleProfile.objects.filter(pk=pk).first()
    form = RoleProfileForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Role {obj.name} saved.')
        return redirect('crud_roles')
    context = admin_context('crud_roles')
    context.update({'form': form, 'object': instance, 'meta': crud_meta('Role Form', 'Create or update a role and its thresholds.')})
    return render(request, 'planner/crud/role_form.html', context)


@login_required
def role_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(RoleProfile, pk=pk)
    if request.method == 'POST':
        name = obj.name
        obj.delete()
        messages.success(request, f'Role {name} deleted.')
        return redirect('crud_roles')
    context = admin_context('crud_roles')
    context.update({'object': obj, 'cancel_url': reverse('crud_roles'), 'title': 'Delete role'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_skills(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows, q = list_filter(request, Skill.objects.all(), ['code', 'pillar', 'name'])
    context = admin_context('crud_skills')
    context.update({'rows': rows, 'q': q, 'meta': crud_meta('Skills', 'Manage the skill catalog used by roles, projects, and evaluations.', reverse('skill_create'), 'Search skills...')})
    return render(request, 'planner/crud/skill_list.html', context)


@login_required
def skill_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = Skill.objects.filter(pk=pk).first()
    form = SkillForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Skill {obj.name} saved.')
        return redirect('crud_skills')
    context = admin_context('crud_skills')
    context.update({'form': form, 'object': instance, 'meta': crud_meta('Skill Form', 'Create or update a skill in the catalog.')})
    return render(request, 'planner/crud/simple_form.html', context)


@login_required
def skill_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(Skill, pk=pk)
    if request.method == 'POST':
        name = obj.name
        obj.delete()
        messages.success(request, f'Skill {name} deleted.')
        return redirect('crud_skills')
    context = admin_context('crud_skills')
    context.update({'object': obj, 'cancel_url': reverse('crud_skills'), 'title': 'Delete skill'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_role_skills(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows = RoleSkill.objects.select_related('role', 'skill').all()
    role_id = request.GET.get('role')
    if role_id:
        rows = rows.filter(role_id=role_id)
    q = request.GET.get('q', '').strip()
    if q:
        rows = rows.filter(Q(role__name__icontains=q) | Q(skill__name__icontains=q) | Q(skill__pillar__icontains=q))
    context = admin_context('crud_role_skills')
    context.update({'rows': rows, 'roles': RoleProfile.objects.all(), 'selected_role': role_id or '', 'q': q, 'meta': crud_meta('Role Skill Mapping', 'Override weight and minimum per skill for each role.', reverse('role_skill_create'), 'Search role-skill mappings...')})
    return render(request, 'planner/crud/role_skill_list.html', context)


@login_required
def role_skill_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = RoleSkill.objects.filter(pk=pk).first()
    form = RoleSkillForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Role skill mapping for {obj.role.name} / {obj.skill.name} saved.')
        return redirect('crud_role_skills')
    context = admin_context('crud_role_skills')
    context.update({'form': form, 'object': instance, 'meta': crud_meta('Role Skill Form', 'Create or update role-specific skill rules.')})
    return render(request, 'planner/crud/simple_form.html', context)


@login_required
def role_skill_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(RoleSkill, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Role skill mapping deleted.')
        return redirect('crud_role_skills')
    context = admin_context('crud_role_skills')
    context.update({'object': obj, 'cancel_url': reverse('crud_role_skills'), 'title': 'Delete role skill mapping'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_employees(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows = Employee.objects.select_related('role').prefetch_related('trainings', 'assigned_projects', 'evaluations__results__skill', 'availability')
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')
    shift = request.GET.get('shift', '')
    building = request.GET.get('building', '')
    if role:
        rows = rows.filter(role_id=role)
    if status:
        rows = rows.filter(status=status)
    if shift:
        rows = rows.filter(shift=shift)
    if building:
        rows = rows.filter(building=building)
    rows, q = list_filter(request, rows, ['code', 'name', 'email', 'shift', 'building', 'role__name'])
    enriched = []
    latest_scores = []
    eval_counts = []
    with_availability = 0
    active_count = 0
    for emp in rows:
        latest = latest_evaluation(emp)
        latest_score = evaluation_score(latest)
        latest_scores.append(latest_score)
        eval_count = emp.evaluations.count()
        eval_counts.append(eval_count)
        assigned_projects = list(emp.assigned_projects.all())
        trainings = list(emp.trainings.all())
        availability = getattr(emp, 'availability', None)
        with_availability += 1 if availability else 0
        active_count += 1 if emp.status == 'Active' else 0
        enriched.append({
            'employee': emp,
            'latest': latest,
            'latest_score': latest_score,
            'level': employee_level(emp),
            'eval_count': eval_count,
            'assigned_projects': assigned_projects,
            'trainings': trainings,
            'availability': availability,
            'overbooked': bool(availability and availability.max_concurrent_projects and len(assigned_projects) > availability.max_concurrent_projects),
        })
    context = admin_context('crud_employees')
    context.update({
        'rows': enriched,
        'roles': RoleProfile.objects.all(),
        'statuses': [x[0] for x in Employee.STATUS_CHOICES],
        'shift_options': sorted(Employee.objects.values_list('shift', flat=True).distinct()),
        'building_options': sorted(Employee.objects.values_list('building', flat=True).distinct()),
        'selected_role': role,
        'selected_status': status,
        'selected_shift': shift,
        'selected_building': building,
        'q': q,
        'kpis': {
            'employees': len(enriched),
            'active': active_count,
            'avg_score': round(sum(latest_scores) / len(latest_scores), 2) if latest_scores else 0,
            'avg_evals': round(sum(eval_counts) / len(eval_counts), 2) if eval_counts else 0,
            'with_availability': with_availability,
        },
        'meta': crud_meta('Employees', 'Manage roster, role assignment, training links, project links, and availability.', reverse('employee_create'), 'Search employees...')
    })
    return render(request, 'planner/crud/employee_list.html', context)


@login_required
def employee_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = Employee.objects.filter(pk=pk).first()
    form = EmployeeForm(request.POST or None, instance=instance)
    availability_instance = getattr(instance, 'availability', None) if instance else None
    availability_form = AvailabilityForm(request.POST or None, instance=availability_instance)
    if availability_instance:
        availability_form.initial_from_instance()
    if request.method == 'POST' and form.is_valid() and availability_form.is_valid():
        obj = form.save()
        availability = availability_form.save(commit=False)
        availability.employee = obj
        availability.save()
        messages.success(request, f'Employee {obj.name} saved.')
        return redirect('crud_employees')
    context = admin_context('crud_employees')
    context.update({'form': form, 'availability_form': availability_form, 'object': instance, 'meta': crud_meta('Employee Form', 'Create or update an employee and availability profile.')})
    return render(request, 'planner/crud/employee_form.html', context)


@login_required
def employee_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        name = obj.name
        obj.delete()
        messages.success(request, f'Employee {name} deleted.')
        return redirect('crud_employees')
    context = admin_context('crud_employees')
    context.update({'object': obj, 'cancel_url': reverse('crud_employees'), 'title': 'Delete employee'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_trainings(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows, q = list_filter(request, Training.objects.prefetch_related('linked_skills').all(), ['code', 'title', 'training_type', 'owner'])
    context = admin_context('crud_trainings')
    context.update({'rows': rows, 'q': q, 'meta': crud_meta('Trainings', 'Manage the training catalog and linked skills.', reverse('training_create'), 'Search trainings...')})
    return render(request, 'planner/crud/training_list.html', context)


@login_required
def training_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = Training.objects.filter(pk=pk).first()
    form = TrainingForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, f'Training {obj.title} saved.')
        return redirect('crud_trainings')
    context = admin_context('crud_trainings')
    context.update({'form': form, 'object': instance, 'meta': crud_meta('Training Form', 'Create or update training programs.')})
    return render(request, 'planner/crud/simple_form.html', context)


@login_required
def training_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(Training, pk=pk)
    if request.method == 'POST':
        title = obj.title
        obj.delete()
        messages.success(request, f'Training {title} deleted.')
        return redirect('crud_trainings')
    context = admin_context('crud_trainings')
    context.update({'object': obj, 'cancel_url': reverse('crud_trainings'), 'title': 'Delete training'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_projects(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows = Project.objects.prefetch_related(
        'allowed_roles', 'required_skills__skill', 'role_constraints__role', 'shift_constraints__role',
        'building_constraints__role', 'assigned_employees__role'
    )
    status = request.GET.get('status', '')
    owner = request.GET.get('owner', '')
    if status:
        rows = rows.filter(status=status)
    if owner:
        rows = rows.filter(owner=owner)
    rows, q = list_filter(request, rows, ['code', 'name', 'owner', 'status'])
    enriched = []
    active = at_risk = blocked = 0
    total_assigned = total_rules = 0
    for project in rows:
        required_skills = list(project.required_skills.select_related('skill').all())
        role_constraints = list(project.role_constraints.select_related('role').all())
        shift_constraints = list(project.shift_constraints.select_related('role').all())
        building_constraints = list(project.building_constraints.select_related('role').all())
        assigned_employees = list(project.assigned_employees.select_related('role').all())
        role_issues = 0
        for rc in role_constraints:
            assigned_count = sum(1 for emp in assigned_employees if emp.role_id == rc.role_id)
            if summarize_constraint(rc, assigned_count) != 'Balanced':
                role_issues += 1
        total_rules += len(required_skills) + len(role_constraints) + len(shift_constraints) + len(building_constraints)
        total_assigned += len(assigned_employees)
        active += 1 if project.status == 'Active' else 0
        at_risk += 1 if project.status == 'At Risk' else 0
        blocked += 1 if project.status == 'Blocked' else 0
        enriched.append({
            'project': project,
            'required_skills': required_skills,
            'role_constraints': role_constraints,
            'shift_constraints': shift_constraints,
            'building_constraints': building_constraints,
            'assigned_employees': assigned_employees,
            'allowed_roles': list(project.allowed_roles.all()),
            'role_issues': role_issues,
        })
    context = admin_context('crud_projects')
    context.update({
        'rows': enriched,
        'statuses': [x[0] for x in Project.STATUS_CHOICES],
        'owners': Project.objects.order_by('owner').values_list('owner', flat=True).distinct(),
        'selected_status': status,
        'selected_owner': owner,
        'q': q,
        'kpis': {
            'projects': len(enriched),
            'active': active,
            'at_risk': at_risk,
            'blocked': blocked,
            'assigned': total_assigned,
            'rules': total_rules,
        },
        'meta': crud_meta('Projects', 'Manage project info, eligibility, required skills, and staffing constraints.', reverse('project_create'), 'Search projects...')
    })
    return render(request, 'planner/crud/project_list.html', context)


@login_required
def project_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = Project.objects.filter(pk=pk).first()
    form = ProjectForm(request.POST or None, instance=instance)
    req_formset = ProjectRequiredSkillFormSet(request.POST or None, instance=instance, prefix='req')
    role_formset = ProjectRoleConstraintFormSet(request.POST or None, instance=instance, prefix='role')
    shift_formset = ProjectShiftConstraintFormSet(request.POST or None, instance=instance, prefix='shift')
    building_formset = ProjectBuildingConstraintFormSet(request.POST or None, instance=instance, prefix='building')
    if request.method == 'POST' and form.is_valid() and req_formset.is_valid() and role_formset.is_valid() and shift_formset.is_valid() and building_formset.is_valid():
        obj = form.save()
        for fs in [req_formset, role_formset, shift_formset, building_formset]:
            fs.instance = obj
            fs.save()
        messages.success(request, f'Project {obj.name} saved.')
        return redirect('crud_projects')
    context = admin_context('crud_projects')
    context.update({
        'form': form,
        'object': instance,
        'req_formset': req_formset,
        'role_formset': role_formset,
        'shift_formset': shift_formset,
        'building_formset': building_formset,
        'meta': crud_meta('Project Form', 'Create or update project info, eligibility, skills, and constraints.'),
    })
    return render(request, 'planner/crud/project_form.html', context)


@login_required
def project_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        name = obj.name
        obj.delete()
        messages.success(request, f'Project {name} deleted.')
        return redirect('crud_projects')
    context = admin_context('crud_projects')
    context.update({'object': obj, 'cancel_url': reverse('crud_projects'), 'title': 'Delete project'})
    return render(request, 'planner/crud/confirm_delete.html', context)


@login_required
def crud_evaluations(request):
    if not admin_only(request):
        return redirect('dashboard')
    rows = Evaluation.objects.select_related('employee', 'employee__role', 'project').prefetch_related('results')
    employee = request.GET.get('employee', '')
    role = request.GET.get('role', '')
    project = request.GET.get('project', '')
    level = request.GET.get('level', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if employee:
        rows = rows.filter(employee_id=employee)
    if role:
        rows = rows.filter(employee__role_id=role)
    if project == '__general__':
        rows = rows.filter(project__isnull=True)
    elif project:
        rows = rows.filter(project_id=project)
    if date_from:
        rows = rows.filter(date__gte=date_from)
    if date_to:
        rows = rows.filter(date__lte=date_to)
    rows, q = list_filter(request, rows, ['code', 'employee__code', 'employee__name', 'employee__role__name', 'evaluator', 'action_plan', 'project__name'])
    enriched = []
    band_counts = {'Over Qualified': 0, 'Qualified': 0, 'Needs Improvement': 0, 'Not Qualified': 0}
    recent_count = 0
    total_score = 0.0
    from django.utils import timezone
    cutoff = timezone.now().date() - timezone.timedelta(days=30)
    for row in rows.order_by('-date', 'code'):
        score = evaluation_score(row)
        emp_role = row.employee.role
        if score >= emp_role.over_threshold:
            row_level = 'Over Qualified'
        elif score >= emp_role.qualified_threshold:
            row_level = 'Qualified'
        elif score >= emp_role.improve_threshold:
            row_level = 'Needs Improvement'
        else:
            row_level = 'Not Qualified'
        if level and row_level != level:
            continue
        below_count = 0
        for rr in row.results.select_related('skill').all():
            rs = RoleSkill.objects.filter(role=row.employee.role, skill=rr.skill).first()
            threshold = float(rs.effective_min_value() if rs else rr.skill.min_value)
            compare_value = 1.0 if rr.skill.scoring_type == 'Pass/Fail checklist' and rr.status == 'Pass' else float(rr.value or 0)
            if compare_value < threshold:
                below_count += 1
        if row.date >= cutoff:
            recent_count += 1
        band_counts[row_level] += 1
        total_score += score
        enriched.append({'obj': row, 'score': score, 'level': row_level, 'below_count': below_count})
    avg_score = round(total_score / len(enriched), 2) if enriched else 0
    context = admin_context('crud_evaluations')
    context.update({
        'rows': enriched,
        'employees': Employee.objects.select_related('role').all(),
        'roles': RoleProfile.objects.all(),
        'projects': Project.objects.all(),
        'selected_employee': employee,
        'selected_role': role,
        'selected_project': project,
        'selected_level': level,
        'date_from': date_from,
        'date_to': date_to,
        'q': q,
        'kpis': {
            'total': len(enriched),
            'avg_score': avg_score,
            'needs_improvement': band_counts['Needs Improvement'] + band_counts['Not Qualified'],
            'over_qualified': band_counts['Over Qualified'],
            'recent': recent_count,
        },
        'meta': crud_meta('Evaluations', 'Manage general and project-linked evaluations with compact drilldown and actions.', reverse('evaluation_create'), 'Search evaluations...')
    })
    return render(request, 'planner/crud/evaluation_list.html', context)


@login_required
def evaluation_create(request, pk=None):
    if not admin_only(request):
        return redirect('dashboard')
    instance = Evaluation.objects.filter(pk=pk).first()
    clone_from = request.GET.get('clone')
    if not instance and clone_from:
        source = get_object_or_404(Evaluation.objects.prefetch_related('results').select_related('employee', 'project'), pk=clone_from)
        instance = Evaluation(
            employee=source.employee,
            project=source.project,
            evaluator=source.evaluator,
            date=source.date,
            strengths=source.strengths,
            weaknesses=source.weaknesses,
            action_plan=source.action_plan,
            code=f"{source.code}-COPY",
        )
    form = EvaluationForm(request.POST or None, instance=instance)
    result_formset = EvaluationResultFormSet(request.POST or None, instance=instance, prefix='results')
    if request.method == 'POST' and form.is_valid() and result_formset.is_valid():
        obj = form.save()
        result_formset.instance = obj
        result_formset.save()
        messages.success(request, f'Evaluation {obj.code} saved.')
        return redirect('crud_evaluations')

    role_skills = {}
    for rs in RoleSkill.objects.select_related('role', 'skill').all():
        role_skills.setdefault(rs.role_id, []).append({
            'skill_id': rs.skill_id,
            'skill_name': rs.skill.name,
            'pillar': rs.skill.pillar,
            'weight': float(rs.effective_weight()),
            'min_value': float(rs.effective_min_value()),
            'scoring_type': rs.skill.scoring_type,
        })
    employee_role_map = {emp.id: emp.role_id for emp in Employee.objects.select_related('role').all()}
    latest_map = {}
    for emp in Employee.objects.prefetch_related('evaluations__results__skill').all():
        latest = latest_evaluation(emp)
        if latest:
            latest_map[emp.id] = [
                {'skill_id': r.skill_id, 'skill_name': r.skill.name, 'value': float(r.value), 'status': r.status, 'notes': r.notes}
                for r in latest.results.select_related('skill').all()
            ]
    context = admin_context('crud_evaluations')
    context.update({
        'form': form, 'result_formset': result_formset, 'object': instance,
        'meta': crud_meta('Evaluation Form', 'Create or update a general evaluation or link it to a project. Load skills by employee role and optionally clone the latest evaluation.'),
        'role_skills_json': json.dumps(role_skills),
        'employee_role_map_json': json.dumps(employee_role_map),
        'latest_map_json': json.dumps(latest_map),
    })
    return render(request, 'planner/crud/evaluation_form.html', context)




@login_required
def evaluation_clone(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    return redirect(f"{reverse('evaluation_create')}?clone={pk}")

@login_required
def evaluation_delete(request, pk):
    if not admin_only(request):
        return redirect('dashboard')
    obj = get_object_or_404(Evaluation, pk=pk)
    if request.method == 'POST':
        code = obj.code
        obj.delete()
        messages.success(request, f'Evaluation {code} deleted.')
        return redirect('crud_evaluations')
    context = admin_context('crud_evaluations')
    context.update({'object': obj, 'cancel_url': reverse('crud_evaluations'), 'title': 'Delete evaluation'})
    return render(request, 'planner/crud/confirm_delete.html', context)
