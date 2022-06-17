from rest_framework.pagination import LimitOffsetPagination as DrfLimitOffsetPagination


class LimitOffsetPagination(DrfLimitOffsetPagination):
    get_all_records_param = "get_all_records"

    def get_all_records(self, request):
        return request.query_params.get(self.get_all_records_param, False)

    def paginate_queryset(self, queryset, request, view=None):
        if self.get_all_records(request):
            self.count = self.get_count(queryset)
            self.offset = 0
            self.limit = self.count
            return list(queryset.all())
        return super(LimitOffsetPagination, self).paginate_queryset(queryset, request, view)
