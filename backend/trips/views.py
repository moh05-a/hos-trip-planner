import logging

from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from . import services
from .planner import plan_trip
from .serializers import TripRequestSerializer

log = logging.getLogger(__name__)


class GeocodeThrottle(AnonRateThrottle):
    rate = "90/min"


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@throttle_classes([GeocodeThrottle])
def geocode(request):
    q = request.query_params.get("q", "")
    try:
        return Response({"results": services.geocode(q)})
    except services.ServiceError as e:
        return Response({"results": [], "error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:  # pragma: no cover
        log.exception("geocode failed")
        return Response({"results": [], "error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
def plan(request):
    ser = TripRequestSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    try:
        result = plan_trip(d["current_location"], d["pickup_location"], d["dropoff_location"],
                           d["current_cycle_used"], d.get("start_time"))
    except services.ServiceError as e:
        return Response({"detail": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except ValueError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)
