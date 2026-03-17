from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from .models import (
    RoleProfile, Skill, RoleSkill, Training, Employee, Project,
    ProjectRequiredSkill, ProjectRoleConstraint, ProjectShiftConstraint,
    ProjectBuildingConstraint, Evaluation, EvaluationResult, Availability,
)


class BootstrapModelForm(forms.ModelForm):
    """Apply Bootstrap styles consistently."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.CheckboxSelectMultiple,)):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs['class'] = 'form-select'
                widget.attrs.setdefault('size', '8')
            elif isinstance(widget, (forms.Select, forms.DateInput, forms.DateTimeInput, forms.NumberInput, forms.TextInput, forms.EmailInput, forms.Textarea)):
                base = 'form-select' if isinstance(widget, forms.Select) else 'form-control'
                widget.attrs['class'] = base
            if isinstance(widget, forms.DateInput):
                widget.attrs.setdefault('type', 'date')


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


class RoleProfileForm(BootstrapModelForm):
    class Meta:
        model = RoleProfile
        fields = ['name', 'over_threshold', 'qualified_threshold', 'improve_threshold']


class SkillForm(BootstrapModelForm):
    class Meta:
        model = Skill
        fields = ['code', 'pillar', 'color', 'name', 'scoring_type', 'default_weight', 'min_value', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class RoleSkillForm(BootstrapModelForm):
    class Meta:
        model = RoleSkill
        fields = ['role', 'skill', 'weight_override', 'min_value_override']


class TrainingForm(BootstrapModelForm):
    class Meta:
        model = Training
        fields = ['code', 'title', 'training_type', 'owner', 'pass_score', 'duration', 'linked_skills']


class EmployeeForm(BootstrapModelForm):
    class Meta:
        model = Employee
        fields = ['code', 'name', 'email', 'shift', 'building', 'role', 'status', 'trainings', 'assigned_projects']


class AvailabilityForm(BootstrapModelForm):
    weekly_availability = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='JSON array, example: ["1st", "2nd"]')
    allowed_buildings = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='JSON array, example: ["B1", "B6"]')
    time_off = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='JSON array of objects')
    unavailable_ranges = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), help_text='JSON array of objects')

    class Meta:
        model = Availability
        fields = ['weekly_availability', 'allowed_buildings', 'max_concurrent_projects', 'time_off', 'unavailable_ranges']

    def _parse_json_text(self, field_name):
        import json
        raw = self.cleaned_data.get(field_name, '')
        if raw in ('', None):
            return []
        try:
            return json.loads(raw)
        except Exception as exc:
            raise forms.ValidationError(f'Invalid JSON for {field_name}: {exc}')

    def clean_weekly_availability(self):
        return self._parse_json_text('weekly_availability')

    def clean_allowed_buildings(self):
        return self._parse_json_text('allowed_buildings')

    def clean_time_off(self):
        return self._parse_json_text('time_off')

    def clean_unavailable_ranges(self):
        return self._parse_json_text('unavailable_ranges')

    def initial_from_instance(self):
        import json
        if self.instance and self.instance.pk:
            for field in ['weekly_availability', 'allowed_buildings', 'time_off', 'unavailable_ranges']:
                self.fields[field].initial = json.dumps(getattr(self.instance, field) or [], indent=2)


class ProjectForm(BootstrapModelForm):
    class Meta:
        model = Project
        fields = ['code', 'name', 'owner', 'status', 'start_date', 'end_date', 'allowed_roles']


class ProjectRequiredSkillForm(BootstrapModelForm):
    class Meta:
        model = ProjectRequiredSkill
        fields = ['skill', 'min_value']


class ProjectRoleConstraintForm(BootstrapModelForm):
    class Meta:
        model = ProjectRoleConstraint
        fields = ['role', 'min_required', 'max_allowed']


class ProjectShiftConstraintForm(BootstrapModelForm):
    class Meta:
        model = ProjectShiftConstraint
        fields = ['role', 'shift', 'min_required', 'max_allowed']


class ProjectBuildingConstraintForm(BootstrapModelForm):
    class Meta:
        model = ProjectBuildingConstraint
        fields = ['role', 'building', 'min_required', 'max_allowed']


class EvaluationForm(BootstrapModelForm):
    strengths_text = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='One item per line')
    weaknesses_text = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='One item per line')

    class Meta:
        model = Evaluation
        fields = ['code', 'employee', 'project', 'evaluator', 'date', 'action_plan']
        widgets = {'action_plan': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].required = False
        if self.instance and self.instance.pk:
            self.fields['strengths_text'].initial = '\n'.join(self.instance.strengths or [])
            self.fields['weaknesses_text'].initial = '\n'.join(self.instance.weaknesses or [])

    def clean(self):
        cleaned = super().clean()
        cleaned['strengths'] = [x.strip() for x in cleaned.get('strengths_text', '').splitlines() if x.strip()]
        cleaned['weaknesses'] = [x.strip() for x in cleaned.get('weaknesses_text', '').splitlines() if x.strip()]
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.strengths = self.cleaned_data.get('strengths', [])
        obj.weaknesses = self.cleaned_data.get('weaknesses', [])
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class EvaluationResultForm(BootstrapModelForm):
    class Meta:
        model = EvaluationResult
        fields = ['skill', 'value', 'status', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['value'].widget.attrs.setdefault('step', '0.01')


ProjectRequiredSkillFormSet = inlineformset_factory(
    Project, ProjectRequiredSkill, form=ProjectRequiredSkillForm, extra=1, can_delete=True
)
ProjectRoleConstraintFormSet = inlineformset_factory(
    Project, ProjectRoleConstraint, form=ProjectRoleConstraintForm, extra=1, can_delete=True
)
ProjectShiftConstraintFormSet = inlineformset_factory(
    Project, ProjectShiftConstraint, form=ProjectShiftConstraintForm, extra=1, can_delete=True
)
ProjectBuildingConstraintFormSet = inlineformset_factory(
    Project, ProjectBuildingConstraint, form=ProjectBuildingConstraintForm, extra=1, can_delete=True
)
EvaluationResultFormSet = inlineformset_factory(
    Evaluation, EvaluationResult, form=EvaluationResultForm, extra=1, can_delete=True
)
