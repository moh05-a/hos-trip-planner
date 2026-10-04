from django.http import JsonResponse
from django.urls import include, path


def root(_request):
    return JsonResponse({"service": "Spotter ELD trip planner API", "endpoints": [
        "GET /api/health/", "GET /api/geocode/?q=", "POST /api/plan-trip/"]})


urlpatterns = [
    path("", root),
    path("api/", include("trips.urls")),
]
