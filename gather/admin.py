from django.contrib import admin

from gather.models import Event, EventAdminGroup, EventSeries


class EventAdmin(admin.ModelAdmin):
    model = Event


class EventAdminGroupAdmin(admin.ModelAdmin):
    model = EventAdminGroup


class EventSeriesAdmin(admin.ModelAdmin):
    model = EventSeries


admin.site.register(Event, EventAdmin)
admin.site.register(EventAdminGroup, EventAdminGroupAdmin)
admin.site.register(EventSeries, EventSeriesAdmin)
