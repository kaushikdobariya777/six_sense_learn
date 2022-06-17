from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django_tenants.utils import schema_context
from apps.user_auth.models import User
from apps.classif_ai.models import UseCase

from apps.organization.models import Organization, OrganizationDomain
from apps.packs.models import Pack
from apps.subscriptions.models import Subscription
from apps.users.models import SubOrganization


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("schema_name", type=str, nargs="?")
        parser.add_argument("tenant_code", type=str, nargs="?")
        parser.add_argument("domain", type=str, nargs="?")
        parser.add_argument("sub_org_name", type=str, nargs="?")
        parser.add_argument("pack_name", type=str, nargs="?")
        parser.add_argument("use_case_name", nargs="?")
        parser.add_argument("use_case_type", nargs="?")
        parser.add_argument("classification_type", nargs="?")
        parser.add_argument("email", nargs="?")
        parser.add_argument("password", nargs="?")
        parser.add_argument("--i", help="interactive", action="store_true")

    def handle(self, **options: Any) -> Optional[str]:
        if options["i"]:
            self.schema_name = input("Enter schema name: ")
            self.tenant_code = input("Enter tenant code: ")
            self.domain = input("Enter tenant domain url: ")
            self.sub_org_name = input("Enter sub org name: ")
            self.pack_name = input("Enter pack name: ")
            self.use_case_name = input("Enter use case name: ")
            self.use_case_type = input("Enter use case type: ")
            self.classification_type = input("Enter classification type: ")
            self.email = input("Enter email: ")
            self.password = input("Enter user password: ")
        else:
            self.schema_name = options["schema_name"]
            self.tenant_code = options["tenant_code"]
            self.domain = options["domain"]
            self.sub_org_name = options["sub_org_name"]
            self.pack_name = options["pack_name"]
            self.use_case_name = options["use_case_name"]
            self.use_case_type = options["use_case_type"]
            self.classification_type = options["classification_type"]
            self.email = input("Enter email: ")
            self.password = input("Enter user password: ")
        self.create_tenant()

    @transaction.atomic
    def create_tenant(self):
        with schema_context("public"):
            org = Organization.objects.create(
                schema_name=self.schema_name, name=self.schema_name, code=self.tenant_code
            )
            OrganizationDomain.objects.create(domain=self.domain, tenant=org)
        with schema_context(self.schema_name):
            sub_org = SubOrganization.objects.create(name=self.sub_org_name, code=self.sub_org_name.lower())
            pack = Pack.objects.create(name=self.pack_name)
            now = datetime.utcnow()
            expiry = now + relativedelta(years=1)
            sub = Subscription.objects.create(pack=pack, sub_organization=sub_org, starts_at=now, expires_at=expiry)
            UseCase.objects.create(
                name=self.use_case_name,
                type=self.use_case_type,
                subscription=sub,
                classification_type=self.classification_type,
            )
            user = User.objects.create(email=self.email, is_active=True)
            user.set_password(self.password)
            user.save()
