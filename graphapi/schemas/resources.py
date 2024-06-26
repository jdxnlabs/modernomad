import logging
from datetime import timedelta

import graphene
from graphene import Node, ObjectType
from graphene.types.datetime import DateTime
from graphene_django.filter.fields import DjangoFilterConnectionField
from graphene_django.types import DjangoObjectType

from core.models import Backing, Resource

logger = logging.getLogger(__name__)


class AvailabilityNode(graphene.ObjectType):
    date = DateTime()
    quantity = graphene.Int()


class BackingNode(DjangoObjectType):
    class Meta:
        model = Backing
        interfaces = (Node,)


class ResourceNode(DjangoObjectType):
    rid = graphene.Int()
    availabilities = graphene.List(
        lambda: AvailabilityNode, arrive=DateTime(), depart=DateTime()
    )
    backing = graphene.Field(BackingNode)
    has_future_drft_capacity = graphene.Boolean()
    accept_drft_these_dates = graphene.Boolean(arrive=DateTime(), depart=DateTime())

    class Meta:
        model = Resource
        interfaces = (Node,)
        filter_fields = {
            "location": ["exact"],
            "location__slug": ["exact"],
        }

    def resolve_has_future_drft_capacity(self, info):
        return self.has_future_drft_capacity()

    def resolve_rid(self, info):
        return self.id

    def resolve_accept_drft_these_dates(self, info, arrive, depart):
        start_date = arrive.date()
        end_date = depart.date() - timedelta(days=1)

        logger.debug(f"{self.name} drftable between? ")
        logger.debug(self.drftable_between(start_date, end_date))
        return self.drftable_between(start_date, end_date)

    def resolve_availabilities(self, info, arrive, depart):
        start_date = arrive.date()
        end_date = depart.date() - timedelta(days=1)

        availabilities = self.daily_availabilities_within(start_date, end_date)

        return [AvailabilityNode(*availability) for availability in availabilities]


class Query(ObjectType):
    all_resources = DjangoFilterConnectionField(ResourceNode)
    all_drft_resources = DjangoFilterConnectionField(ResourceNode)

    def resolve_all_drft_resources(self, info):
        return Resource.objects.filter(hasFutureDrftCapacity=True)
