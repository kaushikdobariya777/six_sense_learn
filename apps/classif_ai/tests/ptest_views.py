import json
from datetime import datetime
from random import randrange
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
import pytz
from rest_framework import status

from apps.classif_ai.models import Defect, File, FileSet, UploadSession, MlModel, FileRegion, FileRegionHistory, MlModelDefect, UseCase
from apps.packs.models import Pack
from apps.subscriptions.models import Subscription
from apps.users.models import SubOrganization
from sixsense.tenant_test_case import SixsenseTenantTestCase


class FileSetTest(SixsenseTenantTestCase):

    def setUp(self):
        super().setUp()
        pack = Pack.objects.create(name='test-pack')
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org,
                       expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        UploadSession.objects.create(name='test-session', subscription=subscription)

    def test_file_set(self):

        upload_session = UploadSession.objects.first()
        subscription = Subscription.objects.first()

        json_body = {
            "upload_session": upload_session.id,
            "subscription": subscription.id,
            "files": [
                {
                    "name": "fd13.jpg"
                },
                {
                    "name": "fd14.jpg"
                },
                {
                    "name": "fd15.jpg"
                }
            ]
        }

        response = self.authorized_client.post(
            '/api/v1/classif-ai/file-set/',
            json.dumps(json_body),
            content_type='application/json',
        )

        # checking status code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # check if all File objects were created
        self.assertEqual(File.objects.count(), 3)

        # check if FileSet object was created
        self.assertEqual(FileSet.objects.count(), 1)

        # check if a path for the File object was created
        self.assertGreater(len(File.objects.first().path), 0)

    def test_file_set_delete(self):
        upload_session = UploadSession.objects.first()
        subscription = Subscription.objects.first()

        file_set = FileSet.objects.create(upload_session=upload_session, subscription=subscription)

        response = self.authorized_client.delete(
            f'/api/v1/classif-ai/file-set/{file_set.id}/',
            {},
            content_type='application/json',
        )

        # checking status code
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # check if FileSet was deleted
        self.assertFalse(FileSet.objects.filter(id=file_set.id).exists())


class UploadSessionTest(SixsenseTenantTestCase):

    def setUp(self):
        super().setUp()
        pack = Pack.objects.create(name='test-pack')
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())

    def test_upload_session(self):

        subscription = Subscription.objects.first()

        response = self.authorized_client.post(
            '/api/v1/classif-ai/upload-session',
            json.dumps({"name": "test-session", "subscription": subscription.id}),
            content_type='application/json'
        )

        # checking status code
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # check if UploadSession was created
        self.assertEqual(UploadSession.objects.count(), 1)

        upload_session = UploadSession.objects.first()

        FileSet.objects.create(upload_session_id=upload_session.id, subscription_id=subscription.id)

        response = self.authorized_client.get(
            f"/api/v1/classif-ai/upload-session/{upload_session.id}",
        )

        # checking status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # check if correct UploadSession is returned
        self.assertEqual(response.data['name'], 'test-session')

        # check if FileSet returned in response
        self.assertEqual(response.data['file_sets'], 1)


class MlModelTest(SixsenseTenantTestCase):

    def setUp(self):
        super().setUp()
        pack = Pack.objects.create(name='test-pack')
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        MlModel.objects.create(
            name='test-model-1', path='test-path-1', input_format={}, output_format={},
            code='test-code-1', version=1, status='Active', subscription=subscription
        )
        MlModel.objects.create(
            name='test-model-2', path='test-path-2', input_format={}, output_format={},
            code='test-code-2', version=2, status='Active', subscription=subscription
        )

    def test_ml_model(self):
        response = self.authorized_client.get("/api/v1/classif-ai/ml-model")
        # checking status code
        self.assertEqual(response.status_code, 200)

        # check number of objects returned
        self.assertEqual(response.data['count'], 2)

        # check if database has two objects
        self.assertEqual(MlModel.objects.count(), 2)

        # sending request to get a filtered response.
        response = self.authorized_client.get("/api/v1/classif-ai/ml-model?version=2")

        # checking status code
        self.assertEqual(response.status_code, 200)

        # checking if correct object is returned
        self.assertEqual(response.data['results'][0]['name'], 'test-model-2')


class FileRegionTest(SixsenseTenantTestCase):

    def setUp(self):
        super().setUp()
        pack = Pack.objects.create(name='test-pack')
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        usecase = UseCase.objects.create(name='test-usecase')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        fs = FileSet.objects.create(upload_session=upload_session, subscription=subscription)
        File.objects.create(file_set=fs, name='test-file')
        MlModel.objects.create(
            name='test-model-1', path='test-path-1', input_format={}, output_format={},
            code='test-code-1', version=1, status='Active', subscription=subscription,
            use_case=usecase
        )

    def test_file_region(self):

        file = File.objects.first()
        ml_model = MlModel.objects.first()
        json_body = {
            "file": file.id,
            "ml_model": ml_model.id,
            "defects": {
                "1": {
                    "confidence_score": 0.6
                },
                "2": {
                    "confidence_score": 0.8
                }
            },
            "region": {
                "coordinates": {
                    "x": 0.1,
                    "y": 0.2,
                    "h": 0.3,
                    "w": 0.4
                }
            },
            "is_user_feedback": False
        }

        response = self.authorized_client.post(
            "/api/v1/classif-ai/file-region/",
            json.dumps(json_body),
            content_type="application/json"
        )

        # checking status code
        self.assertEqual(response.status_code, 201)

        # checking if object was created
        self.assertEqual(FileRegion.objects.count(), 1)

        file_region = FileRegion.objects.first()

        json_body = {
            "file": file.id,
            "ml_model": ml_model.id,
            "defects": {
                "1": {
                    "confidence_score": 0.6
                },
                "2": {
                    "confidence_score": 0.8
                }
            },
            "region": {
                "coordinates": {
                    "x": 0.2,
                    "y": 0.9,
                    "h": 0.1,
                    "w": 0.6
                }
            },
            'ai_region': file_region.id,
            "is_user_feedback": True
        }

        response = self.authorized_client.post(
            "/api/v1/classif-ai/file-region/",
            json.dumps(json_body),
            content_type="application/json"
        )
        # checking status code
        self.assertEqual(response.status_code, 201)

        # checking if object was created
        self.assertEqual(FileRegion.objects.count(), 2)

        # check if FileRegionHistory object was created
        self.assertEqual(FileRegionHistory.objects.count(), 1)

        object_id = response.data['id']

        response = self.authorized_client.patch(
            f"/api/v1/classif-ai/file-region/{object_id}/",
            json.dumps({"defects": {"1": {"confidence_score": 1.0}}}),
            content_type="application/json"
        )

        # checking status code
        self.assertEqual(response.status_code, 200)

        # checking if object was patched successfully
        self.assertEqual(FileRegion.objects.get(id=object_id).defects['1']['confidence_score'], 1.0)

        # check if FileRegionHistory object was created
        self.assertEqual(FileRegionHistory.objects.count(), 2)


class DataPerformanceSummaryTest(SixsenseTenantTestCase):

    @classmethod
    def setUpTestData(cls):

        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        pack = Pack.objects.create(name='test-pack')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        defects = [Defect(), Defect(), Defect(), Defect(), Defect()]
        Defect.objects.bulk_create(defects)
        ml_model_1 = MlModel.objects.create(
            name='test-model-1', path='test-path-1', input_format={}, output_format={},
            code='test-code-1', version=1, status='Active', subscription=subscription
        )
        ml_model_2 = MlModel.objects.create(
            name='test-model-2', path='test-path-2', input_format={}, output_format={},
            code='test-code-2', version=1, status='Active', subscription=subscription
        )
        ml_model_3 = MlModel.objects.create(
            name='test-model-3', path='test-path-3', input_format={}, output_format={},
            code='test-code-3', version=1, status='Active', subscription=subscription
        )
        file_sets = [
            FileSet(upload_session=upload_session, subscription=subscription), FileSet(upload_session=upload_session, subscription=subscription),
            FileSet(upload_session=upload_session, subscription=subscription), FileSet(upload_session=upload_session, subscription=subscription)
        ]
        file_sets = FileSet.objects.bulk_create(file_sets)
        files = []
        for file_set in file_sets:
            file1 = File.objects.create(name='file-1', file_set=file_set)
            file2 = File.objects.create(name='file-2', file_set=file_set)
            files.append(file1)
            files.append(file2)
        for file in files:
            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_2, defects={'1': {}, '2': {}}, classification_correctness=False, is_removed=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_2, defects={'3':{}, '4': {}},
                ai_region=fr, classification_correctness=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_1, region={'coordinates': {'x': 0.9, 'y': 0.2, 'w': 0.3, 'h': 0.5}},
                detection_correctness=True
            )
            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, region={'coordinates': {'x': 0.2, 'y': 0.4, 'w': 0.1, 'h': 0.3}},
                detection_correctness=False, is_removed=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_1, ai_region=fr, region={'coordinates': {'x': 0.84, 'y': 0.4, 'w': 0.9, 'h': 0.2}},
                detection_correctness=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_3, region={'coordinates': {'x': 0.43, 'y': 0.25, 'w': 0.33, 'h': 0.12}},
                defects={'5': {}}, detection_correctness=True, classification_correctness=True
            )

    def test_performance_summary(self):
        subscription_id = Subscription.objects.first().id
        response = self.c.get(f"/api/v1/classif-ai/data-performance-summary?subscription_id={subscription_id}")
        print(response.data)


class UploadMetaInfoTest(SixsenseTenantTestCase):

    @classmethod
    def setUpTestData(cls):
        file_set_meta_info = [
                {'name': 'SerialNo', 'field': 'SerialNo', 'field_type': 'CharField', 'field_props': {'required': False, 'max_length': 256}},
                {'name': 'InitialTotal', 'field': 'InitialTotal', 'field_type': 'IntegerField', 'field_props': {'required': False}},
                {'name': 'Pass', 'field': 'Pass', 'field_type': 'IntegerField', 'field_props': {'required': False}},
                {'name': 'MachineNo', 'field': 'MachineNo', 'field_type': 'CharField', 'field_props': {'required': False, 'max_length': 256}}
            ]
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        pack = Pack.objects.create(name='test-pack')
        subscription = Subscription.objects.create(
                pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now(),
                file_set_meta_info=file_set_meta_info
            )
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        FileSet.objects.bulk_create(
                [FileSet(upload_session=upload_session, subscription=subscription),
                FileSet(upload_session=upload_session, subscription=subscription),
                FileSet(upload_session=upload_session, subscription=subscription),]
                )

    def test_upload_meta_info(self):
        upload_session_id = UploadSession.objects.first().id
        with open('84PPHX48X04_global.xml') as xml_file:
            response = self.c.patch(f"/api/v1/classif-ai/upload-meta-info", {'upload_session_id': upload_session_id, "file": xml_file})

        # checking status code
        self.assertEqual(response.status_code, 200)

        meta_info = FileSet.objects.first().meta_info

        # checking whether data was populated
        self.assertEqual(meta_info['SerialNo'], "5860131")
        self.assertEqual(meta_info['Pass'], "5422")


class DetailedReportTest(SixsenseTenantTestCase):

    @classmethod
    def setUpTestData(cls):

        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        pack = Pack.objects.create(name='test-pack')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        defects = [Defect(), Defect(), Defect(), Defect(), Defect()]
        defects = Defect.objects.bulk_create(defects)
        use_case_1 = UseCase.objects.create(name='test-code-1')
        use_case_2 = UseCase.objects.create(name='test-code-2')
        ml_model_1 = MlModel.objects.create(
            name='test-model-1', path='test-path-1', input_format={}, output_format={}, use_case=use_case_1,
            code='test-code-1', version=1, status='Active', subscription=subscription
        )
        ml_model_2 = MlModel.objects.create(
            name='test-model-2', path='test-path-2', input_format={}, output_format={}, use_case=use_case_2,
            code='test-code-1', version=2, status='Active', subscription=subscription
        )
        model_defects = [
                MlModelDefect(ml_model=ml_model_1, defect=defects[0]), MlModelDefect(ml_model=ml_model_1, defect=defects[1]),
                MlModelDefect(ml_model=ml_model_1, defect=defects[2]), MlModelDefect(ml_model=ml_model_2, defect=defects[3]),
                MlModelDefect(ml_model=ml_model_2, defect=defects[4])
        ]
        MlModelDefect.objects.bulk_create(model_defects)
        file_sets = [
            FileSet(upload_session=upload_session, subscription=subscription), FileSet(upload_session=upload_session, subscription=subscription),
            FileSet(upload_session=upload_session, subscription=subscription), FileSet(upload_session=upload_session, subscription=subscription)
        ]
        file_sets = FileSet.objects.bulk_create(file_sets)
        files = []
        for file_set in file_sets:
            file1 = File.objects.create(name='file-1', file_set=file_set)
            file2 = File.objects.create(name='file-2', file_set=file_set)
            files.append(file1)
            files.append(file2)
        for file in files:
            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'1': {}, '2': {}}, classification_correctness=False, is_removed=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'3':{}, '4': {}},
                ai_region=fr, classification_correctness=True
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'1':{}, '4': {}}, classification_correctness=True
            )
            FileRegion.objects.create(
                    file=file, ml_model=ml_model_1, defects={'2': {}, '3': {}}, classification_correctness=True
            )
            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_2, region={'coordinates': {'x': 0.43, 'y': 0.25, 'w': 0.33, 'h': 0.12}},
                defects={'5': {}}, detection_correctness=True, classification_correctness=False
            )
            FileRegion.objects.create(
                file=file, ml_model=ml_model_2, region={'coordinates': {'x': 0.43, 'y': 0.25, 'w': 0.33, 'h': 0.12}},
                defects={'3': {}}, detection_correctness=True, classification_correctness=True, ai_region=fr
            )

    def test_detailed_reports(self):
        ml_model_ids = MlModel.objects.all().values_list('id', flat=True)
        ml_model_string = ""
        for i, model_id in enumerate(sorted(ml_model_ids)):
            if i==len(ml_model_ids)-1:
                ml_model_string += str(model_id)
            else:
                ml_model_string += str(model_id) + ','
        response = self.c.get(f"/api/v1/classif-ai/detailed-report?ml_model_id__in={ml_model_string}")
        print(response.data)


class ApplicationChartTest(SixsenseTenantTestCase):

    def random_date(start, end):
        """
        This function will return a random datetime between two datetime
        objects.
        """
        delta = end - start
        int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
        random_second = randrange(int_delta)
        return start + timedelta(seconds=random_second)

    @classmethod
    def setUpTestData(cls):
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        pack = Pack.objects.create(name='test-pack')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        defects = [Defect(name='dark'), Defect(name='bent_lead'), Defect(name='frenkel'), Defect(name='schottky'), Defect(name='flake')]
        Defect.objects.bulk_create(defects)
        use_case = UseCase.objects.create(name='test-code-1')
        ml_model_1 = MlModel.objects.create(
            name='test-model-1', path='test-path-1', input_format={}, output_format={}, use_case=use_case,
            code='test-code-1', version=1, status='Active', subscription=subscription
        )
        meta_info_1 = {"Pass": '2442', "MachineNo": "KLA-108", "InitialTotal": '3131'}
        meta_info_2 = {"Pass": '2412', "MachineNo": "KLA-109", "InitialTotal": '3641'}
        meta_info_3 = {"Pass": '2456', "MachineNo": "KLA-110", "InitialTotal": '4069'}
        file_sets = [
            FileSet(upload_session=upload_session, subscription=subscription, meta_info=meta_info_1),
            FileSet(upload_session=upload_session, subscription=subscription, meta_info=meta_info_1),
            FileSet(upload_session=upload_session, subscription=subscription, meta_info=meta_info_2),
            FileSet(upload_session=upload_session, subscription=subscription, meta_info=meta_info_3)
        ]
        file_sets = FileSet.objects.bulk_create(file_sets)
        files = []
        for file_set in file_sets:
            file1 = File.objects.create(name='file-1', file_set=file_set)
            file2 = File.objects.create(name='file-2', file_set=file_set)
            files.append(file1)
            files.append(file2)
        for file in files:
            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'1': {}, '2': {}}, classification_correctness=False, is_removed=True,
            )
            fr.created_ts = datetime(year=2020, month=10, day=1, tzinfo=pytz.UTC)
            fr.save()

            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'5': {}, '2': {}}, classification_correctness=True,
            )
            fr.created_ts = datetime(year=2020, month=9, day=23, tzinfo=pytz.UTC)
            fr.save()

            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'1': {}, '3': {}}, classification_correctness=True,
            )
            fr.created_ts = datetime(year=2020, month=9, day=11, tzinfo=pytz.UTC)
            fr.save()

            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'4': {}, '1': {}}, classification_correctness=True,
            )
            fr.created_ts = datetime(year=2020, month=9, day=1, tzinfo=pytz.UTC)
            fr.save()

            fr = FileRegion.objects.create(
                file=file, ml_model=ml_model_1, defects={'2': {}, '5': {}}, classification_correctness=True,
            )
            fr.created_ts = datetime(year=2020, month=8, day=5, tzinfo=pytz.UTC)
            fr.save()

    def test_application_charts(self):
        defect_ids = Defect.objects.all().values_list('id', flat=True)
        defects_string = ""
        for i, defect_id in enumerate(sorted(defect_ids)):
            if i==len(defect_ids)-1:
                defects_string += str(defect_id)
            else:
                defects_string += str(defect_id) + ','

        response = self.c.get(f"/api/v1/classif-ai/application-charts?time_format=monthly&date__gte=2020-08-30&defect_id__in={defects_string}")

        # checking status code
        self.assertEqual(response.status_code, 200)

        # checking yield losses 
        self.assertAlmostEqual(response.data["yield_loss"]["KLA-108"], 77.99, delta=2)
        self.assertAlmostEqual(response.data["yield_loss"]["KLA-109"], 66.24, delta=2)
        self.assertAlmostEqual(response.data["yield_loss"]["KLA-110"], 60.35, delta=2)

        defect_v_count = response.data['defect_v_count']

        # checking number of elements
        self.assertEqual(len(defect_v_count), 5)

        print(response.data)
        # checking count values
        for defect in defect_v_count:
            counts = [count['count'] for count in defect['count_grouped_by_machine']]
            if defect['name'] == 'dark':
                self.assertEqual(counts, [6, 6, 12])
            elif defect['name'] == 'bent_lead':
                self.assertEqual(counts, [4, 4, 8])
            else:
                self.assertEquals(counts, [2, 2, 4])




class FileSetDistinctMetaInfoTest(SixsenseTenantTestCase):

    def setUp(self):
        super().setUp()
        sub_org = SubOrganization.objects.create(name='test-sub-org', code='test-code')
        pack = Pack.objects.create(name='test-pack')
        subscription = Subscription.objects.create(pack=pack, sub_organization=sub_org, expires_at=datetime(2020, 10, 20), starts_at=datetime.now())
        upload_session = UploadSession.objects.create(name='test-session', subscription=subscription)
        FileSet.objects.create(
            upload_session=upload_session, subscription=subscription,
            meta_info={"lot_id": "84PKWW23X05", "tray_id": "Tray021", "application": "Bottom SMI Burr RTR copy 5.bmp", "row_and_col_id": "R010C001"}
        )
        FileSet.objects.create(
            upload_session=upload_session, subscription=subscription,
            meta_info={"lot_id": "84PKWW23Y09", "tray_id": "Tray022", "application": "Bottom SMI Burr RTR copy 8.bmp", "row_and_col_id": "R010C003"}
        )
        FileSet.objects.create(
            upload_session=upload_session, subscription=subscription,
            meta_info={"lot_id": "84PKWW23Z10", "tray_id": "Tray023", "application": "Bottom SMI Burr RTR copy 15.bmp", "row_and_col_id": "R010C002"}
        )

    def test_distinct_meta_info(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set-meta-info/lot_id/distinct")

        # checking status code
        self.assertEqual(response.status_code, 200)

        # checking distinct info by comparing length
        self.assertEqual(len(response.data['data']), 3)


class UserMeTest(SixsenseTenantTestCase):

    def test_users_me(self):
        response = self.authorized_client.get("/api/v1/users/me/")

        # checking status code
        self.assertEqual(response.status_code, 200)

        # checking response body
        self.assertEqual(response.data['email'], "test@sixsense.ai")

        response = self.authorized_client.get("/api/v1/users/")

        # checking status code
        self.assertEqual(response.status_code, 403)
