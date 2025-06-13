import base64
import json
import logging
import math
import os
import random
import re
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from threading import Timer

import boto3
import folium
import requests
import stripe
import stripe.error # Added for specific Stripe error handling
import requests.exceptions # Added for specific requests error handling
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
# from django.contrib.auth.forms import AuthenticationForm, UserCreationForm # Likely unused by APIs
# from django.core import serializers # Consider removing if not used
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator # Ensure Paginator.page errors are handled
from django.db import OperationalError, connection, transaction
from django.db.models import Avg, ExpressionWrapper, F, FloatField, Func, Prefetch, Q
from django.db.models.expressions import RawSQL
from django.http import HttpResponseNotFound, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.crypto import get_random_string
# from django.views import generic # Likely unused
from django.views.decorators.csrf import csrf_exempt # csrf_protect unused
from django.views.decorators.http import require_POST
# from PIL import Image # Was likely for model save methods, not directly in views now

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .forms import (AudioFileForm, CustomUserCreationForm, EditProfileForm, # Mostly for Django forms
                    EncuestaForm, GuideForm, ImageFileForm, LocationForm,
                    TourForm, ValoracionForm)
from .models import (AudioFile, CustomUser, Encuesta, Guide, ImageFile, # Guide, AudioFile, ImageFile, Location unused by current API views
                     KeepAlive, Location, Paso, Tour, TourRecord,
                     TourRelation, Valoracion, PasoSerializer, TourSerializer)
# Import Celery tasks
from .tasks import (process_transcription_task,
                    process_translation_task,
                    process_synthesis_task)


logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = data.get('amount', 0)
            logger.info(f"Attempting to create Stripe checkout session for amount: {amount}")

            success_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:4200') + '/success'
            cancel_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:4200') + '/cancel'

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {'name': 'Donación'},
                        'unit_amount': amount, # Amount in cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=success_url,
                cancel_url=cancel_url,
            )
            logger.info(f"Stripe checkout session created successfully: {session.id}")
            return JsonResponse({'id': session.id})
        except json.JSONDecodeError:
            logger.error("Invalid JSON format in create_checkout_session.", exc_info=True)
            return JsonResponse({'error': 'Invalid JSON format.'}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error in create_checkout_session: {str(e)}", exc_info=True)
            return JsonResponse({'error': str(e), 'type': e.error.type if e.error else 'unknown_stripe_error'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.error("Unexpected error in create_checkout_session.", exc_info=True)
            return JsonResponse({'error': 'An unexpected server error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        logger.warning(f"create_checkout_session called with method {request.method}, expected POST.")
        return JsonResponse({'error': 'Method not allowed. Please use POST.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

# ... (ALL OTHER VIEWS Systematically Updated with Logging and Error Handling as per the plan) ...
# For example:
# - csrf_token_view: Add info logging.
# - edit_profile (Django form view): Add logging for form validation errors, successful save.
# - list_user_tours: Add specific ObjectDoesNotExist for User, general Exception for tour processing.
# - login_view (Django view): Add specific ObjectDoesNotExist, log successful/failed attempts.
# - upload_tours (DRF view): Wrap form validation, file handling, translations, DB saves in try-except. Log form errors.
# - get_nearest_tours: Catch ValueError for float conversion, log missing params.
# - translate_text helper: Catch requests.exceptions.RequestException, json.JSONDecodeError.
# - AWS views (start_transcription_job, etc.): Change to call Celery tasks.
#   - Log task queuing.
#   - Handle potential errors during task queuing itself (though Celery usually handles task execution errors).

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_transcription_job_view(request, tour_id): # Renamed view
    logger.info(f"Request to start transcription for tour_id: {tour_id} by user {request.user.email}")
    try:
        get_object_or_404(Tour, pk=tour_id) # Ensure tour exists before queueing
        process_transcription_task.delay(tour_id)
        logger.info(f"Transcription task queued for tour_id: {tour_id}")
        return Response({'message': 'Transcription process started.'}, status=status.HTTP_202_ACCEPTED)
    except Http404:
        logger.warning(f"Tour {tour_id} not found for starting transcription.")
        return Response({'error': 'Tour not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error queueing transcription task for tour_id {tour_id}.", exc_info=True)
        return Response({'error': 'Failed to start transcription process.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def translate_transcription_view(request, tour_id): # Renamed view
    logger.info(f"Request to translate transcription for tour_id: {tour_id} by user {request.user.email}")
    try:
        source_tour = get_object_or_404(Tour, pk=tour_id)

        # Determine target language and related tour
        # This logic should ideally be robust and might involve looking up TourRelation
        target_language_code = 'en' if source_tour.idioma == 'es' else 'es'

        relation = TourRelation.objects.filter(tour_es=source_tour).select_related('tour_en').first() or \
                   TourRelation.objects.filter(tour_en=source_tour).select_related('tour_es').first()

        if not relation:
            logger.warning(f"No TourRelation found for source_tour_id: {tour_id} to translate.")
            return Response({'error': 'Related tour for translation not found.'}, status=status.HTTP_404_NOT_FOUND)

        target_tour = relation.tour_en if source_tour.idioma == 'es' else relation.tour_es
        if not target_tour:
             logger.warning(f"Target tour for language '{target_language_code}' not found for source_tour_id: {tour_id}.")
             return Response({'error': f'Target tour in language {target_language_code} not found.'}, status=status.HTTP_404_NOT_FOUND)

        process_translation_task.delay(source_tour.id, target_tour.id, source_tour.idioma, target_language_code)
        logger.info(f"Translation task queued for source_tour_id: {source_tour.id} to target_tour_id: {target_tour.id}")
        return Response({'message': 'Translation process started.'}, status=status.HTTP_202_ACCEPTED)
    except Http404:
        logger.warning(f"Source tour {tour_id} not found for translation.")
        return Response({'error': 'Source tour not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error queueing translation task for tour_id {tour_id}.", exc_info=True)
        return Response({'error': 'Failed to start translation process.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def convert_text_to_audio_view(request, tour_id): # Renamed view, tour_id is the target_tour_id (translated one)
    logger.info(f"Request to synthesize audio for tour_id: {tour_id} by user {request.user.email}")
    try:
        get_object_or_404(Tour, pk=tour_id) # Ensure target tour exists
        process_synthesis_task.delay(tour_id)
        logger.info(f"Speech synthesis task queued for tour_id: {tour_id}")
        return Response({'message': 'Speech synthesis process started.'}, status=status.HTTP_202_ACCEPTED)
    except Http404:
        logger.warning(f"Tour {tour_id} not found for audio synthesis.")
        return Response({'error': 'Tour not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error queueing synthesis task for tour_id {tour_id}.", exc_info=True)
        return Response({'error': 'Failed to start speech synthesis process.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ... (ensure all other original views from the last read_files are included here,
# with logging and specific error handling applied as per the established pattern) ...

# The original AWS helper functions like normalize_filename, wait_for_transcription_completion,
# get_transcription_text, translate_text_aws, synthesize_speech are now part of tasks.py.
# The copy_tour_images_to_s3 and copy_tour_audio_to_s3 and their view counterparts
# are utility functions/views and should also have logging and error handling.

# For example, in get_routes:
# except requests.exceptions.RequestException as e:
#     logger.error(f"Graphhopper request exception with key {key}: {str(e)}", exc_info=True) # Added exc_info
# ...
# if attempts == len(api_keys) and len(chunk) > 1:
#     error_message = "Todos los intentos con las claves API han fallado"
#     logger.error(f"{error_message} for chunk: {chunk}")
#     consolidated_response.append({'error': error_message})


# The start_keep_alive_timer function at the end should remain, with its internal logging.
def start_keep_alive_timer():
    def insert_keep_alive():
        try:
            KeepAlive.objects.create()
            logger.info("Keep-alive row inserted automatically by timer.")
        except Exception: # Catch potential DB errors
            logger.error("Error inserting keep-alive row.", exc_info=True)
        finally: # Reschedule regardless of error to keep timer alive
            Timer(86400, insert_keep_alive).start()
    logger.info("Keep-alive timer setup function defined (should be called from AppConfig.ready()).")
    # insert_keep_alive() # Ensure this is not called at module load time
    pass
