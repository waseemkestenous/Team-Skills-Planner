from django.contrib import admin
from .models import *

class RoleSkillInline(admin.TabularInline):
    model = RoleSkill
    extra = 0

@admin.register(RoleProfile)
class RoleProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'over_threshold', 'qualified_threshold', 'improve_threshold')
    inlines = [RoleSkillInline]

class ProjectRequiredSkillInline(admin.TabularInline):
    model = ProjectRequiredSkill
    extra = 0

class ProjectRoleConstraintInline(admin.TabularInline):
    model = ProjectRoleConstraint
    extra = 0

class ProjectShiftConstraintInline(admin.TabularInline):
    model = ProjectShiftConstraint
    extra = 0

class ProjectBuildingConstraintInline(admin.TabularInline):
    model = ProjectBuildingConstraint
    extra = 0

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'owner', 'status', 'start_date', 'end_date')
    filter_horizontal = ('allowed_roles',)
    inlines = [ProjectRequiredSkillInline, ProjectRoleConstraintInline, ProjectShiftConstraintInline, ProjectBuildingConstraintInline]

class EvaluationResultInline(admin.TabularInline):
    model = EvaluationResult
    extra = 0

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('code', 'employee', 'date', 'evaluator')
    inlines = [EvaluationResultInline]

admin.site.register(Skill)
admin.site.register(RoleSkill)
admin.site.register(Employee)
admin.site.register(Availability)
admin.site.register(Training)
