from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Skill, RoleProfile, Employee, Project, Training


def skills(request):
    data = list(Skill.objects.values())
    return JsonResponse(data, safe=False)


@csrf_exempt
def save_skill(request):
    body = json.loads(request.body)

    skill_id = body.get("id")

    if skill_id:
        skill = Skill.objects.get(id=skill_id)
    else:
        skill = Skill()

    skill.name = body.get("name")
    skill.save()

    return JsonResponse({"ok": True})