from django.http import HttpResponse, HttpResponseNotFound
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser

from api.commands.capacities import *
from api.utils.http import JSONResponse
from core.data_fetchers import SerializedResourceCapacity
from core.models import CapacityChange, Resource
from core.serializers import CapacityChangeSerializer


@csrf_exempt
def capacities(request):
    """handles adding and updating capacities; deleting is handled by the
    capacity_detail method."""
    if request.method == "POST":
        data = JSONParser().parse(request)
        if not user_can_administer_a_resource(
            request.user, Resource.objects.get(id=data["resource"])
        ):
            return HttpResponseNotFound("404 not found")

        capacity = get_or_create_unsaved_capacity(data)
        errors, warnings = update_capacities_as_appropriate(capacity)

        capacities = SerializedResourceCapacity(
            capacity.resource, timezone.localtime(timezone.now())
        )
        command = CommandResult(capacities.as_dict(), errors, warnings)
        output = command.serialize()
        return JSONResponse(output, status=200)
    else:
        return HttpResponseNotFound("404 not found")


@csrf_exempt
def capacity_detail(request, capacity_id):
    try:
        capacity = CapacityChange.objects.get(pk=capacity_id)
    except CapacityChange.DoesNotExist:
        return HttpResponse(status=404)

    if request.method == "GET":
        serializer = CapacityChangeSerializer(capacity)
        return JSONResponse(serializer.data)

    elif request.method == "DELETE":
        command = DeleteCapacityChange(request.user, capacity=capacity)
        command.execute()
        return JSONResponse(
            command.result().serialize(), status=command.result().http_status()
        )
