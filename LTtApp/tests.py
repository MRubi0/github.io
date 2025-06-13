from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile # For file uploads in tests
import json # For POSTing JSON data
from django.conf import settings # For accessing settings

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import Tour, Paso, CustomUser, TourRelation, Valoracion, TourRecord
from .tasks import process_transcription_task, process_translation_task, process_synthesis_task
# Import views to test directly if needed, or use client for API views
# from .views import list_latest_tours_by_category, start_transcription_job_view # Not used directly

User = get_user_model()

class ModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='testuser@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        cls.tour = Tour.objects.create(
            user=cls.user,
            titulo='Test Tour Title',
            descripcion='Test tour description.',
            idioma='es',
            tipo_de_tour='cultural',
            latitude=10.0,
            longitude=20.0
        )
        cls.paso = Paso.objects.create(
            tour=cls.tour,
            step_number=1,
            tittle='Test Paso Title',
            description='Paso description'
        )
        cls.tour_record = TourRecord.objects.create(user=cls.user, tour=cls.tour)
        cls.valoracion = Valoracion.objects.create(user=cls.user, tour=cls.tour, puntuacion=5)


    def test_custom_user_str(self):
        self.assertEqual(str(self.user), 'testuser@example.com')

    def test_tour_str(self):
        self.assertEqual(str(self.tour), 'Test Tour Title')

    def test_paso_str(self):
        self.assertEqual(str(self.paso), "Paso 1 for Tour {} ('Test Paso Title')".format(self.tour.id))

    def test_tour_relation_str(self):
        tour2 = Tour.objects.create(user=self.user, titulo='Tour English', idioma='en')
        relation = TourRelation.objects.create(tour_es=self.tour, tour_en=tour2)
        self.assertEqual(str(relation), f"Relation: ES Tour ID {self.tour.id} - EN Tour ID {tour2.id}")

    def test_tour_record_str(self):
        self.assertTrue(self.tour.titulo in str(self.tour_record))


    def test_valoracion_str(self):
        self.assertTrue(self.user.email in str(self.valoracion))
        self.assertTrue(self.tour.titulo in str(self.valoracion))


    def test_tour_as_dict(self):
        # Ensure that the as_dict method includes the 'original' field.
        expected_original_value = self.tour.original  # Assuming 'original' field exists

        # Mock file fields if .url is accessed and storage is not default
        with patch.object(self.tour.imagen, 'url', MagicMock(return_value='http://example.com/image.jpg'), create=True):
            with patch.object(self.tour.audio, 'url', MagicMock(return_value='http://example.com/audio.mp3'), create=True):
                tour_dict = self.tour.as_dict()
                self.assertEqual(tour_dict['titulo'], 'Test Tour Title')
                self.assertEqual(tour_dict['user_id'], self.user.id)
                self.assertEqual(tour_dict['imagen_url'], 'http://example.com/image.jpg')
                self.assertEqual(tour_dict['audio_url'], 'http://example.com/audio.mp3')
                self.assertEqual(tour_dict['latitude'], 10.0)
                self.assertEqual(tour_dict['original'], expected_original_value)


    def test_paso_as_dict(self):
        with patch.object(self.paso.image, 'url', MagicMock(return_value='http://example.com/paso_image.jpg'), create=True):
             with patch.object(self.paso.audio, 'url', MagicMock(return_value='http://example.com/paso_audio.mp3'), create=True):
                paso_dict = self.paso.as_dict()
                self.assertEqual(paso_dict['title'], 'Test Paso Title')
                self.assertEqual(paso_dict['step_number'], 1)
                self.assertEqual(paso_dict['image_url'], 'http://example.com/paso_image.jpg')


class CeleryTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='taskuser@example.com', password='password')
        # Correctly simulate an audio file being associated with the tour for tasks
        cls.tour_es = Tour.objects.create(user=cls.user, titulo='Celery Spanish Tour', idioma='es')
        cls.tour_es.audio.name = 'test_audio/spanish_audio.mp3' # Simulate S3 path
        cls.tour_es.save()

        cls.tour_en = Tour.objects.create(user=cls.user, titulo='Celery English Tour', idioma='en', original=str(cls.tour_es.id))
        TourRelation.objects.create(tour_es=cls.tour_es, tour_en=cls.tour_en)

        cls.paso_es = Paso.objects.create(tour=cls.tour_es, step_number=1, tittle="Paso ES 1")
        cls.paso_es.audio.name = 'test_audio/paso1_es.mp3' # Simulate S3 path
        cls.paso_es.save()


    @patch('LTtApp.tasks.boto3.client')
    @patch('LTtApp.tasks.wait_for_transcription_job_completion')
    def test_process_transcription_task(self, mock_wait, mock_boto_client):
        mock_s3 = MagicMock()
        mock_transcribe = MagicMock()
        mock_boto_client.side_effect = lambda service_name, region_name=None: mock_transcribe if service_name == 'transcribe' else mock_s3
        mock_wait.return_value = {'TranscriptionJob': {'TranscriptionJobStatus': 'COMPLETED'}}

        process_transcription_task(self.tour_es.id)

        self.assertTrue(mock_transcribe.start_transcription_job.called)
        # Check call for main tour audio
        main_audio_call_args = mock_transcribe.start_transcription_job.call_args_list[0][1]
        self.assertTrue(main_audio_call_args['TranscriptionJobName'].startswith(f"spanish_audio_{self.user.id}_{self.tour_es.id}_main"))
        # Check call for paso audio
        paso_audio_call_args = mock_transcribe.start_transcription_job.call_args_list[1][1]
        self.assertTrue(paso_audio_call_args['TranscriptionJobName'].startswith(f"paso1_es_{self.user.id}_{self.tour_es.id}_step_1"))

    @patch('LTtApp.tasks.boto3.client')
    def test_process_translation_task(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_translate = MagicMock()
        mock_boto_client.side_effect = lambda service_name, region_name=None: mock_translate if service_name == 'translate' else mock_s3

        mock_s3.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b"Hola mundo"))}
        mock_translate.translate_text.return_value = {'TranslatedText': 'Hello world'}

        process_translation_task(self.tour_es.id, self.tour_en.id, 'es', 'en')

        mock_s3.get_object.assert_called_once()
        mock_translate.translate_text.assert_called_once_with(Text="Hola mundo", SourceLanguageCode='es', TargetLanguageCode='en')
        mock_s3.put_object.assert_called_once()


    @patch('LTtApp.tasks.boto3.client')
    def test_process_synthesis_task(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_polly = MagicMock()
        mock_boto_client.side_effect = lambda service_name, region_name=None: mock_polly if service_name == 'polly' else mock_s3

        mock_s3.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b"Hello world ######################################################################## Hello step"))}
        mock_polly.synthesize_speech.return_value = {'AudioStream': MagicMock(read=MagicMock(return_value=b"audio_data"))}

        Paso.objects.create(tour=self.tour_en, step_number=1, tittle="English Step 1")

        process_synthesis_task(self.tour_en.id)

        mock_s3.get_object.assert_called_once()
        self.assertTrue(mock_polly.synthesize_speech.called)
        # Check main tour audio synthesis
        self.assertEqual(mock_polly.synthesize_speech.call_args_list[0][1]['Text'], 'Hello world')
        # Check step audio synthesis
        self.assertEqual(mock_polly.synthesize_speech.call_args_list[1][1]['Text'], 'Hello step')
        self.assertTrue(mock_s3.put_object.called)
        self.assertEqual(mock_s3.put_object.call_count, 2) # Main audio + 1 step


class APIViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='apiuser@example.com', password='password123', first_name='API', last_name='User')
        cls.tour_es = Tour.objects.create(user=cls.user, titulo='Spanish Tour', idioma='es', tipo_de_tour='cultural', validado=True, created_at=timezone.now())
        cls.tour_en = Tour.objects.create(user=cls.user, titulo='English Tour', idioma='en', tipo_de_tour='cultural', validado=True, created_at=timezone.now())
        TourRelation.objects.create(tour_es=cls.tour_es, tour_en=cls.tour_en)
        Paso.objects.create(tour=cls.tour_es, step_number=1, tittle="Paso Uno")

    def setUp(self): # Renamed from setUpTestData as client needs to be fresh for each test
        self.client = APIClient()


    @patch('LTtApp.views.process_transcription_task.delay')
    def test_start_transcription_job_view_authenticated(self, mock_task_delay):
        self.client.force_authenticate(user=self.user)
        # Assuming 'start_transcription_job' is the correct URL name from urls.py
        url = reverse('start_transcription_job_view', kwargs={'tour_id': self.tour_es.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['message'], 'Transcription process started.')
        mock_task_delay.assert_called_once_with(self.tour_es.id)

    def test_start_transcription_job_view_unauthenticated(self):
        url = reverse('start_transcription_job_view', kwargs={'tour_id': self.tour_es.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) # Corrected from 403


    def test_list_latest_tours_by_category_success(self):
        url = reverse('list_latest_tours_by_category') + '?language=es'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        found_tour = False
        for tour_data in response.data:
            if tour_data['id'] == self.tour_es.id:
                found_tour = True
                self.assertEqual(tour_data['title'], self.tour_es.titulo)
                self.assertEqual(tour_data['tour_type'], self.tour_es.tipo_de_tour)
        self.assertTrue(found_tour, "Spanish tour not found in latest cultural tours for ES.")

    def test_crear_valoracion_unauthenticated(self):
        url = reverse('crear_valoracion')
        data = {'tour_id': self.tour_es.id, 'puntuacion': 5, 'comentario': 'Great!'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # AllowAny is set

    def test_crear_valoracion_authenticated(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('crear_valoracion')
        data = {'tour_id': self.tour_es.id, 'puntuacion': 4, 'comentario': 'Good tour!'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Valoracion.objects.filter(tour=self.tour_es, user=self.user, puntuacion=4).exists())

    def test_crear_valoracion_missing_data(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('crear_valoracion')
        data = {'tour_id': self.tour_es.id, 'comentario': 'No rating'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Faltan datos necesarios')


class DonationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='donor@example.com', password='password123')

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('create_checkout_session') # Assuming 'create_checkout_session' is the URL name

    def test_create_donation_unauthenticated(self):
        response = self.client.post(self.url, {'amount': 5000})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED) # Changed from 403 as per IsAuthenticated

    @patch('stripe.checkout.Session.create')
    def test_create_donation_success_authenticated(self, mock_stripe_session_create):
        self.client.force_authenticate(user=self.user)
        mock_stripe_session_create.return_value = MagicMock(id='cs_test_123')

        data = {'amount': 5000, 'description': 'Test Donation'} # Amount in cents
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Changed from 200
        self.assertEqual(response.data['id'], 'cs_test_123')

        mock_stripe_session_create.assert_called_once()
        called_args, called_kwargs = mock_stripe_session_create.call_args
        self.assertEqual(called_kwargs['customer_email'], self.user.email)
        self.assertEqual(called_kwargs['line_items'][0]['price_data']['unit_amount'], 5000)
        self.assertEqual(called_kwargs['metadata']['user_provided_description'], 'Test Donation')
        self.assertEqual(called_kwargs['metadata']['django_user_id'], str(self.user.id))
        self.assertEqual(called_kwargs['line_items'][0]['price_data']['product_data']['name'], "Donation to Let's Tour Tec")

    @patch('stripe.checkout.Session.create')
    def test_create_donation_no_description(self, mock_stripe_session_create):
        self.client.force_authenticate(user=self.user)
        mock_stripe_session_create.return_value = MagicMock(id='cs_test_456')

        data = {'amount': 3000} # Amount in cents
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['id'], 'cs_test_456')

        called_args, called_kwargs = mock_stripe_session_create.call_args
        self.assertNotIn('user_provided_description', called_kwargs['metadata'])
        self.assertEqual(called_kwargs['metadata']['django_user_id'], str(self.user.id))


    def test_create_donation_invalid_amount(self):
        self.client.force_authenticate(user=self.user)
        invalid_amounts = [-100, 0, 'not-a-number', 10.50]
        for amount in invalid_amounts:
            data = {'amount': amount, 'description': 'Invalid amount test'}
            response = self.client.post(self.url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, f"Failed for amount: {amount}")
            self.assertIn('error', response.data)
            self.assertEqual(response.data['error'], 'Amount must be a positive integer in cents.')

    @patch('stripe.checkout.Session.create')
    def test_create_donation_stripe_api_error(self, mock_stripe_session_create):
        self.client.force_authenticate(user=self.user)
        # Simulate a Stripe API error
        mock_stripe_session_create.side_effect = stripe.error.StripeError("Stripe processing error")

        data = {'amount': 5000, 'description': 'Stripe error test'}
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertTrue("Stripe processing error" in response.data['error'])

    def test_create_donation_invalid_json(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, data="this is not json", content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid JSON format.')

    def test_create_donation_missing_amount(self):
        self.client.force_authenticate(user=self.user)
        data = {'description': 'Missing amount'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Amount must be a positive integer in cents.')
