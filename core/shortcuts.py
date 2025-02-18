from django.http import Http404
from django.shortcuts import _get_queryset


def get_qs_or_404(klass, *args, **kwargs):
    """
    Uses exists() to check whether the query exists, if it doesn't exist a
    Http404 exception is raised. Using a queryset instead of get allows you to
    use select_related to save queries.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the filter() query.
    """
    queryset = _get_queryset(klass)
    try:
        qs = queryset.filter(*args, **kwargs)
    except AttributeError as ex:
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            "First argument to get_object_or_404() must be a Model, Manager, "
            f"or QuerySet, not '{klass__name}'."
        ) from ex
    if not qs.exists():
        raise Http404(f"No {queryset.model._meta.object_name} matches the given query.")
    return qs
