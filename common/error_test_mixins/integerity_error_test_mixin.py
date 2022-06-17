from contextlib import contextmanager

from django.db.utils import IntegrityError


class IntegrityErrorTestMixin(object):
    @contextmanager
    def asssertIntegrityErrors(self, fields):
        try:
            yield
            raise AssertionError("IntegrityError not raised")
        except IntegrityError as e:
            for field in fields:
                self.assertIn(field, e.__str__())
