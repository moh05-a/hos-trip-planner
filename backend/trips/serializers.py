from rest_framework import serializers


class LocationField(serializers.Field):
    """Either a free-text string or {"label", "lat", "lng", "short"}."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            if len(data.strip()) < 2:
                raise serializers.ValidationError("Please enter a location.")
            return data.strip()
        if isinstance(data, dict):
            if data.get("lat") is not None and data.get("lng") is not None:
                try:
                    lat, lng = float(data["lat"]), float(data["lng"])
                except (TypeError, ValueError):
                    raise serializers.ValidationError("Invalid coordinates.")
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    raise serializers.ValidationError("Coordinates out of range.")
                return {**data, "lat": lat, "lng": lng}
            if data.get("label"):
                return str(data["label"])
        raise serializers.ValidationError("Please enter a location.")

    def to_representation(self, value):
        return value


class TripRequestSerializer(serializers.Serializer):
    current_location = LocationField()
    pickup_location = LocationField()
    dropoff_location = LocationField()
    current_cycle_used = serializers.FloatField(min_value=0, max_value=70)
    start_time = serializers.DateTimeField(required=False, allow_null=True,
                                           input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "iso-8601"])

    def validate_start_time(self, value):
        # Logs use the home-terminal clock: drop any timezone info and keep wall time.
        return value.replace(tzinfo=None) if value else value
