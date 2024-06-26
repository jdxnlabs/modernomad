import graphene
from django.contrib.auth.models import User
from graphene import Node, ObjectType
from graphene_django.filter.fields import DjangoFilterConnectionField
from graphene_django.types import DjangoObjectType

from core.models import UserProfile


class UserProfileNode(DjangoObjectType):
    class Meta:
        model = UserProfile
        interfaces = (Node,)


class UserNode(DjangoObjectType):
    name = graphene.String()
    url = graphene.String()

    class Meta:
        model = User
        interfaces = (Node,)
        filter_fields = ["id"]

    def resolve_name(self, info):
        return " ".join([self.first_name, self.last_name])

    def resolve_url(self, info):
        return "/people/" + self.username


class Query(ObjectType):
    all_users = DjangoFilterConnectionField(UserNode)
