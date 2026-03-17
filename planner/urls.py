from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('team/', views.team, name='team'),
    path('employees/<str:code>/', views.employee_detail, name='employee_detail'),
    path('evaluations/<str:code>/', views.evaluation_detail, name='evaluation_detail'),
    path('matrix/', views.matrix, name='matrix'),
    path('projects/', views.projects, name='projects'),
    path('projects/<str:code>/', views.project_detail, name='project_detail'),
    path('projects/<str:code>/assign/', views.project_assign_employee, name='project_assign_employee'),
    path('projects/<str:code>/unassign/', views.project_unassign_employee, name='project_unassign_employee'),
    path('training/', views.training, name='training'),
    path('training/<str:code>/', views.training_detail, name='training_detail'),
    path('training/<str:code>/assign/', views.training_assign_employee, name='training_assign_employee'),
    path('training/<str:code>/unassign/', views.training_unassign_employee, name='training_unassign_employee'),
    path('training/<str:code>/bulk-assign/', views.training_bulk_assign, name='training_bulk_assign'),
    path('workforce/', views.workforce, name='workforce'),
    path('admin-portal/', views.admin_portal, name='admin_portal'),

    # CRUD UI
    path('admin-portal/roles/', views.crud_roles, name='crud_roles'),
    path('admin-portal/roles/create/', views.role_create, name='role_create'),
    path('admin-portal/roles/<int:pk>/edit/', views.role_create, name='role_edit'),
    path('admin-portal/roles/<int:pk>/delete/', views.role_delete, name='role_delete'),

    path('admin-portal/skills/', views.crud_skills, name='crud_skills'),
    path('admin-portal/skills/create/', views.skill_create, name='skill_create'),
    path('admin-portal/skills/<int:pk>/edit/', views.skill_create, name='skill_edit'),
    path('admin-portal/skills/<int:pk>/delete/', views.skill_delete, name='skill_delete'),

    path('admin-portal/role-skills/', views.crud_role_skills, name='crud_role_skills'),
    path('admin-portal/role-skills/create/', views.role_skill_create, name='role_skill_create'),
    path('admin-portal/role-skills/<int:pk>/edit/', views.role_skill_create, name='role_skill_edit'),
    path('admin-portal/role-skills/<int:pk>/delete/', views.role_skill_delete, name='role_skill_delete'),

    path('admin-portal/employees/', views.crud_employees, name='crud_employees'),
    path('admin-portal/employees/create/', views.employee_create, name='employee_create'),
    path('admin-portal/employees/<int:pk>/edit/', views.employee_create, name='employee_edit'),
    path('admin-portal/employees/<int:pk>/delete/', views.employee_delete, name='employee_delete'),

    path('admin-portal/trainings/', views.crud_trainings, name='crud_trainings'),
    path('admin-portal/trainings/create/', views.training_create, name='training_create'),
    path('admin-portal/trainings/<int:pk>/edit/', views.training_create, name='training_edit'),
    path('admin-portal/trainings/<int:pk>/delete/', views.training_delete, name='training_delete'),

    path('admin-portal/projects/', views.crud_projects, name='crud_projects'),
    path('admin-portal/projects/create/', views.project_create, name='project_create'),
    path('admin-portal/projects/<int:pk>/edit/', views.project_create, name='project_edit'),
    path('admin-portal/projects/<int:pk>/delete/', views.project_delete, name='project_delete'),

    path('admin-portal/evaluations/', views.crud_evaluations, name='crud_evaluations'),
    path('admin-portal/evaluations/create/', views.evaluation_create, name='evaluation_create'),
    path('admin-portal/evaluations/<int:pk>/edit/', views.evaluation_create, name='evaluation_edit'),
    path('admin-portal/evaluations/<int:pk>/clone/', views.evaluation_clone, name='evaluation_clone'),
    path('admin-portal/evaluations/<int:pk>/delete/', views.evaluation_delete, name='evaluation_delete'),
]
