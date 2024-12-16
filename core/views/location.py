import json
import logging

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView
from rules.contrib.views import PermissionRequiredMixin

from core.data_fetchers import (
    SerializedNullResourceCapacity,
    SerializedResourceCapacity,
)
from core.decorators import house_admin_required, resident_or_admin_required
from core.forms import (
    LocationContentForm,
    LocationPageForm,
    LocationRoomForm,
    LocationSettingsForm,
)
from core.models import (
    FlatPage,
    Location,
    LocationFlatPage,
    LocationMenu,
    Resource,
)
from core.views import view_helpers

logger = logging.getLogger(__name__)


def community(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    residents = location.residents()
    return render(
        request,
        "location_community.html",
        {"residents": residents, "location": location},
    )


def team(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    team = location.house_admins.all()
    return render(request, "location_team.html", {"team": team, "location": location})


def guests(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    guests_today = location.guests_today()
    return render(
        request, "location_guests.html", {"guests": guests_today, "location": location}
    )


class LocationDetail(PermissionRequiredMixin, DetailView):
    model = Location
    context_object_name = "location"
    template_name = "location/location_detail.html"
    permission_required = "location.can_view"
    slug_url_kwarg = "location_slug"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.prefetch_related("house_admins", "resources")
        return qs

    def handle_no_permission(self):
        raise Http404(
            "The location does not exist or you do not have permission to view it"
        )

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            if not request.user.is_authenticated:
                return HttpResponseRedirect("/membership/")
            if (not view_helpers.has_active_membership(request.user)) and settings.REQUIRE_MEMBERSHIP_ON_ACCOUNT_CREATION:
                return HttpResponseRedirect("/membership/")
        return super().dispatch(request, *args, **kwargs)


@house_admin_required
def LocationEditSettings(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    if request.method == "POST":
        form = LocationSettingsForm(request.POST, instance=location)
        if form.is_valid():
            form.save()
            messages.info(request, "Location Updated.")
    else:
        form = LocationSettingsForm(instance=location)
    return render(
        request,
        "location_edit_settings.html",
        {"page": "settings", "location": location, "form": form},
    )


@house_admin_required
def LocationEditUsers(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    if request.method == "POST":
        admin_user = event_admin_user = readonly_admin_user = None
        if "admin_username" in request.POST:
            admin_username = request.POST.get("admin_username")
            admin_user = User.objects.filter(username=admin_username).first()
        elif "readonly_admin_username" in request.POST:
            readonly_admin_username = request.POST.get("readonly_admin_username")
            readonly_admin_user = User.objects.filter(
                username=readonly_admin_username
            ).first()
        elif "event_admin_username" in request.POST:
            event_admin_username = request.POST.get("event_admin_username")
            event_admin_user = User.objects.filter(
                username=event_admin_username
            ).first()

        if admin_user:
            action = request.POST.get("action")
            if action == "Remove":
                # Remove user
                location.house_admins.remove(admin_user)
                location.save()
                messages.info(
                    request,
                    f"User '{admin_username}' removed from house admin group.",
                )
            elif action == "Add":
                # Add user
                location.house_admins.add(admin_user)
                location.save()
                messages.info(
                    request,
                    f"User '{admin_username}' added to house admin group.",
                )
        elif readonly_admin_user:
            action = request.POST.get("action")
            if action == "Remove":
                # Remove user
                location.readonly_admins.remove(readonly_admin_user)
                location.save()
                messages.info(
                    request,
                    f"User '{readonly_admin_username}' removed from readonly admin group.",
                )
            elif action == "Add":
                # Add user
                location.readonly_admins.add(readonly_admin_user)
                location.save()
                messages.info(
                    request,
                    f"User '{readonly_admin_username}' added to readonly admin group.",
                )
        elif event_admin_user:
            action = request.POST.get("action")
            if action == "Remove":
                # Remove user
                event_admin_group = location.event_admin_group
                event_admin_group.users.remove(event_admin_user)
                event_admin_group.save()
                messages.info(
                    request,
                    f"User '{event_admin_username}' removed from event admin group.",
                )
            elif action == "Add":
                # Add user
                event_admin_group = location.event_admin_group
                event_admin_group.users.add(event_admin_user)
                event_admin_group.save()
                messages.info(
                    request,
                    f"User '{event_admin_username}' added to event admin group.",
                )
        else:
            messages.error(request, "Username Required!")
    all_users = User.objects.all().order_by("username")
    return render(
        request,
        "location_edit_users.html",
        {"page": "users", "location": location, "all_users": all_users},
    )


@house_admin_required
def LocationEditPages(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)

    if request.method == "POST":
        action = request.POST["action"]
        logger.debug(f"action={action}")
        logger.debug(request.POST)
        if action == "Add Menu":
            try:
                menu = request.POST["menu"].strip().title()
                if (
                    menu
                    and not LocationMenu.objects.filter(
                        location=location, name=menu
                    ).count()
                    > 0
                ):
                    LocationMenu.objects.create(location=location, name=menu)
            except Exception as e:
                messages.error(request, f"Could not create menu: {e}")
        elif action == "Delete Menu" and "menu_id" in request.POST:
            try:
                menu = LocationMenu.objects.get(pk=request.POST["menu_id"])
                menu.delete()
            except Exception as e:
                messages.error(request, f"Could not delete menu: {e}")
        elif action == "Save Changes" and "page_id" in request.POST:
            try:
                page = LocationFlatPage.objects.get(pk=request.POST["page_id"])
                menu = LocationMenu.objects.get(pk=request.POST["menu"])
                page.menu = menu
                page.save()

                url_slug = request.POST["slug"].strip().lower()
                page.flatpage.url = f"/locations/{location.slug}/{url_slug}/"
                page.flatpage.title = request.POST["title"]
                page.flatpage.content = request.POST["content"]
                page.flatpage.save()
                messages.info(request, "The page was updated.")
            except Exception as e:
                messages.error(request, f"Could not edit page: {e}")
        elif action == "Delete Page" and "page_id" in request.POST:
            logger.debug("in Delete Page")
            try:
                page = LocationFlatPage.objects.get(pk=request.POST["page_id"])
                page.delete()
                messages.info(request, "The page was deleted")
            except Exception as e:
                messages.error(request, f"Could not delete page: {e}")
        elif action == "Create Page":
            try:
                menu = LocationMenu.objects.get(pk=request.POST["menu"])
                url_slug = request.POST["slug"].strip().lower()
                url = f"/locations/{location.slug}/{url_slug}/"
                if not url_slug or FlatPage.objects.filter(url=url).count() != 0:
                    raise Exception(f"Invalid slug ({url_slug})")
                flatpage = FlatPage.objects.create(
                    url=url,
                    title=request.POST["title"],
                    content=request.POST["content"],
                )
                flatpage.sites.add(Site.objects.get_current())
                LocationFlatPage.objects.create(menu=menu, flatpage=flatpage)
            except Exception as e:
                messages.error(request, f"Could not edit page: {e}")

    menus = location.get_menus()
    new_page_form = LocationPageForm(location=location)

    page_forms = {}
    for page in LocationFlatPage.objects.filter(menu__location=location):
        form = LocationPageForm(
            location=location,
            initial={
                "menu": page.menu,
                "slug": page.slug,
                "title": page.title,
                "content": page.content,
            },
        )
        page_forms[page] = form

    return render(
        request,
        "location_edit_pages.html",
        {
            "page": "pages",
            "location": location,
            "menus": menus,
            "page_forms": page_forms,
            "new_page_form": new_page_form,
        },
    )


@house_admin_required
def LocationManageRooms(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    resources = location.resources.all().order_by("name")
    return render(
        request, "location_manage_rooms.html", {"rooms": resources, "page": "rooms"}
    )


@resident_or_admin_required
def LocationEditRoom(request, location_slug, room_id):
    """Edit an existing room."""
    location = get_object_or_404(Location, slug=location_slug)
    resources = location.resources.all().order_by("name")
    room = Resource.objects.get(pk=room_id)
    resource_capacity = SerializedResourceCapacity(
        room, timezone.localtime(timezone.now())
    )
    resource_capacity_as_dict = json.dumps(resource_capacity.as_dict())
    logger.debug("resource capacity")
    logger.debug(resource_capacity_as_dict)

    logger.debug(request.method)
    if request.method == "POST":
        form = LocationRoomForm(
            request.POST, request.FILES, instance=Resource.objects.get(id=room_id)
        )
        if form.is_valid():
            backer_ids = form.cleaned_data["change_backers"]
            new_backing_date = form.cleaned_data["new_backing_date"]
            backers = [User.objects.get(pk=i) for i in backer_ids]
            resource = form.save()
            messages.info(request, f"{resource.name} updated.")
            if backers and backers != form.instance.backers():
                if not new_backing_date:
                    messages.error(
                        request,
                        "You must supply both a backer and a date if you want to update the backing",
                    )
                else:
                    logger.debug("found both backer id and new date. updating backing")
                    resource.set_next_backing(backers, new_backing_date)
                    messages.info(request, "Backing was scheduled.")
            elif backers:
                messages.info(
                    request,
                    "The new room backers must be different from the current room backers",
                )
        else:
            messages.info(
                request,
                "There was an error in your form, please see below.",
            )

        if request.META["HTTP_REFERER"] and "people" in request.META["HTTP_REFERER"]:
            # return to the user page we came from
            return HttpResponseRedirect(request.META["HTTP_REFERER"])

    else:
        form = LocationRoomForm(instance=Resource.objects.get(id=room_id))

    return render(
        request,
        "location_edit_room.html",
        {
            "location": location,
            "form": form,
            "room_id": room_id,
            "rooms": resources,
            "room_capacity": resource_capacity_as_dict,
        },
    )


@resident_or_admin_required
def LocationNewRoom(request, location_slug):
    """Create a new room."""
    location = get_object_or_404(Location, slug=location_slug)
    resources = location.resources.all().order_by("name")

    if request.method == "POST":
        form = LocationRoomForm(request.POST, request.FILES)
        if form.is_valid():
            new_room = form.save(commit=False)
            new_room.location = location
            new_room.save()
            messages.info(request, f"{new_room.name} created.")
            return HttpResponseRedirect(
                reverse(
                    "location_edit_room",
                    args=(
                        location.slug,
                        new_room.id,
                    ),
                )
            )
    else:
        form = LocationRoomForm()
        resource_capacity = SerializedNullResourceCapacity()

    return render(
        request,
        "location_edit_room.html",
        {
            "location": location,
            "form": form,
            "rooms": resources,
            "room_capacity": resource_capacity,
        },
    )


def LocationEditContent(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    if request.method == "POST":
        form = LocationContentForm(request.POST, request.FILES, instance=location)
        if form.is_valid():
            form.save()
            messages.info(request, "Location Updated.")
    else:
        form = LocationContentForm(instance=location)
    return render(
        request,
        "location_edit_content.html",
        {"page": "content", "location": location, "form": form},
    )


@house_admin_required
def LocationEditEmails(request, location_slug):
    location = get_object_or_404(Location, slug=location_slug)
    form = LocationSettingsForm(instance=location)
    return render(
        request,
        "location_edit_settings.html",
        {"page": "emails", "location": location, "form": form},
    )


def location_list(request):
    locations = Location.objects.filter(visibility="public").order_by("name")
    return render(request, "location_list.html", {"locations": locations})
