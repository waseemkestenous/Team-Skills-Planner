from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from planner.models import *
from datetime import date

class Command(BaseCommand):
    help = 'Seed demo data for Quanta planner'

    def handle(self, *args, **options):
        self.stdout.write('Resetting demo data...')
        EvaluationResult.objects.all().delete()
        Evaluation.objects.all().delete()
        Availability.objects.all().delete()
        Employee.objects.all().delete()
        ProjectBuildingConstraint.objects.all().delete()
        ProjectShiftConstraint.objects.all().delete()
        ProjectRoleConstraint.objects.all().delete()
        ProjectRequiredSkill.objects.all().delete()
        Project.objects.all().delete()
        Training.objects.all().delete()
        RoleSkill.objects.all().delete()
        Skill.objects.all().delete()
        RoleProfile.objects.all().delete()

        roles = {
            'Associate': RoleProfile.objects.create(name='Associate', over_threshold=90, qualified_threshold=75, improve_threshold=60),
            'Sr. Server Support Tech': RoleProfile.objects.create(name='Sr. Server Support Tech', over_threshold=92, qualified_threshold=78, improve_threshold=62),
            'Production Tech': RoleProfile.objects.create(name='Production Tech', over_threshold=90, qualified_threshold=76, improve_threshold=60),
            'Repair Tech': RoleProfile.objects.create(name='Repair Tech', over_threshold=90, qualified_threshold=75, improve_threshold=60),
            'Floor Lead': RoleProfile.objects.create(name='Floor Lead', over_threshold=94, qualified_threshold=82, improve_threshold=68),
            'Test Tech': RoleProfile.objects.create(name='Test Tech', over_threshold=90, qualified_threshold=74, improve_threshold=58),
        }

        skills = {}
        skill_rows = [
            ('gb300-arch','Technical Knowledge','#2f69b3','GB300 architecture & component identification','Score out of 100',9,50,'Core baseline knowledge'),
            ('linux-basic','Technical Knowledge','#2f69b3','Basic Linux commands','Score out of 100',7,40,'CLI navigation and process basics'),
            ('nvlink-topology','Technical Knowledge','#2f69b3','NVLink / NVSwitch topology','Score out of 100',7,40,'Tracing and topology basics'),
            ('firmware-bmc','Technical Knowledge','#2f69b3','Firmware & BMC fundamentals','Score out of 100',7,40,'OOB workflow and logs'),
            ('fault-isolation','Hands-On Skills & Diagnostics','#c46f3b','Fault isolation & structured troubleshooting','Scored rubric (1-5)',8,4,'Structured RCA flow'),
            ('gpu-diagnostics','Hands-On Skills & Diagnostics','#c46f3b','GPU / compute node diagnostics','Scored rubric (1-5)',7,4,'DGCM and error interpretation'),
            ('hardware-replacement','Hands-On Skills & Diagnostics','#c46f3b','Hardware replacement & cable management','Pass/Fail checklist',7,1,'Safe replacement and rebuild'),
            ('diagnostic-tools','Hands-On Skills & Diagnostics','#c46f3b','Diagnostic tools proficiency','Scored rubric (1-5)',6,3,'Correct command usage'),
            ('esd-compliance','Safety & Process','#678a54','ESD compliance','Pass/Fail checklist',11,1,'Zero tolerance'),
            ('sop-adherence','Safety & Process','#678a54','SOP / runbook adherence','Pass/Fail checklist',8,1,'Checklist adherence'),
            ('ticket-documentation','Safety & Process','#678a54','Ticket documentation & incident reporting','Score out of 100',4,20,'Documentation quality'),
            ('training-completion','Professional Growth','#7b56b3','Training completion','Pass/Fail checklist',4,1,'Training roadmap status'),
            ('knowledge-sharing','Professional Growth','#7b56b3','Knowledge sharing & mentoring','Scored rubric (1-5)',2,1,'KT and mentoring'),
            ('stakeholder-updates','Professional Growth','#7b56b3','Communication & stakeholder updates','Scored rubric (1-5)',2,1,'Clear updates'),
            ('adaptability','Professional Growth','#7b56b3','Adaptability & initiative','Scored rubric (1-5)',2,1,'Flexible under change'),
            ('feedback-application','Professional Growth','#7b56b3','Feedback receptiveness & applying coaching','Scored rubric (1-5)',2,1,'Follows coaching'),
            ('leadership-readiness','Professional Growth','#7b56b3','Leadership readiness & decision-making','Scored rubric (1-5)',1,1,'Lead potential'),
            ('career-pathing','Professional Growth','#7b56b3','Career pathing & goal setting','Scored rubric (1-5)',1,1,'Growth plan clarity'),
        ]
        for code, pillar, color, name, scoring, weight, minv, notes in skill_rows:
            skills[code] = Skill.objects.create(code=code, pillar=pillar, color=color, name=name, scoring_type=scoring, default_weight=weight, min_value=minv, notes=notes)

        role_skill_ids = {
            'Associate': ['linux-basic','ticket-documentation','sop-adherence','training-completion','stakeholder-updates'],
            'Sr. Server Support Tech': ['gb300-arch','linux-basic','nvlink-topology','firmware-bmc','fault-isolation','gpu-diagnostics','diagnostic-tools','ticket-documentation','sop-adherence','knowledge-sharing','leadership-readiness'],
            'Production Tech': ['gb300-arch','hardware-replacement','esd-compliance','sop-adherence','ticket-documentation','training-completion','adaptability'],
            'Repair Tech': ['firmware-bmc','fault-isolation','gpu-diagnostics','hardware-replacement','diagnostic-tools','esd-compliance','ticket-documentation'],
            'Floor Lead': ['gb300-arch','linux-basic','fault-isolation','gpu-diagnostics','sop-adherence','ticket-documentation','knowledge-sharing','stakeholder-updates','adaptability','feedback-application','leadership-readiness','career-pathing'],
            'Test Tech': ['linux-basic','firmware-bmc','diagnostic-tools','esd-compliance','sop-adherence','ticket-documentation','training-completion'],
        }
        for role_name, skill_ids in role_skill_ids.items():
            for skill_id in skill_ids:
                RoleSkill.objects.create(role=roles[role_name], skill=skills[skill_id])

        trainings = {
            'TR-001': Training.objects.create(code='TR-001', title='Linux Basics Bootcamp', training_type='Internal', owner='Training Manager', pass_score=70, duration='2 weeks'),
            'TR-002': Training.objects.create(code='TR-002', title='Advanced Diagnostics Lab', training_type='Internal', owner='Senior SME', pass_score=80, duration='3 weeks'),
            'TR-003': Training.objects.create(code='TR-003', title='Production Assembly & BMC Flow', training_type='Internal', owner='Infrastructure SME', pass_score=75, duration='1 week'),
            'TR-004': Training.objects.create(code='TR-004', title='Safety & SOP Recertification', training_type='Mandatory', owner='Safety Officer', pass_score=100, duration='1 day'),
        }
        trainings['TR-001'].linked_skills.set([skills['linux-basic'], skills['ticket-documentation']])
        trainings['TR-002'].linked_skills.set([skills['fault-isolation'], skills['gpu-diagnostics'], skills['diagnostic-tools']])
        trainings['TR-003'].linked_skills.set([skills['firmware-bmc'], skills['hardware-replacement']])
        trainings['TR-004'].linked_skills.set([skills['esd-compliance'], skills['sop-adherence'], skills['knowledge-sharing']])

        employees = {
            'EMP-001': Employee.objects.create(code='EMP-001', name='Belinda Brown', email='belinda@example.com', shift='3rd', building='B1', role=roles['Associate']),
            'EMP-002': Employee.objects.create(code='EMP-002', name='Henock Mekonen', email='henock@example.com', shift='3rd', building='B1', role=roles['Sr. Server Support Tech']),
            'EMP-003': Employee.objects.create(code='EMP-003', name='Jalen Donald', email='jalen@example.com', shift='3rd', building='B1', role=roles['Production Tech']),
            'EMP-004': Employee.objects.create(code='EMP-004', name='Amina Hassan', email='amina@example.com', shift='1st', building='B6', role=roles['Repair Tech']),
            'EMP-005': Employee.objects.create(code='EMP-005', name='Marcus Reed', email='marcus@example.com', shift='2nd', building='B6', role=roles['Floor Lead']),
            'EMP-006': Employee.objects.create(code='EMP-006', name='Sofia Nguyen', email='sofia@example.com', shift='1st', building='B1', role=roles['Test Tech']),
        }
        employees['EMP-001'].trainings.set([trainings['TR-001']])
        employees['EMP-002'].trainings.set([trainings['TR-001'], trainings['TR-002']])
        employees['EMP-003'].trainings.set([trainings['TR-003']])
        employees['EMP-004'].trainings.set([trainings['TR-002'], trainings['TR-003']])
        employees['EMP-005'].trainings.set([trainings['TR-002'], trainings['TR-004']])
        employees['EMP-006'].trainings.set([trainings['TR-004']])

        projects = {
            'PRJ-001': Project.objects.create(code='PRJ-001', name='Rack Deployment', owner='Operations', status='Active', start_date=date(2026,3,17), end_date=date(2026,3,31)),
            'PRJ-002': Project.objects.create(code='PRJ-002', name='Firmware Upgrade Wave', owner='Infrastructure', status='Active', start_date=date(2026,3,17), end_date=date(2026,3,31)),
            'PRJ-003': Project.objects.create(code='PRJ-003', name='Diagnostics Recovery Pod', owner='Reliability', status='At Risk', start_date=date(2026,3,20), end_date=date(2026,4,5)),
            'PRJ-004': Project.objects.create(code='PRJ-004', name='Safety Compliance Refresh', owner='Safety', status='Active', start_date=date(2026,3,17), end_date=date(2026,3,31)),
        }
        projects['PRJ-001'].allowed_roles.set([roles['Production Tech'], roles['Sr. Server Support Tech'], roles['Floor Lead']])
        projects['PRJ-002'].allowed_roles.set([roles['Sr. Server Support Tech'], roles['Repair Tech'], roles['Test Tech'], roles['Floor Lead']])
        projects['PRJ-003'].allowed_roles.set([roles['Repair Tech'], roles['Sr. Server Support Tech'], roles['Test Tech'], roles['Floor Lead']])
        projects['PRJ-004'].allowed_roles.set([roles['Associate'], roles['Production Tech'], roles['Repair Tech'], roles['Test Tech'], roles['Floor Lead']])

        prs = [
            ('PRJ-001','linux-basic',70),('PRJ-001','fault-isolation',4),('PRJ-001','sop-adherence',1),
            ('PRJ-002','firmware-bmc',70),('PRJ-002','ticket-documentation',80),('PRJ-002','sop-adherence',1),
            ('PRJ-003','gpu-diagnostics',4),('PRJ-003','diagnostic-tools',4),('PRJ-003','fault-isolation',4),
            ('PRJ-004','esd-compliance',1),('PRJ-004','sop-adherence',1),('PRJ-004','knowledge-sharing',3),
        ]
        for p, s, mv in prs:
            ProjectRequiredSkill.objects.create(project=projects[p], skill=skills[s], min_value=mv)

        for p, role, mn, mx in [
            ('PRJ-001','Floor Lead',1,1),('PRJ-001','Production Tech',2,4),('PRJ-001','Sr. Server Support Tech',1,2),
            ('PRJ-002','Floor Lead',1,1),('PRJ-002','Repair Tech',1,3),('PRJ-002','Test Tech',1,2),('PRJ-002','Sr. Server Support Tech',1,2),
            ('PRJ-003','Floor Lead',1,1),('PRJ-003','Repair Tech',2,4),('PRJ-003','Test Tech',1,2),
            ('PRJ-004','Floor Lead',1,1),('PRJ-004','Associate',1,3),('PRJ-004','Production Tech',1,2),
        ]:
            ProjectRoleConstraint.objects.create(project=projects[p], role=roles[role], min_required=mn, max_allowed=mx)

        for p, shift, role, mn, mx in [
            ('PRJ-001','1st','Production Tech',1,2),('PRJ-001','2nd','Production Tech',1,2),('PRJ-001','1st','Floor Lead',1,1),
            ('PRJ-002','1st','Repair Tech',1,2),('PRJ-002','3rd','Test Tech',1,1),
            ('PRJ-003','2nd','Repair Tech',1,2),('PRJ-003','3rd','Repair Tech',1,2),('PRJ-003','3rd','Floor Lead',1,1),
            ('PRJ-004','1st','Associate',1,2),('PRJ-004','2nd','Production Tech',1,1),
        ]:
            ProjectShiftConstraint.objects.create(project=projects[p], shift=shift, role=roles[role], min_required=mn, max_allowed=mx)

        for p, building, role, mn, mx in [
            ('PRJ-001','B1','Production Tech',1,2),('PRJ-001','B6','Production Tech',1,2),('PRJ-001','B1','Sr. Server Support Tech',1,1),
            ('PRJ-002','B1','Repair Tech',1,2),('PRJ-002','B6','Test Tech',1,1),
            ('PRJ-003','B1','Repair Tech',1,2),('PRJ-003','B6','Repair Tech',1,2),
            ('PRJ-004','B1','Associate',1,2),('PRJ-004','B6','Production Tech',1,1),
        ]:
            ProjectBuildingConstraint.objects.create(project=projects[p], building=building, role=roles[role], min_required=mn, max_allowed=mx)

        employees['EMP-001'].assigned_projects.set([projects['PRJ-001']])
        employees['EMP-002'].assigned_projects.set([projects['PRJ-001'], projects['PRJ-002']])
        employees['EMP-003'].assigned_projects.set([projects['PRJ-003']])
        employees['EMP-004'].assigned_projects.set([projects['PRJ-002']])
        employees['EMP-005'].assigned_projects.set([projects['PRJ-001'], projects['PRJ-004']])
        employees['EMP-006'].assigned_projects.set([projects['PRJ-004']])

        avail_rows = {
            'EMP-001': {'weekly_availability':['3rd'], 'allowed_buildings':['B1'], 'max_concurrent_projects':1, 'time_off':['2026-03-24','2026-03-25'], 'unavailable_ranges':[]},
            'EMP-002': {'weekly_availability':['3rd'], 'allowed_buildings':['B1','B6'], 'max_concurrent_projects':2, 'time_off':['2026-03-18'], 'unavailable_ranges':[]},
            'EMP-003': {'weekly_availability':['2nd','3rd'], 'allowed_buildings':['B1'], 'max_concurrent_projects':1, 'time_off':[], 'unavailable_ranges':[{'start':'2026-03-20','end':'2026-03-22','reason':'Training Bootcamp'}]},
            'EMP-004': {'weekly_availability':['1st'], 'allowed_buildings':['B6'], 'max_concurrent_projects':1, 'time_off':['2026-03-27'], 'unavailable_ranges':[]},
            'EMP-005': {'weekly_availability':['1st','2nd','3rd'], 'allowed_buildings':['B1','B6'], 'max_concurrent_projects':3, 'time_off':[], 'unavailable_ranges':[]},
            'EMP-006': {'weekly_availability':['1st'], 'allowed_buildings':['B1'], 'max_concurrent_projects':2, 'time_off':['2026-03-21'], 'unavailable_ranges':[]},
        }
        for code, data in avail_rows.items():
            Availability.objects.create(employee=employees[code], **data)

        eval_rows = [
            ('EV-001','EMP-001','2026-03-01','Marcus Reed',['Good SOP follow-through','Responsive to coaching'],['Needs stronger Linux basics','Still building confidence in documentation quality'],'Finish Linux basics track and complete two documented shadowing tasks.', [('linux-basic',58,'Below Min','Needs more hands-on repetition'),('ticket-documentation',72,'Meets Min','Basic documentation is acceptable'),('sop-adherence',1,'Pass','Follows SOP well'),('training-completion',1,'Pass','Required onboarding complete'),('stakeholder-updates',3,'Meets Min','Can provide concise updates')]),
            ('EV-002','EMP-002','2026-03-01','Marcus Reed',['Strong diagnostics','Reliable documentation','Can support peers'],['Could mentor more consistently'],'Assign as buddy in two onboarding rotations and stretch into incident ownership.', [('gb300-arch',88,'Meets Min','Strong platform understanding'),('linux-basic',92,'Meets Min','Excellent'),('nvlink-topology',83,'Meets Min','Strong topology tracing'),('firmware-bmc',86,'Meets Min','Confident'),('fault-isolation',5,'Meets Min','Leads complex RCA well'),('gpu-diagnostics',4,'Meets Min','Strong practical depth'),('diagnostic-tools',5,'Meets Min','Excellent tool usage'),('ticket-documentation',95,'Meets Min','High quality notes'),('sop-adherence',1,'Pass','Excellent adherence'),('knowledge-sharing',4,'Meets Min','Runs KT sessions'),('leadership-readiness',4,'Meets Min','Strong lead potential')]),
            ('EV-003','EMP-003','2026-03-01','Marcus Reed',['Safe hardware handling','Good adaptability'],['Needs more assembly speed and better documentation discipline'],'Pair with senior production tech for cable workflow and QA checklist practice.', [('gb300-arch',62,'Meets Min','Basic component understanding'),('hardware-replacement',1,'Pass','Safe hands-on work'),('esd-compliance',1,'Pass','No violations'),('sop-adherence',1,'Pass','Checklist usage is steady'),('ticket-documentation',61,'Meets Min','Needs more detail'),('training-completion',1,'Pass','Core training completed'),('adaptability',3,'Meets Min','Learns new steps reasonably well')]),
            ('EV-004','EMP-004','2026-03-02','Amina Hassan',['Strong repair discipline','Good firmware understanding'],['Needs deeper GPU failure pattern recognition'],'Add one advanced GPU diagnostics lab and two ticket review drills.', [('firmware-bmc',74,'Meets Min','Good firmware workflow'),('fault-isolation',4,'Meets Min','Structured approach'),('gpu-diagnostics',3,'Below Min','Still improving on edge cases'),('hardware-replacement',1,'Pass','Very safe and precise'),('diagnostic-tools',4,'Meets Min','Independent tool usage'),('esd-compliance',1,'Pass','Excellent'),('ticket-documentation',84,'Meets Min','Good repair notes')]),
            ('EV-005','EMP-005','2026-03-03','Operations Manager',['Strong leadership','Excellent incident communication'],['Can delegate more tactical work'],'Shift more tactical tasks to seniors and spend more time on coaching.', [('gb300-arch',90,'Meets Min','Excellent'),('linux-basic',90,'Meets Min','Strong technical depth'),('fault-isolation',5,'Meets Min','Excellent RCA coaching'),('gpu-diagnostics',4,'Meets Min','Strong enough for lead role'),('sop-adherence',1,'Pass','Excellent'),('ticket-documentation',94,'Meets Min','Very strong updates'),('knowledge-sharing',5,'Meets Min','Excellent mentor'),('stakeholder-updates',5,'Meets Min','Clear executive communication'),('adaptability',5,'Meets Min','Very strong initiative'),('feedback-application',5,'Meets Min','Excellent'),('leadership-readiness',5,'Meets Min','Operating at lead level'),('career-pathing',5,'Meets Min','Clear org-growth mindset')]),
            ('EV-006','EMP-006','2026-03-03','Operations Manager',['Excellent compliance habits','Reliable test process execution'],['Needs stronger firmware depth for ambiguous failures'],'Add one firmware troubleshooting lab and review 5 failed test tickets.', [('linux-basic',66,'Meets Min','Good enough for standard test flow'),('firmware-bmc',55,'Meets Min','Adequate but can improve'),('diagnostic-tools',3,'Meets Min','Can use standard commands'),('esd-compliance',1,'Pass','Excellent'),('sop-adherence',1,'Pass','Excellent'),('ticket-documentation',86,'Meets Min','Strong pass/fail notes'),('training-completion',1,'Pass','Required cert complete')]),
        ]
        for ev_code, emp_code, ev_date, evaluator, strengths, weaknesses, plan, results in eval_rows:
            ev = Evaluation.objects.create(code=ev_code, employee=employees[emp_code], date=ev_date, evaluator=evaluator, strengths=strengths, weaknesses=weaknesses, action_plan=plan)
            for skill_id, value, status, notes in results:
                EvaluationResult.objects.create(evaluation=ev, skill=skills[skill_id], value=value, status=status, notes=notes)

        demo_users = [
            ('admin','admin','System Admin', True, True),
            ('manager1','123456','Operations Manager', False, True),
            ('lead1','123456','Shift Lead', False, True),
            ('viewer1','123456','Read Only User', False, False),
        ]
        for username, pwd, first_name, is_super, is_staff in demo_users:
            user, _ = User.objects.get_or_create(username=username, defaults={'first_name': first_name, 'is_superuser': is_super, 'is_staff': True if is_super else is_staff})
            user.first_name = first_name
            user.is_superuser = is_super
            user.is_staff = True if is_super else is_staff
            user.set_password('123456' if username != 'admin' else 'admin')
            user.save()
        self.stdout.write(self.style.SUCCESS('Demo data seeded.'))
