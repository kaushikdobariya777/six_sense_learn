from rest_framework.routers import Route, SimpleRouter, DynamicRoute


class ReadOnlyRouter(SimpleRouter):
    """
    A router for read-only APIs, which doesn't use trailing slashes.
    """

    routes = [
        Route(
            url=r"^{prefix}$",
            mapping={"get": "list"},
            name="{basename}-list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        Route(
            url=r"^{prefix}/{lookup}$",
            mapping={"get": "retrieve"},
            name="{basename}-detail",
            detail=True,
            initkwargs={"suffix": "Detail"},
        ),
        DynamicRoute(
            url=r"^{prefix}/{url_path}{trailing_slash}$", name="{basename}-{url_name}", detail=False, initkwargs={}
        ),
    ]


# ToDo: think of a better name?
class GETPOSTRouter(SimpleRouter):
    """
    A router which allows only GET and POST requests.
    """

    routes = [
        Route(
            url=r"^{prefix}$",
            mapping={"get": "list", "post": "create"},
            name="{basename}-list",
            detail=False,
            initkwargs={},
        ),
        Route(
            url=r"^{prefix}/{lookup}$",
            mapping={"get": "retrieve"},
            name="{basename}-detail",
            detail=True,
            initkwargs={},
        ),
        DynamicRoute(
            url=r"^{prefix}/{url_path}{trailing_slash}$", name="{basename}-{url_name}", detail=False, initkwargs={}
        ),
    ]
