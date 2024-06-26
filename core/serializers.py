import datetime as dt
from datetime import timedelta

import dateutil
from rest_framework import serializers

from core.models import CapacityChange, Fee, Location, Resource


class CapacityChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapacityChange
        fields = ("id", "start_date", "resource", "quantity", "accept_drft")


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"


class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = ("id", "description", "percentage", "paid_by_house")


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        exclude = ["location"]

    def to_representation(self, obj):
        representation = super().to_representation(obj)
        request = self.context["request"]
        try:
            params = request.query_params.dict()
        except AttributeError:
            # this is a django request and not a REST request
            params = request.GET.dict()

        try:
            arrive = params.get("arrive", dt.datetime.today())
            arrive = dateutil.parser(arrive).date
            depart = params.get("depart", arrive + timedelta(days=13))
            depart = dateutil.parser(depart).date
        except Exception:
            arrive = dt.date.today()
            depart = arrive + timedelta(days=13)

        availabilities = [
            {"date": date, "quantity": quantity}
            for (date, quantity) in obj.daily_availabilities_within(arrive, depart)
        ]
        representation["availabilities"] = availabilities
        representation["hasFutureDrftCapacity"] = obj.has_future_drft_capacity()
        representation["maxBookingDays"] = obj.location.max_booking_days
        return representation
