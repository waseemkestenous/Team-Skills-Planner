from django.db import models
from django.contrib.auth.models import User


LEVEL_CHOICES = [
    ('Over Qualified', 'Over Qualified'),
    ('Qualified', 'Qualified'),
    ('Needs Improvement', 'Needs Improvement'),
    ('Not Qualified', 'Not Qualified'),
]


class RoleProfile(models.Model):
    name = models.CharField(max_length=100, unique=True)
    over_threshold = models.PositiveIntegerField(default=90)
    qualified_threshold = models.PositiveIntegerField(default=75)
    improve_threshold = models.PositiveIntegerField(default=60)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Skill(models.Model):
    SCORING_CHOICES = [
        ('Score out of 100', 'Score out of 100'),
        ('Scored rubric (1-5)', 'Scored rubric (1-5)'),
        ('Pass/Fail checklist', 'Pass/Fail checklist'),
    ]
    code = models.SlugField(max_length=120, unique=True)
    pillar = models.CharField(max_length=120)
    color = models.CharField(max_length=20, default='#2f69b3')
    name = models.CharField(max_length=255)
    scoring_type = models.CharField(max_length=50, choices=SCORING_CHOICES)
    default_weight = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    min_value = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    roles = models.ManyToManyField(RoleProfile, through='RoleSkill', related_name='skills')

    class Meta:
        ordering = ['pillar', 'name']

    def __str__(self):
        return self.name


class RoleSkill(models.Model):
    role = models.ForeignKey(RoleProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    weight_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    min_value_override = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = [('role', 'skill')]
        ordering = ['role__name', 'skill__pillar', 'skill__name']

    def effective_weight(self):
        return self.weight_override if self.weight_override is not None else self.skill.default_weight

    def effective_min_value(self):
        return self.min_value_override if self.min_value_override is not None else self.skill.min_value


class Training(models.Model):
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=255)
    training_type = models.CharField(max_length=80)
    owner = models.CharField(max_length=120)
    pass_score = models.PositiveIntegerField(default=70)
    duration = models.CharField(max_length=120, blank=True)
    linked_skills = models.ManyToManyField(Skill, related_name='trainings', blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.title}'


class Project(models.Model):
    STATUS_CHOICES = [('Active', 'Active'), ('At Risk', 'At Risk'), ('Blocked', 'Blocked'), ('Completed', 'Completed')]
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=255)
    owner = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    allowed_roles = models.ManyToManyField(RoleProfile, related_name='eligible_projects', blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ProjectRequiredSkill(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='required_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    min_value = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = [('project', 'skill')]
        ordering = ['project__code', 'skill__name']


class ProjectRoleConstraint(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='role_constraints')
    role = models.ForeignKey(RoleProfile, on_delete=models.CASCADE)
    min_required = models.PositiveIntegerField(default=0)
    max_allowed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('project', 'role')]


class ProjectShiftConstraint(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='shift_constraints')
    role = models.ForeignKey(RoleProfile, on_delete=models.CASCADE)
    shift = models.CharField(max_length=20)
    min_required = models.PositiveIntegerField(default=0)
    max_allowed = models.PositiveIntegerField(default=0)


class ProjectBuildingConstraint(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='building_constraints')
    role = models.ForeignKey(RoleProfile, on_delete=models.CASCADE)
    building = models.CharField(max_length=20)
    min_required = models.PositiveIntegerField(default=0)
    max_allowed = models.PositiveIntegerField(default=0)


class Employee(models.Model):
    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive')]
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    shift = models.CharField(max_length=20)
    building = models.CharField(max_length=20)
    role = models.ForeignKey(RoleProfile, on_delete=models.PROTECT, related_name='employees')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    trainings = models.ManyToManyField(Training, blank=True, related_name='employees')
    assigned_projects = models.ManyToManyField(Project, blank=True, related_name='assigned_employees')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class Availability(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='availability')
    weekly_availability = models.JSONField(default=list, blank=True)
    allowed_buildings = models.JSONField(default=list, blank=True)
    max_concurrent_projects = models.PositiveIntegerField(default=1)
    time_off = models.JSONField(default=list, blank=True)
    unavailable_ranges = models.JSONField(default=list, blank=True)


class Evaluation(models.Model):
    code = models.CharField(max_length=40, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.CharField(max_length=120)
    date = models.DateField()
    project = models.ForeignKey(Project, null=True, blank=True, on_delete=models.SET_NULL, related_name='evaluations')
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    action_plan = models.TextField(blank=True)

    class Meta:
        ordering = ['date', 'code']

    def __str__(self):
        return f'{self.code} - {self.employee.code}'

    @property
    def scope_label(self):
        return self.project.name if self.project_id else 'General'


class EvaluationResult(models.Model):
    STATUS_CHOICES = [('Pass', 'Pass'), ('Fail', 'Fail'), ('Meets Min', 'Meets Min'), ('Below Min', 'Below Min')]
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='results')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [('evaluation', 'skill')]
        ordering = ['skill__pillar', 'skill__name']
