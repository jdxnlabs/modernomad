import graphene
from graphene import ObjectType
from graphene_django.filter.fields import DjangoFilterConnectionField
from graphene_django.types import DjangoObjectType

from gather.models import Event


class EventNode(DjangoObjectType):
    url = graphene.String()

    class Meta:
        model = Event
        filter_fields = ["slug", "title"]

    def resolve_url(self, info, **kwargs):
        return (
            "/locations/"
            + self.location.slug
            + "/events/"
            + str(self.id)
            + "/"
            + self.slug
            + "/"
        )


class Query(ObjectType):
    # event = relay.NodeField(EventNode)
    all_events = DjangoFilterConnectionField(EventNode)
