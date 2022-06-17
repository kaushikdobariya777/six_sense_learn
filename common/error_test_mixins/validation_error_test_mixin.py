from contextlib import contextmanager

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as RestValidationError


class ValidationErrorTestMixin(object):
    @contextmanager
    def assertValidationErrors(self, fields):
        """
        Assert that a validation error is raised, containing all the specified
        fields, and only the specified fields.
        """
        try:
            yield
            raise AssertionError("ValidationError not raised")
        except DjangoValidationError as e:
            self.assertEqual(set(fields), set(e.message_dict.keys()))
        except RestValidationError as e:
            self.assertEqual(set(fields), set(e.detail.keys()))
