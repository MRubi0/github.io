import base64
import json
import math
import os
import random
import re
from django.conf import settings
import requests
import folium
import shutil
import sqlite3
import time
import unicodedata
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
import io
import boto3
import stripe
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from PIL import Image
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core import serializers
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db import OperationalError, transaction, connection
from django.db.models import Avg, ExpressionWrapper, F, FloatField, Func, Q
from django.db.models.expressions import RawSQL
from botocore.exceptions import ClientError
from django.http import JsonResponse, HttpResponseNotFound
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.views import generic
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from threading import Timer


from .forms import (AudioFileForm, CustomUserCreationForm, EditProfileForm,
                    EncuestaForm, GuideForm, ImageFileForm, LocationForm,
                    TourForm, ValoracionForm)
from .models import (AudioFile, CustomUser, Encuesta, Guide, ImageFile,
                     Location, Paso, Tour, TourRecord, TourRelation, Valoracion, PasoSerializer, TourSerializer, KeepAlive)

stripe.api_key = settings.STRIPE_SECRET_KEY




@csrf_exempt
def create_checkout_session(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        amount = data.get('amount', 0)
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'eur',
                        'product_data': {
                            'name': 'Donación',
                        },
                        'unit_amount': amount,
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url='http://localhost:4200/success',
                cancel_url='http://localhost:4200/cancel',
            )
            return JsonResponse({'id': session.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=403)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_auth(request):
    # Esta vista es solo para propósitos de testeo.
    return Response({'message': 'El token es válido y el usuario está autenticado'}, status=status.HTTP_200_OK)


@csrf_exempt
def csrf_token_view(request):
    """Obtiene el token CSRF de Django."""
    csrf_token = get_token(request)
    print('csrf_token ->', csrf_token);
    return JsonResponse({'csrf_token': csrf_token})


def haversine(lat1, lon1, lat2, lon2):
    # Radio de la Tierra en km
    R = 6371.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c



@permission_classes([IsAuthenticated])
def edit_profile(request):
    if request.method == 'POST':
        form = EditProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu perfil ha sido actualizado correctamente.')
            return redirect('profile')
    else:
        form = EditProfileForm(instance=request.user)
    return render(request, 'user/edit_profile.html', {'form': form})

@login_required
def profile(request):
    return render(request, 'user/profile.html', {'user': request.user})


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def edit_profile(request):
#     if request.method == 'POST':
#         user = request.user
#         data = request.data

#         if 'firstName' in data:
#             user.first_name = data['firstName']
#         if 'lastName' in data:
#             user.last_name = data['lastName']
#         if 'email' in data:
#             user.email = data['email']
#         if 'bio' in data:
#             user.bio = data['bio']
#         if 'avatar' in request.FILES:
#             user.avatar.save(request.FILES['avatar'].name, request.FILES['avatar'])

#         user.save()
#         return Response({'message': 'Profile updated successfully'})
#     return Response({'error': 'Invalid request method'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)



def get_user_tours(request):
    if request.method == 'GET':
        user_id = request.GET.get('id')
        if user_id:
            tours = Tour.objects.filter(user_id=user_id)
            tours_data = []
            for tour in tours:
                tour_data = tour.as_dict()
                # Modificar imagen y audio para incluir una clave intermedia 'url'
                if tour_data.get('imagen'):
                    tour_data['imagen'] = {'url': tour_data['imagen']}
                if tour_data.get('audio'):
                    tour_data['audio'] = {'url': tour_data['audio']}
                    
                # Agregar la información del usuario que creó el tour
                tour_data['user'] = {
                    'id': tour.user.id,
                    'email': tour.user.email,
                    'first_name': tour.user.first_name, 
                    'last_name': tour.user.last_name,
                    'avatar': tour.user.avatar.url,
                    'bio': tour.user.bio,                   
                }
                
                tours_data.append(tour_data)
            return JsonResponse({'tours': tours_data})
        else:
            return JsonResponse({'error': 'Se necesita proporcionar un ID de usuario'}, status=400)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def login_view(request):
    print("Hello, estamos en login_view")
    if request.method == 'POST':
        print(f"Request body: {request.body}")
        print(f"Request POST data: {request.POST}")
        
        email = request.POST.get('username')  # Si estás enviando el email en el campo 'username'
        password = request.POST.get('password')

        print(f"Email: {email}, Password: {password}")
        
        # Buscar al usuario por su email
        try:
            user = CustomUser.objects.get(email=email)
            print(f"Usuario encontrado: {user.username}")
            
            # Intentar autenticar usando el username del usuario
            user = authenticate(request, username=user.username, password=password)

            if user is not None:
                print(f"Usuario autenticado: {user.username}")
                login(request, user)
                return JsonResponse({'success': True})
            else:
                print("Fallo de autenticación")
                return JsonResponse({'error': 'Invalid credentials'}, status=401)
        except CustomUser.DoesNotExist:
            print(f"No existe un usuario con el email {email}")
            return JsonResponse({'error': 'Invalid credentials'}, status=401)
    else:
        print("Método GET no soportado para login")
        return JsonResponse({'error': 'GET request not supported'}, status=405)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_tours(request):
    print("llegamos aqui")
    print(request)
    error_message = None
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header:
        token = auth_header.split(' ')[1]
    else:
        print("No se encontró el header de autorización")
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return Response({'error': 'Usuario no autenticado'}, status=401)     
        form = TourForm(request.POST, request.FILES)       


        if form.is_valid():     
            print("tour valido")
   
            tour_es = form.save(commit=False)
            tour_destino = request.POST['idioma_destino']
            tour_es.user = request.user
            tour_es.idioma = request.POST['idioma']
            tour_es.original = 'original'
            tour_es.suma_valoraciones = 0  # Asignar antes de guardar
            tour_es.total_valoraciones = 0
            tour_es.validado = False  # Si es un campo obligatorio


           
            
            
            tour_es.validado = False
            tour_es.suma_valoraciones = 0

            next_id_es = get_next_id()

            next_id_en = get_next_id()
 

            print('next_id ----> ', next_id_es)

            if 'imagen' in request.FILES:
                image_file = request.FILES['imagen']
                timestamp = int(time.time() * 1000)
                image_name = f"{str(next_id_es).zfill(5)}/{timestamp}.jpg"
                
                tour_es.imagen.save(image_name, image_file, save=False)

            # Asegúrate de que 'audio' no cause el mismo problema
            if 'audio' in request.FILES:
                audio_file = request.FILES['audio']
                timestamp = int(time.time() * 1000)
                audio_name = f"{str(next_id_es).zfill(5)}/aud_{timestamp}.mp3"
                tour_es.audio.save(audio_name, audio_file, save=False)  

            if tour_es.tipo_de_tour == 'leisure':
                tour_es.tipo_de_tour = 'ocio'
            elif tour_es.tipo_de_tour == 'nature':
                tour_es.tipo_de_tour = 'naturaleza'
            print("voy a imprimir el tour")
            print(tour_es)
            print("FINAL")

            print(f"suma_valoraciones antes de guardar: {tour_es.suma_valoraciones}")
            tour_es.save()
            

            

            tour_en = Tour()
            tour_en.user = request.user
            tour_en.imagen = tour_es.imagen
            tour_en.original = tour_es.id   
            tour_en.audio = tour_es.audio
            tour_en.tipo_de_tour = tour_es.tipo_de_tour
            tour_en.recorrido=tour_es.recorrido
            tour_en.duracion=tour_es.duracion
            tour_en.validado = False
            tour_en.descripcion = translate_text(tour_es.descripcion, tour_es.idioma, tour_destino)
            tour_en.titulo = translate_text(tour_es.titulo, tour_es.idioma, tour_destino)         
            tour_en.suma_valoraciones = 0 
            tour_en.total_valoraciones = 0
            tour_en.save()
            

            for i in range(100):
                extra_audio_key = f'extra_step_audio_{i}'

                if extra_audio_key in request.FILES:
                    extra_audio = request.FILES[extra_audio_key]                    
                    extra_description = None
                    extra_image = None
                    extra_latitude = None
                    extra_longitude = None
                    extra_tittle = None
           
                    extra_description_key = f'description_{i}'
                    if extra_description_key in request.POST:
                        extra_description = request.POST.get(extra_description_key, '')

                    extra_tittle_key = f'tittle_{i}'  
                    if extra_tittle_key in request.POST:
                        extra_tittle = request.POST.get(extra_tittle_key, '')

                    paso_es = Paso(tour=tour_es, description=extra_description, tittle=extra_tittle)
                    paso_en = Paso(tour=tour_en, description=extra_description, tittle=extra_tittle)

                    if request.FILES[f'extra_step_audio_{i}']:          
                        extra_audio_file = request.FILES[f'extra_step_audio_{i}']                        
                        timestamp = int(time.time() * 1000)
                        extra_audio_name = f"Tour_audio/{str(next_id_es).zfill(5)}/{str(i+1).zfill(5)}//{timestamp}.mp3"
                        paso_en.audio.save(extra_audio_name, extra_audio_file)
                        paso_es.audio.save(extra_audio_name, extra_audio_file)

                    extra_latitude_key = f'extra_step_latitude_{i}'
                    if extra_latitude_key in request.POST and request.POST[extra_latitude_key]:
                        extra_latitude = float(request.POST[extra_latitude_key])

                    extra_longitude_key = f'extra_step_longitude_{i}'
                    if extra_longitude_key in request.POST and request.POST[extra_longitude_key]:
                        extra_longitude = float(request.POST[extra_longitude_key])

                    if extra_latitude:
                        paso_es.latitude = extra_latitude
                        paso_en.latitude = extra_latitude
                    if extra_longitude:
                        paso_es.longitude = extra_longitude
                        paso_en.longitude = extra_longitude                             

                    extra_image_key = f'extra_step_image_{i}'
        
                    if extra_image_key in request.FILES:
                       extra_image_file = request.FILES[f'extra_step_image_{i}']
                       timestamp = int(time.time() * 1000)
                       extra_image_name = f"Tour_imagen/{str(next_id_es).zfill(5)}/{str(i+1).zfill(5)}/extra_image_{next_id_es}/{timestamp}.jpg"
                       paso_es.image.save(extra_image_name, extra_image_file, save=False)  
                       paso_en.image = paso_es.image                 
                       paso_es.save()
                    paso_en.save()
                 
                else:
                    break


            # Crear la relación entre los tours
            tour_relation = TourRelation(tour_es=tour_es, tour_en=tour_en)
            tour_relation.save()

            return Response({'message': 'Gracias por tu esfuerzo, el tour sera validado por nuestro equipo'})
        else:
            print("tour no valido")
            print(form.errors)  # Esto te ayudará a ver los errores en la consola
            return Response({'error': 'Formulario no válido', 'detalles': form.errors}, status=400)



def upload_to_func(instance, filename):
    timestamp = int(time.time() * 1000)
    return f'{timestamp}_{filename}'


@csrf_exempt
@api_view(['POST'])
def upload_encuesta(request):
    if request.method == 'POST':
        # Mapeo de los nombres de campos del formulario a los nombres de campos del modelo
        mapeo_campos = {
            'pregunta1': 'edad',
            'pregunta2': 'genero',
            'pregunta3': 'nacionalidad',
            'subpregunta3_1': 'otro_nacionalidad',
            'pregunta4': 'viajes_al_anio',
            'pregunta5': 'tours_al_anio',
            'pregunta6': 'valoracion_tour',
            'pregunta7': 'valoracion_contenido',
            'subpregunta7_1': 'otro_contenido',
            'pregunta8': 'valoracion_formato',
            'subpregunta8_1': 'gusta_formato',
            'subpregunta8_2': 'menos_gusta_formato',
            'pregunta9': 'valoracion_duracion',
            'pregunta10': 'duracion_optima',
            'pregunta11': 'ayuda_a_lograr_objetivos',
            'pregunta12': 'caracteristicas_valiosas',
            'pregunta13': 'caracteristicas_menos_valiosas',
            'pregunta14': 'puntos_friccion',
            'pregunta15': 'usar_producto_en_proximas_vacaciones',
            'pregunta16': 'recomendar_producto',
            'pregunta17': 'probabilidad_de_volver_a_realizar_tour',
            'pregunta18': 'flexibilidad_de_horarios_idioma',
            'pregunta19': 'acceso_a_tours',
            'subpregunta19_1': 'otro_acceso',
            'pregunta20': 'precio_dispuesto_a_pagar',
            'pregunta21': 'formato_red_social',
            'pregunta22': 'correo',
            'id': 'id_tour',
        }

        # Crear la instancia del modelo Encuesta sin guardarla aún
        encuesta = Encuesta()
        print(encuesta)

        for clave_form, clave_modelo in mapeo_campos.items():
            valor = request.data.get(clave_form)
            if valor is not None:  # Esto manejará el caso de campos vacíos o no enviados
                setattr(encuesta, clave_modelo, valor)

        encuesta.save()  # Guardar la instancia en la base de datos
        return Response({'success': 'Encuesta guardada correctamente'})

    return Response({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def register_view(request):
    if request.method == 'POST':
        # Cargamos el cuerpo de la solicitud (que es un JSON) en un diccionario de Python
        data = json.loads(request.body.decode('utf-8'))
        print(data)
        # En lugar de usar request.POST, usamos el diccionario data que acabamos de crear
        form = CustomUserCreationForm(data)
        
        if form.is_valid():
            user = form.save()
            login(request, user)
            return JsonResponse({"success": True, "message": "Registration successful!"})
        else:
            errors = {}
            for field, error_list in form.errors.as_data().items():
                errors[field] = [str(error) for error in error_list]
            print(errors)
            messages.error(request, "Ha ocurrido un error en el registro. Por favor, verifica tus datos e inténtalo de nuevo.")

            return JsonResponse({
                "success": False,
                "message": "Error in registration. Please verify your data and try again.",
                "errors": errors
            })            
    else:
        form = CustomUserCreationForm()

    return JsonResponse({"success": False, "message": "Invalid request method."})

def registration_success(request):
    return render(request, 'registration/success.html')


def index(request):
    last_naturaleza = Tour.objects.filter(tipo_de_tour="naturaleza").order_by('-created_at').first()
    last_cultural = Tour.objects.filter(tipo_de_tour="cultural").order_by('-created_at').first()
    last_ocio = Tour.objects.filter(tipo_de_tour="ocio").order_by('-created_at').first()



    # Crear una lista con los tours obtenidos
    latest_tours = [last_ocio, last_naturaleza, last_cultural]

    # Eliminar posibles valores None en caso de que no haya tours de algún tipo
    latest_tours = [tour for tour in latest_tours if tour is not None]

    context = {'tours': latest_tours}
    return render(request, 'index.html', context)



def sqlite_haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c



def get_nearest_tours(request):
    latitud_usuario = float(request.GET.get('latitude', None))
    longitud_usuario = float(request.GET.get('longitude', None))
    idioma = request.GET.get('language', None)
    if latitud_usuario is None or longitud_usuario is None:
        return JsonResponse({"error": "Faltan parámetros: latitude y/o longitude"}, status=400)
    
    if idioma is None:
        return JsonResponse({"error": "Falta el parámetro: language"}, status=400)

    # Aquí iría la lógica para buscar los tours más cercanos
    tours = Tour.objects.filter(idioma=idioma)
    tours_with_distances = []
    for tour in tours:
        distance = haversine(latitud_usuario, longitud_usuario, tour.latitude, tour.longitude)
        tours_with_distances.append({'tour': tour, 'distance': distance})

    tour_categories = ['cultural', 'naturaleza', 'ocio']
    nearest_tours = {}

    result = []

    for category in tour_categories:
        # Ordenar por distancia y filtrar por categoría
        filtered_tours = sorted(
            filter(lambda x: x['tour'].tipo_de_tour == category, tours_with_distances),
            key=lambda x: x['distance']
        )
        # Tomar el primer tour de la lista, que es el más cercano
        if filtered_tours:
            tour = filtered_tours[0]['tour']
            tour_object = {
                'id': tour.id,
                'titulo': tour.titulo,
                'descripcion': tour.descripcion,
                'tipo_de_tour': tour.tipo_de_tour,
                'imagen': {'url': tour.imagen.url},
                'distance': filtered_tours[0]['distance'],
                'duracion': tour.duracion,
                'recorrido': tour.recorrido,
                'user': {
                    'id': tour.user.id,
                    'email': tour.user.email,
                    'first_name': tour.user.first_name, 
                    'last_name': tour.user.last_name,
                    'avatar': tour.user.avatar.url,
                    'bio': tour.user.bio,                   
                }
            }
            result.append(tour_object)

    return JsonResponse(result, safe=False)


def tour_detail(request, tour_id):
    # Obtener el tour
    tour = get_object_or_404(Tour, pk=tour_id)

    # Imprimir latitud y longitud
    print("Tour Lat: ", tour.latitude)
    print("Tour Lng: ", tour.longitude)
    
    if tour.imagen:
        print("Image URL: ", tour.imagen.url)
    if tour.audio:
        print("Audio URL: ", tour.audio.url)
    context = {
        'tour': tour, 
        'user': request.user,
    }
    return render(request, 'tour_detail.html', context)



def get_latest_tours(request):
    idioma = request.GET.get('language', None)
    if not idioma:
        return JsonResponse({"error": "Falta el parámetro: language"}, status=400)
    tour_types = ['cultural', 'naturaleza','ocio']

    # Consulta el último tour de cada tipo
    tour_data = {}

    result = []

    for t in tour_types:
        try:
            latest_tour = Tour.objects.filter(tipo_de_tour=t, idioma=idioma).latest('created_at')
            tour_data = {
                'id': latest_tour.id,
                'titulo': latest_tour.titulo,
                'descripcion': latest_tour.descripcion,
                'tipo_de_tour': latest_tour.tipo_de_tour,
                'imagen': {
                    'url': latest_tour.imagen.url,
                },
                'recorrido': latest_tour.recorrido,
                'duracion': latest_tour.duracion,
                'user': {
                    'id': latest_tour.user.id,
                    'email': latest_tour.user.email,
                    'first_name': latest_tour.user.first_name, 
                    'last_name': latest_tour.user.last_name,
                    'avatar': latest_tour.user.avatar.url,
                    'bio': latest_tour.user.bio               
                }
            }
            result.append(tour_data)
        except Tour.DoesNotExist:
            # No hay tours para este tipo
            pass

    return JsonResponse(result, safe=False)


def get_random_tours(request):
    idioma = request.GET.get('language', None)
    if not idioma:
        return JsonResponse({"error": "Falta el parámetro: language"}, status=400)
    
    ocio_tours = Tour.objects.filter(tipo_de_tour="ocio", idioma=idioma, validado=True)
    naturaleza_tours = Tour.objects.filter(tipo_de_tour="naturaleza",idioma=idioma, validado=True)
    cultural_tours = Tour.objects.filter(tipo_de_tour="cultural", idioma=idioma, validado=True)
               
    # Elige un tour aleatorio de cada categoría
    random_tours = {
        "cultural": random.choice(cultural_tours) if cultural_tours else None,
        "naturaleza": random.choice(naturaleza_tours) if naturaleza_tours else None,
        "ocio": random.choice(ocio_tours) if ocio_tours else None,        
    }

    # Convierte los objetos de los tours en diccionarios para que puedan ser serializados a JSON
    
    random_tours_json = {}
    result=[]
    for key, tour in random_tours.items():

        if tour:
            random_tours_json= tour.as_dict()
            random_tours_json['id'] = tour.id            
            random_tours_json['imagen']={
                'url': random_tours_json['imagen']                
            }
            random_tours_json['user']={
                    'id': tour.user.id,
                    'email': tour.user.email,
                    'first_name': tour.user.first_name, 
                    'last_name': tour.user.last_name,
                    'avatar': tour.user.avatar.url,
                    'bio': tour.user.bio,                   
                }                       
            result.append(random_tours_json)      
    return JsonResponse(result,safe=False)


def get_tour_distance(request):
    tour_id = request.GET.get('tourId')
    languaje = request.GET.get('languaje')
    latitud_usuario = request.GET.get('latitude', None)
    longitud_usuario = request.GET.get('longitude', None)
    
    if not tour_id or not languaje:
        return JsonResponse({"error": "Faltan parámetros: tourId y/o languaje"}, status=400)
    related_tour_id = tour_id  
    
    if languaje == "en":
        relation = TourRelation.objects.filter(tour_es_id=tour_id).first()
        if relation:
            related_tour_id = relation.tour_en.id
    else:
        relation = TourRelation.objects.filter(tour_en_id=tour_id).first()
        if relation:
            related_tour_id = relation.tour_es.id
    if latitud_usuario is None or longitud_usuario is None:
        return JsonResponse({"error": "Faltan parámetros: latitude y/o longitude"}, status=400)

    if latitud_usuario != 'None':
        latitud_usuario = float(latitud_usuario)
    else:
        latitud_usuario = None

    if longitud_usuario != 'None':
        longitud_usuario = float(longitud_usuario)
    else:
        longitud_usuario = None

    tour = get_object_or_404(Tour, id=related_tour_id)

    distance = haversine(latitud_usuario, longitud_usuario, tour.latitude, tour.longitude)

    tour_data = serializers.serialize('python', [tour])
    tour_data[0]['fields']['distance'] = distance
    
    return JsonResponse(tour_data, safe=False)

def get_nearest_tours_all(request):
    latitud_usuario = request.GET.get('latitude', None)
    longitud_usuario = request.GET.get('longitude', None)
    idioma = request.GET.get('language', None)

    if latitud_usuario is None or longitud_usuario is None:
        return JsonResponse({"error": "Faltan parámetros: latitude y/o longitude"}, status=400)
    
    if idioma is None:
        return JsonResponse({"error": "Falta el parámetro: language"}, status=400)

    if latitud_usuario != 'None':
        latitud_usuario = float(latitud_usuario)
    else:
        latitud_usuario = None

    if longitud_usuario != 'None':
        longitud_usuario = float(longitud_usuario)
    else:
        longitud_usuario = None

    # Obtener todos los tours filtrados por idioma
    tours = Tour.objects.filter(idioma=idioma, validado=True)
    tours_with_distances = []
    if latitud_usuario is not None and longitud_usuario is not None:
        for tour in tours:
            distance = haversine(latitud_usuario, longitud_usuario, tour.latitude, tour.longitude)
            tours_with_distances.append({'tour': tour, 'distance': distance})
        sorted_tours = sorted(tours_with_distances, key=lambda x: x['distance'])
    else:
        for tour in tours:
            tours_with_distances.append({'tour': tour, 'id': tour.id, 'distance': None})
        sorted_tours = sorted(tours_with_distances, key=lambda x: x['id'])

    per_page = len(sorted_tours)
    page = request.GET.get('page', 1)  # Obtiene el número de página de los parámetros GET
    # Paginar los resultados
    paginator = Paginator(sorted_tours, per_page)
    current_page_tours = paginator.get_page(page)

    # Serializar solo los objetos de tour en la página actual
    serialized_tours = [{
        'id': tour['tour'].id,
        'titulo': tour['tour'].titulo,
        'descripcion': tour['tour'].descripcion,
        'tipo_de_tour': tour['tour'].tipo_de_tour,
        'imagen': {'url': tour['tour'].imagen.url},
        'distance': tour['distance'],
        'recorrido': tour['tour'].recorrido,
        'duracion': tour['tour'].duracion,
        'user': {
            'id': tour['tour'].user.id,
            'email': tour['tour'].user.email,
            'first_name': tour['tour'].user.first_name, 
            'last_name': tour['tour'].user.last_name,
            'avatar': None,
            'bio': tour['tour'].user.bio,
        }
    } for tour in current_page_tours]

    response_data = {
        'tours': serialized_tours,
        'total_pages': paginator.num_pages  # Devuelve el número total de páginas
    }

    # Devolver los tours más cercanos como respuesta JSON
    return JsonResponse(response_data)


def all_tours(request):
    # Obtenemos todos los tours disponibles
    tours = Tour.objects.all()

    # Pasamos los tours al contexto de la plantilla
    context = {'tours': tours}
    return render(request, 'all_tours.html', context)

def custom_tours_page(request):
    latitude = request.GET.get('latitude', None)
    longitude = request.GET.get('longitude', None)
    location = request.GET.get('location', 'la ubicación buscada')
    context = {'latitude': latitude, 'longitude': longitude, 'location': location}
    return render(request, 'custom_tours_page.html', context)


def directions(request, tour_id):
    tour = Tour.objects.get(pk=tour_id)
    print(f"Latitud del tour: {tour.latitude}")
    print(f"Longitud del tour: {tour.longitude}")
     # Obtiene el primer paso del tour
    try:
        first_step = tour.paso_set.order_by('id').first()
        if first_step:
            step_id = first_step.id
        else:
            step_id = None
    except Paso.DoesNotExist:
        step_id = None

    return render(request, 'directions.html', {'tour': tour, 'step_id': step_id})

@api_view(['GET'])
def get_tour_with_steps(request, tour_id, languaje):
    try:        
        relation = TourRelation.objects.filter(tour_es_id=tour_id).first()
        if relation:
            if languaje == "en":                
                related_tour_id = relation.tour_en_id
            else:
                related_tour_id = tour_id
        else:
            relation = TourRelation.objects.filter(tour_en_id=tour_id).first()
            if relation:
                if languaje == "es":             
                    related_tour_id = relation.tour_es_id
                else:
                    related_tour_id = relation.tour_en_id
            else:
                related_tour_id = tour_id

        tour = get_object_or_404(Tour, pk=related_tour_id)
        steps = Paso.objects.filter(tour=tour)

        tour_data = {
            "id": tour.id,
            "latitude": tour.latitude,
            "longitude": tour.longitude,
            "titulo": tour.titulo,
            "image": tour.imagen.url,
            "audio": tour.audio.url,
            "description": tour.descripcion,
            "duracion":tour.duracion,
            "recorrido":tour.recorrido,
            "tipo_de_tour":tour.tipo_de_tour,
            "idioma":tour.idioma,
            "steps": [],
            "relation":[related_tour_id,tour_id]
        }

        for step in steps:
            tour_data["steps"].append({
                "id": step.id,
                "image": step.image.url if step.image else None,                
                "audio": step.audio.url if step.audio else None,
                "latitude": step.latitude,
                "longitude": step.longitude,
                "description": step.description,
                "tittle": step.tittle,
                "step_number":step.step_number
            })

        return Response(tour_data)
    except Tour.DoesNotExist:
        return Response({"error": "Tour no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    
def get_tour_data(tour_id):
    print('init')
    tour_objects = Tour.objects.get(id=tour_id)  
    tour_data = []
    for tour in tour_objects:
        tour_data.append({
            "latitude": tour.latitude,
            "longitude": tour.longitude,
            "titulo": tour.titulo
        })
    return tour_data


def create_map(tour_data):
    m = folium.Map(location=[20, 0], zoom_start=2.5)

    for data in tour_data:
        folium.Marker(
            location=[data["latitude"], data["longitude"]],
            popup=data["titulo"],
            icon=folium.Icon(icon="cloud"),
        ).add_to(m)

    m.save('LTtApp/templates/LTtApp/map.html')


def map_view(request):
    tour_data = get_tour_data()
    create_map(tour_data)
    return render(request, 'LTtApp/map.html')

def debug_tour(request, tour_id):
    # asumimos que obtenes tu tour de esta manera
    tour = Tour.objects.get(id=tour_id)
    
    # imprimimos todos los atributos y valores del tour
    print(vars(tour))


def next_step(request, tour_id, step_id=None):
    print(f"Handling next_step request for tour_id={tour_id}, step_id={step_id}")

    try:
        # Encuentra el tour por su ID
        tour = Tour.objects.get(pk=tour_id)
        print(f"Found tour: {tour}")
        # Encuentra el paso actual
        current_step = Paso.objects.get(pk=step_id)
        print(f"Found current step: {current_step}")

        try:
            next_step = Paso.objects.filter(tour_id=tour_id, id__gte=current_step.id).order_by('id').first()

            print(f"Found next step: {next_step}")
        except Paso.DoesNotExist:
            print(f"No more steps found for tour_id={tour_id}")
            return JsonResponse({'error': 'No more steps'}, status=404)


        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Retornar los datos del próximo paso
            if next_step is not None:
                response = {
                    'latitude': next_step.latitude,
                    'longitude': next_step.longitude

                }
                print(f"Returning response: {response}")  
                return JsonResponse(response)
            else:
                return JsonResponse({'message': 'End of tour'}, status=200)

        else:
            return render(request, 'step.html', {'tour': tour, 'step': next_step})

    except Tour.DoesNotExist:
        print(f"No tour found with tour_id={tour_id}")
        return JsonResponse({'error': 'Tour not found'}, status=404)
    except Paso.DoesNotExist:
        print(f"No step found with step_id={step_id}")
        return JsonResponse({'error': 'Step not found'}, status=404)

def step_detail(request, tour_id, step_id):
    try:
        tour = Tour.objects.get(pk=tour_id)

        step = Paso.objects.get(pk=step_id)

        if step.tour != tour:
            raise Paso.DoesNotExist()

        try:
            next_step = Paso.objects.filter(tour_id=tour_id, id__gt=step_id).order_by('id').first()
        except Paso.DoesNotExist:
            next_step = None

        return render(request, 'step.html', {'tour': tour, 'step': step, 'next_step': next_step})

    except Tour.DoesNotExist:
        # Manejo del error cuando no se encuentra el tour
        return HttpResponseNotFound('Tour not found')

    except Paso.DoesNotExist:
        # Manejo del error cuando no se encuentra el paso o el paso no pertenece al tour
        return HttpResponseNotFound('Step not found or does not belong to this tour')
    
def get_tour_locations(request, tour_id):
    try:
        
        tour = Tour.objects.get(id=tour_id)
        
        pasos = Paso.objects.filter(tour=tour)

        
        locations = [{'lat': paso.latitude, 'long': paso.longitude} for paso in pasos if paso.latitude and paso.longitude]

        return JsonResponse({'locations': locations})

    except Tour.DoesNotExist:
        return JsonResponse({'error': 'Tour no encontrado'}, status=404)



@api_view(['POST'])
def create_tour_record(request):    
    tour_id = request.data.get('tour_id')
    if not tour_id:
        print("Error: Falta el ID del tour")
        return JsonResponse({'error': 'Falta el ID del tour'}, status=400)

    # Verifica si el tour existe
    tour = get_object_or_404(Tour, pk=tour_id)

    # Verificar si ya existe un registro para este tour y usuario
    if TourRecord.objects.filter(user=request.user, tour=tour).exists():
        print("El usuario ya ha registrado este tour.")
        return JsonResponse({'error': 'Este tour ya ha sido registrado por el usuario'}, status=400)

    try:
        tour_record = TourRecord(user=request.user, tour=tour)
        tour_record.save()
        print("Tour registrado con éxito para el usuario:", request.user.username)
        return JsonResponse({'message': 'Tour registrado con éxito'})
    except Exception as e:
        print("Error al registrar el tour:", str(e))
        return JsonResponse({'error': 'Error al registrar el tour'}, status=500)


def get_user_tour_records(request):
    if request.method == 'GET':
        user_id = request.GET.get('id')
        language = request.GET.get('language', 'es')
        print(f'Received user_id: {user_id}, language: {language}')
        
        if user_id:
            tours = Tour.objects.filter(user_id=user_id)
            print(f'Found tours for user {user_id}: {tours}')
            tours_data = []
            processed_tours = set()

            for tour in tours:
                if tour.id in processed_tours:
                    continue
                
                # Obtener el tour en el idioma preferido
                if language == 'es':
                    related_tour = TourRelation.objects.filter(tour_es=tour).first()
                else:
                    related_tour = TourRelation.objects.filter(tour_en=tour).first()

                if related_tour:
                    if language == 'es':
                        tour_to_use = related_tour.tour_es
                        other_tour = related_tour.tour_en
                    else:
                        tour_to_use = related_tour.tour_en
                        other_tour = related_tour.tour_es
                else:
                    tour_to_use = tour
                    other_tour = None

                # Registrar el tour procesado
                processed_tours.add(tour_to_use.id)
                if other_tour:
                    processed_tours.add(other_tour.id)

                # Obtener todas las valoraciones del tour actual solo del usuario autenticado
                valoraciones = Valoracion.objects.filter(tour_id=tour_to_use.id, user_id=user_id)
                print(f'Valoraciones iniciales del tour {tour_to_use.id} para el usuario {user_id}: {valoraciones}')
                
                # Si hay una relación, agregar las valoraciones del tour relacionado solo del usuario autenticado
                if other_tour:
                    valoraciones_otro = Valoracion.objects.filter(tour_id=other_tour.id, user_id=user_id)
                    valoraciones = valoraciones | valoraciones_otro
                    print(f'Valoraciones relacionadas del tour {other_tour.id} para el usuario {user_id}: {valoraciones_otro}')
                
                print(f'Valoraciones finales del tour {tour_to_use.id} para el usuario {user_id}: {valoraciones}')

                valoraciones_data = []

                for valoracion in valoraciones:
                    valoracion_data = {
                        "puntuacion": valoracion.puntuacion,
                        "comentario": valoracion.comentario,
                        "fecha": valoracion.fecha.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    valoraciones_data.append(valoracion_data)

                tour_data = {
                    "id": tour_to_use.id,
                    "titulo": tour_to_use.titulo,
                    "descripcion": tour_to_use.descripcion,
                    "imagen": {'url': tour_to_use.imagen.url} if tour_to_use.imagen else None,
                    "audio": {'url': tour_to_use.audio.url} if tour_to_use.audio else None,
                    "latitude": tour_to_use.latitude,
                    "longitude": tour_to_use.longitude,
                    "tipo_de_tour": tour_to_use.tipo_de_tour,
                    "recorrido": tour_to_use.recorrido,
                    "duracion": tour_to_use.duracion,
                    "user": {
                        'id': tour_to_use.user.id,
                        'email': tour_to_use.user.email,
                        'first_name': tour_to_use.user.first_name, 
                        'last_name': tour_to_use.user.last_name,
                        'avatar': tour_to_use.user.avatar.url if tour_to_use.user.avatar else None,
                        'bio': tour_to_use.user.bio,
                    },
                    "valoraciones": valoraciones_data
                }
                tours_data.append(tour_data)
            return JsonResponse({'tours': tours_data})
        else:
            return JsonResponse({'error': 'Se necesita proporcionar un ID de usuario'}, status=400)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
@require_POST
def get_routes(request):
    global current_key_index
    
    if request.method == 'POST':
        request_body = request.body
        try:
            data = json.loads(request_body)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Formato JSON inválido'}, status=400)

        api_keys = [
            '69604395-613a-4fc0-b3af-1d841ac5d565',
            'd56a81fe-a24e-4ace-ab47-b9aa06ed0874',
            '74f72b76-bb28-4bb8-b862-a756103cb2b1', 
            'b3bca5f8-0181-44f8-9d90-a8819d20bb71',
            'a0d7b1fe-9ebe-4975-a389-be62b705d15d',
            '8ad22295-91d0-40f7-9033-1ca16a877881'
        ]
        
        current_minute = datetime.now().minute
        key_index = current_minute % len(api_keys)
        
        consolidated_response = []
        for i in range(0, len(data[0]['points']), 5):
            attempts = 0  # Contador de intentos para cada chunk
            while attempts < len(api_keys):
                try:
                    key = api_keys[key_index]
                    print(f"Intentando con la clave {key}")
                    url = f'https://graphhopper.com/api/1/route?key={key}'
                    chunk = data[0]['points'][i:i+5]
                    print(f"Puntos actuales: {chunk}")
                    response = requests.post(url, json={'points': chunk, "points_encoded": False, "profile": "foot"})
                    
                    if len(chunk)==1:
                        response.status_code = 200
                    # Simplificar la verificación de éxito al estado HTTP 200 solamente
                    if response.status_code == 200:
                        json_response = response.json()
                        consolidated_response.append(json_response)
                        print("Respuesta exitosa.")
                        break  # Sale del loop de reintento y continúa con el siguiente chunk
                    else:
                        # Imprime información adicional para diagnosticar el fallo
                        print(f"Fallo con clave {key}. Código de estado: {response.status_code}")
                        print("Parte de la respuesta:", response.text[:150])  # Imprime los primeros 150 caracteres de la respuesta
                    

                except requests.exceptions.RequestException as e:
                    print(f"Excepción al hacer la solicitud con clave {key}: {str(e)}")
                finally:
                    key_index = (key_index + 1) % len(api_keys)  # Siguiente clave
                    attempts += 1  # Incrementa el contador de intentos
            
            if attempts == len(api_keys):
                error_message = "Todos los intentos con las claves API han fallado"
                consolidated_response.append({'error': error_message})
            
        return JsonResponse(consolidated_response, safe=False)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


def save_base64_as_file(base64_data, file_path):
    try:
        decoded_data = base64.b64decode(base64_data)
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        return True
    except Exception as e:
        print(f"Error saving base64 data as file: {e}")
        return False

def upload_file_to_s3(file_path, bucket_name, folder_path, file_name):
    try:
        s3 = boto3.client('s3')
        with open(file_path, 'rb') as f:
            s3.put_object(Body=f, Bucket=bucket_name, Key=f'{folder_path}/{file_name}')
        return True
    except ClientError as e:
        print(f"Error uploading file to S3: {e}")
        return False
    


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])  # Cambia según tus requerimientos de autenticación
def crear_valoracion(request):
    
    data = request.data
    
    # Asegúrate de que el 'tour_id' y la 'puntuacion' están presentes, la resena no porque es opcional
    if 'tour_id' not in data or 'puntuacion' not in data:
        
        return JsonResponse({'error': 'Faltan datos necesarios'}, status=400)

    # Intenta obtener el tour
    tour = get_object_or_404(Tour, pk=data['tour_id'])

    # Crea una instancia de ValoracionForm para validar los datos
    valoracion_data = {
        'puntuacion': data['puntuacion'],
        'comentario': data.get('comentario', '')  # El comentario es opcional
    }
    
    if request.user.is_authenticated:
        valoracion_existente = Valoracion.objects.filter(tour=tour, user=request.user).first()

        if valoracion_existente:
            # Actualiza la valoración existente
            for key, value in valoracion_data.items():
                setattr(valoracion_existente, key, value)
            valoracion_existente.fecha = timezone.now()  # Actualiza la fecha
            valoracion_existente.save()
            
            return JsonResponse({'mensaje': 'Valoración actualizada correctamente'}, status=200)



    form = ValoracionForm(valoracion_data)
    
    if form.is_valid():
        valoracion = form.save(commit=False)
        valoracion.tour = tour

        # Asocia el usuario solo si está autenticado
        if request.user.is_authenticated:
            valoracion.user = request.user
           
        try:
            valoracion.save()
           
            return JsonResponse({'mensaje': 'Valoración creada correctamente'}, status=201)
        except ValidationError as e:
         
            return JsonResponse({'error': str(e)}, status=400)
    else:
        
        return JsonResponse({'error': 'Datos inválidos', 'detalles': form.errors}, status=400)
    


def media_valoracion_tour(request, tour_id):
    cache_key = f"media_valoracion_{tour_id}"
    media_puntuacion = cache.get(cache_key)
    if media_puntuacion is None:
        tour = get_object_or_404(Tour, pk=tour_id)
        relation = TourRelation.objects.filter(tour_es=tour).first() or TourRelation.objects.filter(tour_en=tour).first()
        valoraciones = Valoracion.objects.filter(tour=tour)

        if tour.original != 'original':
                # Es una traducción, obtener valoraciones del tour original
                tour_original = get_object_or_404(Tour, pk=tour.original)
                valoraciones = Valoracion.objects.filter(tour=tour) | Valoracion.objects.filter(tour=tour_original)
                
        else:
            # Es un tour original, obtener valoraciones de sus traducciones
            traducciones = Tour.objects.filter(original=tour.id)
            for traduccion in traducciones:
                valoraciones = valoraciones | Valoracion.objects.filter(tour=traduccion)
                
        resultado = valoraciones.aggregate(media_puntuacion=Avg('puntuacion'))
        media_puntuacion = resultado.get('media_puntuacion', 5.0)
        if media_puntuacion == 0.0:
            media_puntuacion = 5.0
        cache.set(cache_key, media_puntuacion, timeout=3600*25)  # Lo guarda en caché por 25 horas
    return JsonResponse({'media_puntuacion': media_puntuacion})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    print(f"Usuario autenticado: {request.user.is_authenticated}")
    if request.method == 'POST':
        user = request.user  # Asume que ya has manejado la autenticación

        # Actualizar campos basados en la presencia en el request.POST o request.FILES
        first_name = request.POST.get('firstName')
        if first_name is not None:
            user.first_name = first_name

        last_name = request.POST.get('lastName')
        if last_name is not None:
            user.last_name = last_name

        email = request.POST.get('email')
        if email is not None:
            user.email = email

        bio = request.POST.get('bio')
        if bio is not None:
            user.bio = bio

        avatar = request.FILES.get('profileImage')
        if avatar is not None:
            user.avatar.save(avatar.name, avatar)

        user.save()

        return JsonResponse({'message': 'Perfil actualizado correctamente'})
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    

@csrf_exempt
def upload_profile_image(request):
    if request.method == 'POST':
        user = request.user  # Asegúrate de obtener el usuario correctamente, esto es solo un ejemplo
        file = request.FILES.get('avatar')
        if file:
            # Aquí deberías guardar el archivo en el lugar deseado y actualizar la referencia en el usuario
            user.avatar.save(file.name, file)
            user.save()
            return JsonResponse({'message': 'Imagen cargada con éxito.'})
        else:
            return JsonResponse({'error': 'No se proporcionó archivo.'}, status=400)
    else:
        return JsonResponse({'error': 'Método no permitido.'}, status=405)


def search_user_by_id(request):
    if request.method == 'GET':
        user_id = request.GET.get('id')
        try:
            if user_id:
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    return JsonResponse({'error': 'El usuario con el ID proporcionado no existe'}, status=404)

                user_data = {
                    'id': user.id,
                    'email': user.email,
                    'bio': user.bio,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'avatar': user.avatar.url if user.avatar else None,
                }
        
                return JsonResponse({'user': user_data})
            else:
                return JsonResponse({'error': 'Se necesita proporcionar un ID de usuario'}, status=400)
        
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': 'Usuario no encontrado'}, status=404)
        except Exception as e:
            # Log general para cualquier otro tipo de error
            print(e)

    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)



def translate_text(text, idioma_origen, tour_destino):
    url = "https://deep-translate1.p.rapidapi.com/language/translate/v2"
    headers = {
        'X-RapidAPI-Key': "75c294e6a8msh19ef7b3ebb91873p16517ejsn5f6bff2b1abd",
        'X-RapidAPI-Host': "deep-translate1.p.rapidapi.com"
    }
    payload = {
        "q": text,
        "source": idioma_origen,
        "target": tour_destino
    } 
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response_data = response.json()
        if response.status_code == 200:
            translated_text = response_data.get('data', {}).get('translations', {}).get('translatedText', '')
            return translated_text if translated_text else text
        else:
            return text
    except Exception as e:
        print(f"Exception in translation: {str(e)}")
        return text
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def edit_tour(request, tour_id, size):
    language = request.POST.get('idioma', 'es')
    tour_source = get_object_or_404(Tour, id=tour_id)
    tour_relation = get_object_or_404(TourRelation, tour_es=tour_source) if language == 'es' else get_object_or_404(TourRelation, tour_en=tour_source)
    tour_target = tour_relation.tour_en if language == 'es' else tour_relation.tour_es
    tour_destino = 'en' if language == 'es' else 'es'

    if request.method == 'PUT':
        if not request.user.is_authenticated:
            return Response({'error': 'Usuario no autenticado'}, status=401)

        form = TourForm(request.POST, request.FILES, instance=tour_source)

        if form.is_valid():
            tour_source = form.save(commit=False)
            tour_source.user = request.user
            tour_source.idioma = language

            if 'image' in request.FILES:
                image_file = request.FILES['image']
                timestamp = int(time.time() * 1000)
                image_name = f"{tour_source.id}/{timestamp}.jpg"
                delete_s3_file(tour_source.imagen.name)
                tour_source.imagen.save(image_name, image_file)

            if 'audio' in request.FILES:
                audio_file = request.FILES['audio']
                timestamp = int(time.time() * 1000)
                audio_name = f"{tour_source.id}/aud_{timestamp}.mp3"
                delete_s3_file(tour_source.audio.name)
                tour_source.audio.save(audio_name, audio_file)

            tour_source.validado = False
            tour_source.save()

            tour_target.user = request.user
            tour_target.imagen = tour_source.imagen
            tour_target.audio = tour_source.audio
            tour_target.tipo_de_tour = tour_source.tipo_de_tour
            tour_target.recorrido = tour_source.recorrido
            tour_target.duracion = tour_source.duracion
            tour_target.validado = False
            tour_target.latitude = tour_source.latitude
            tour_target.longitude = tour_source.longitude
            tour_target.descripcion = translate_text(tour_source.descripcion, tour_source.idioma, tour_destino)
            tour_target.titulo = translate_text(tour_source.titulo, tour_source.idioma, tour_destino)
            tour_target.save()

            deleting_steps = json.loads(request.POST.get('deleting', '[]'))
            if deleting_steps:
                for step_id in deleting_steps:
                    paso = get_object_or_404(Paso, id=step_id)
                    if paso.image:
                        delete_s3_file(paso.image.name)
                    if paso.audio:
                        delete_s3_file(paso.audio.name)
                    paso.delete()

            for i in range(size):
                step_id = request.POST.get(f'steps[{i}][id]', None)
                extra_audio_key = f'steps[{i}][audio]'
                extra_description_key = f'steps[{i}][description]'
                extra_tittle_key = f'steps[{i}][tittle]'
                extra_latitude_key = f'steps[{i}][latitude]'
                extra_longitude_key = f'steps[{i}][longitude]'
                extra_image_key = f'steps[{i}][image]'
                extra_step_number_key = f'steps[{i}][stepNumber]'

                extra_description = request.POST.get(extra_description_key, '')
                extra_tittle = request.POST.get(extra_tittle_key, '')
                extra_step_number = int(request.POST.get(extra_step_number_key, i + 1))

                if step_id and Paso.objects.filter(id=int(step_id)).exists():
                    paso_source = Paso.objects.get(id=int(step_id))
                    paso_source.step_number = extra_step_number
                else:
                    paso_source = Paso(tour=tour_source, step_number=extra_step_number)

                if extra_audio_key in request.FILES:
                    extra_audio_file = request.FILES[extra_audio_key]
                    timestamp = int(time.time() * 1000)
                    extra_audio_name = f"extra_audio_{tour_source.id}/{timestamp}.mp3"
                    if paso_source.audio:
                        delete_s3_file(paso_source.audio.name)
                    paso_source.audio.save(extra_audio_name, extra_audio_file)
                else:
                    extra_audio = request.POST.get(extra_audio_key, None)
                    if extra_audio:
                        extra_audio = extra_audio.replace("https://bucket-test-west2.s3.amazonaws.com", "")
                        paso_source.audio = extra_audio

                if extra_image_key in request.FILES:
                    extra_image_file = request.FILES[extra_image_key]
                    timestamp = int(time.time() * 1000)
                    extra_image_name = f"extra_image_{tour_source.id}/{timestamp}.jpg"
                    delete_s3_file(paso_source.image.name)
                    paso_source.image.save(extra_image_name, extra_image_file, save=False)
                else:
                    extra_image = request.POST.get(extra_image_key, None)
                    if extra_image:
                        extra_image = extra_image.replace("https://bucket-test-west2.s3.amazonaws.com", "")
                        paso_source.image = extra_image

                extra_latitude = float(request.POST.get(extra_latitude_key, 0))
                extra_longitude = float(request.POST.get(extra_longitude_key, 0))

                paso_source.latitude = extra_latitude if extra_latitude else 0.0
                paso_source.longitude = extra_longitude if extra_longitude else 0.0

                paso_source.description = extra_description
                paso_target_description = translate_text(extra_description, tour_source.idioma, tour_destino)
                paso_source.tittle = extra_tittle
                paso_target_tittle = translate_text(extra_tittle, tour_source.idioma, tour_destino)
                paso_source.step_number = extra_step_number
                paso_source.save()

                paso_target = Paso.objects.filter(tour=tour_target, step_number=extra_step_number).first()
                if not paso_target:
                    paso_target = Paso(tour=tour_target, step_number=extra_step_number)

                paso_target.audio = paso_source.audio
                paso_target.image = paso_source.image
                paso_target.latitude = paso_source.latitude
                paso_target.longitude = paso_source.longitude
                paso_target.description = paso_target_description
                paso_target.tittle = paso_target_tittle
                paso_target.step_number = paso_source.step_number
                paso_target.save()

            response_data = paso_source.as_dict()
            return Response(response_data)
        else:
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

def delete_s3_file(file_name):
    if not file_name:
        return
    s3 = boto3.client('s3', aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                      aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                      region_name=settings.AWS_S3_REGION_NAME )
    try:
        s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=file_name)
    except NoCredentialsError:
        print("No AWS credentials found")
    except PartialCredentialsError:
        print("Incomplete AWS credentials")
    except Exception as e:
        print(f"Unexpected error: {e}")

@csrf_exempt
@api_view(['POST'])
def translate_and_save_tour(request, tour_id):
    try:
        tour_es = get_object_or_404(Tour, pk=tour_id, idioma='es')
        tour_relation = TourRelation.objects.filter(tour_es=tour_es).first()
        if tour_relation and tour_relation.tour_en:
            return Response({
                'message': 'El tour ya existe en inglés', 
                'tour': {
                    'id': tour_relation.tour_en.id,
                    'latitude': tour_relation.tour_en.latitude,
                    'longitude': tour_relation.tour_en.longitude,
                    'titulo': tour_relation.tour_en.titulo,
                    'image': tour_relation.tour_en.imagen.url,
                    'audio': tour_relation.tour_en.audio.url,
                    'description': tour_relation.tour_en.descripcion,
                    'steps': [
                        {
                            'id': paso.id,
                            'image': paso.image.url if paso.image else None,
                            'audio': paso.audio.url if paso.audio else None,
                            'latitude': paso.latitude,
                            'longitude': paso.longitude,
                            'description': paso.description,
                            'tittle': paso.tittle
                        } for paso in Paso.objects.filter(tour=tour_relation.tour_en)
                    ]
                }
            }, status=200)
        tour_en = Tour()
        tour_en.user = tour_es.user
        tour_en.imagen = tour_es.imagen
        tour_en.audio = tour_es.audio
        tour_en.tipo_de_tour = tour_es.tipo_de_tour
        tour_en.idioma = 'en'
        tour_en.validado = False
        tour_en.descripcion = translate_text(tour_es.descripcion, tour_es.idioma)
        tour_en.titulo = translate_text(tour_es.titulo, tour_es.idioma)
        tour_en.latitude = tour_es.latitude
        tour_en.longitude = tour_es.longitude
        tour_en.save()

        # Crear y guardar la relación entre los tours
        tour_relation = TourRelation(tour_es=tour_es, tour_en=tour_en)
        tour_relation.save()

        # Traducir y guardar los pasos
        pasos_es = Paso.objects.filter(tour=tour_es)
        for paso_es in pasos_es:
            paso_en = Paso()
            paso_en.tour = tour_en
            paso_en.image = paso_es.image
            paso_en.audio = paso_es.audio
            paso_en.latitude = paso_es.latitude
            paso_en.longitude = paso_es.longitude
            paso_en.description = translate_text(paso_es.description, tour_es.idioma)
            paso_en.tittle = translate_text(paso_es.tittle, tour_es.idioma)
            paso_en.save()
        tour_data = {
            'id': tour_en.id,
            'latitude': tour_en.latitude,
            'longitude': tour_en.longitude,
            'titulo': tour_en.titulo,
            'image': tour_en.imagen.url,
            'audio': tour_en.audio.url,
            'description': tour_en.descripcion,
            'steps': [
                {
                    'id': paso.id,
                    'image': paso.image.url if paso.image else None,
                    'audio': paso.audio.url if paso.audio else None,
                    'latitude': paso.latitude, 
                    'longitude': paso.longitude,
                    'description': paso.description,
                    'tittle': paso.tittle
                } for paso in Paso.objects.filter(tour=tour_en)
            ]
        }

        return Response({'message': 'Tour traducido y guardado exitosamente', 'tour': tour_data}, status=200)
    except Tour.DoesNotExist:
        return Response({'error': 'Tour no encontrado'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    

def get_transcription_text(bucket_name, key):
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        raw_data = response['Body'].read()
        
        # Detectar la codificación
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        
        # Decodificar el texto usando la codificación detectada
        transcription_data = json.loads(raw_data.decode(encoding))
        transcription_text = transcription_data['results']['transcripts'][0]['transcript']
        return transcription_text
    except Exception as e:
        return f"Error retrieving transcription: {e}"



def normalize_filename(filename):
        # Normalize unicode characters
        nfkd_form = unicodedata.normalize('NFKD', filename)
        # Encode to ASCII bytes, ignore errors, then decode back to string
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
        # Replace any remaining invalid characters with '_'
        return re.sub(r'[^0-9a-zA-Z._-]', '_', only_ascii)

def wait_for_transcription_completion(transcribe_client, job_name):
    while True:
        time.sleep(30)        
        status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status['TranscriptionJob']['TranscriptionJobStatus']
        if job_status in ['COMPLETED', 'FAILED']:
            return status


def start_transcription_job(request, tour_id = 117):


    bucket_name = 'bucket-test-west2'
    region_name = 'eu-west-2' 


    tour_og = get_object_or_404(Tour, pk=tour_id)
    print(f"Tour Object: {tour_og}")
    print(f"User: {tour_og.user}")
    print(f"Idioma: {tour_og.idioma}")
    print(f"Audio: {tour_og.audio}")

    key = str(tour_og.audio)


    transcribe = boto3.client('transcribe', region_name=region_name)
    job_name_base = normalize_filename(f"{key.split('/')[-1].split('.')[0]}_{tour_og.user.id}_{tour_id}")
    job_name = f"{job_name_base}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    
    job_uri = f's3://{bucket_name}/{key}'
    output_key = f'transcriptions/{str(tour_id).zfill(5)}/{job_name}.json'
    langCode = 'es-ES' if tour_og.idioma == 'es' else tour_og.idioma

    try:
        response = transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat=key.split('.')[-1],
            LanguageCode=langCode,
            OutputBucketName=bucket_name,
            OutputKey=output_key
        )
    except ClientError as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    wait_for_transcription_completion(transcribe, job_name)
    transcription_file = io.StringIO()
    
    # Transcribir el audio del tour principal
    transcription_text = get_transcription_text(bucket_name, output_key)
    transcription_file.write(transcription_text)
    transcription_file.write('\n########################################################################\n')
    transcription_file.write('\n\n')
        #return JsonResponse(response)
    
    
    pasos_og = Paso.objects.filter(tour=tour_og)

    for paso in pasos_og:

            key = str( paso.audio)

            #transcribe = boto3.client('transcribe', region_name=region_name)
            job_name_base = normalize_filename(f"{key.split('/')[-1].split('.')[0]}_{tour_og.user.id}_{tour_id}")
            job_name = f"{job_name_base}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            
            job_uri = f's3://{bucket_name}/{key}'
            output_key = f'transcriptions/{str(tour_id).zfill(5)}/{str(paso.step_number).zfill(5)}/{job_name}.json'
            #langCode = 'es-ES' if tour_og.idioma == 'es' else tour_og.idioma
            try:
                response = transcribe.start_transcription_job(
                    TranscriptionJobName=job_name,
                    Media={'MediaFileUri': job_uri},
                    MediaFormat=key.split('.')[-1],
                    LanguageCode=langCode,
                    OutputBucketName=bucket_name,
                    OutputKey=output_key
                )
            except ClientError as e:
                return JsonResponse({'error': str(e)}, status=500)
            
            wait_for_transcription_completion(transcribe, job_name)
        # Obtener la transcripción del paso
            transcription_text = get_transcription_text(bucket_name, output_key)
            transcription_file.write(transcription_text)
            transcription_file.write('\n########################################################################\n')


    s3 = boto3.client('s3', region_name=region_name)
    transcription_file.seek(0)  # Volver al inicio del archivo
    s3.put_object(
        Bucket=bucket_name,
        Key=f'transcriptions/{str(tour_id).zfill(5)}/complete_transcription.txt',
        Body=transcription_file.read(),
        ContentType='text/plain'
    )

    return JsonResponse({'message': 'Transcription jobs were successfully'})


def get_complete_transcription(bucket_name, region_name, key):
    s3 = boto3.client('s3', region_name=region_name)
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        raw_data = response['Body'].read()
        # Asumimos que la codificación es UTF-8
        transcription_text = raw_data.decode('utf-8')
        return transcription_text
    except ClientError as e:
        return f"Error retrieving complete transcription: {e}"


def translate_text_aws(region_name, text, source_language_code, target_language_code):
    translate = boto3.client('translate', region_name=region_name)
    try:
        response = translate.translate_text(
            Text=text,
            SourceLanguageCode=source_language_code,
            TargetLanguageCode=target_language_code
        )
        return response['TranslatedText']
    except ClientError as e:
        return f"Error translating text: {e}"



def translate_transcription(request, tour_id=117):
    bucket_name = 'bucket-test-west2'
    region_name = 'eu-west-2' 
    key = f'transcriptions/{str(tour_id).zfill(5)}/complete_transcription.txt'

    relation = TourRelation.objects.filter(tour_es_id=tour_id).first()
    source_language_code = 'es'
    target_language_code = 'en'
    
    if not relation:
        relation = TourRelation.objects.filter(tour_en_id=tour_id).first()
        source_language_code = 'en'
        target_language_code = 'es'

    if not relation:
        return JsonResponse({'error': 'No relation found for the provided tour_id'}, status=404)
    
    if source_language_code == 'es':
        related_tour_id = relation.tour_en.id
    else:
        related_tour_id = relation.tour_es.id

    transcription_text = get_complete_transcription(bucket_name, region_name, key)

    if "Error" in transcription_text:
        return JsonResponse({'error': transcription_text}, status=500)

    sections = transcription_text.split('########################################################################')
    translated_sections = []

    for section in sections:
        if section.strip():
            translated_text = translate_text_aws(region_name, section.strip(), source_language_code, target_language_code)
            if "Error" in translated_text:
                return JsonResponse({'error': translated_text}, status=500)
            translated_sections.append(translated_text)
        else:
            translated_sections.append('')

    translated_text_with_hashes = '\n########################################################################\n'.join(translated_sections)

    output_key = f'transcriptions/{str(related_tour_id).zfill(5)}/complete_transcription_translated.txt'
    s3 = boto3.client('s3', region_name=region_name)
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=translated_text_with_hashes,
            ContentType='text/plain'
        )
    except ClientError as e:
        return JsonResponse({'error': f"Error uploading translated text: {e}"}, status=500)

    # Verificar que el archivo se haya subido correctamente
    try:
        response = s3.head_object(Bucket=bucket_name, Key=output_key)
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            return JsonResponse({'message': 'Translation of transcription job was successful', 'translated_text': translated_text_with_hashes})
        else:
            return JsonResponse({'error': 'Error verifying upload of translated text'}, status=500)
    except ClientError as e:
        return JsonResponse({'error': f"Error verifying upload of translated text: {e}"}, status=500)


def synthesize_speech(region_name, text, output_format='mp3', voice_id='Joanna'):
    polly = boto3.client('polly', region_name=region_name)
    try:
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat=output_format,
            VoiceId=voice_id
        )
        return response['AudioStream'].read()
    except ClientError as e:
        return f"Error synthesizing speech: {e}".encode('utf-8')
    

def convert_text_to_audio(request, tour_id=298):

    bucket_name = 'bucket-test-west2'
    region_name = 'eu-west-2' 
    key = f'transcriptions/{str(tour_id).zfill(5)}/complete_transcription_translated.txt'
    s3 = boto3.client('s3', region_name=region_name)

    transcription_text = get_complete_transcription(bucket_name, region_name, key)

    if "Error" in transcription_text:
        return JsonResponse({'error': transcription_text}, status=500) 

    sections = transcription_text.split('########################################################################')
    
    step = 0
    for section in sections:
        if section.strip():
            if "End Of File" in section:
                pass
            audio_stream = synthesize_speech(region_name, section)
            if isinstance(audio_stream, bytes) and audio_stream.startswith(b"Error"):
                return JsonResponse({'error': audio_stream.decode('utf-8')}, status=500)


            if step !=0:
                #output_key_audio = f'Tour_audio/{str(tour_id).zfill(5)}/{str(step).zfill(5)}/audio_traducido_{str(step).zfill(5)}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3'
                output_key_audio = f"Tour_audio/{str(tour_id).zfill(5)}/{str(step).zfill(5)}/audio_traducido_{str(step).zfill(5)}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"

                
                try:
                    paso = Paso.objects.get(tour=tour_id, step_number=step)
                    paso.audio = output_key_audio
                    paso.save()
                except Paso.DoesNotExist:
                    return JsonResponse({'error': 'Paso not found'}, status=404)
            else:
                output_key_audio = f"Tour_audio/{str(tour_id).zfill(5)}/audio_traducido_{str(step).zfill(5)}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
                try:
                    tour = Tour.objects.get(id=tour_id)
                    tour.audio = output_key_audio
                    tour.save()
                except Tour.DoesNotExist:
                    return JsonResponse({'error': 'Tour not found'}, status=404)
            try:
                s3.put_object(
                    Bucket=bucket_name,
                    Key=output_key_audio,
                    Body=audio_stream,
                    ContentType='audio/mpeg'
                )
            except ClientError as e:
                return JsonResponse({'error': f"Error uploading audio file: {e}"}, status=500)
            
            try:
                response = s3.head_object(Bucket=bucket_name, Key=output_key_audio)
                if response['ResponseMetadata']['HTTPStatusCode'] != 200:
                    return JsonResponse({'error': 'Error verifying upload of audio file'}, status=500)
                

            except ClientError as e:
                return JsonResponse({'error': f"Error verifying upload of audio file: {e}"}, status=500)
            
            

            step+=1


    return JsonResponse({'message': 'Speech synthesis of transcription job were successful'})




def copy_tour_images_to_s3():
    # Configuración de AWS S3
    bucket_name = 'bucket-test-west2'
    region_name = 'eu-west-2'
    source_bucket = 'bucket-test-west2'
    destination_bucket = 'bucket-test-west2'
    s3 = boto3.client('s3', region_name=region_name)
    base_path = 'Tour_imagen'

    # Obtener todos los tours
    tours = Tour.objects.all()

    with transaction.atomic():
        for tour in tours:

            # Crear la ruta del directorio del tour
            tour_dir = f"{base_path}/{str(tour.id).zfill(5)}"
            print(f"Procesando tour ID: {tour.id} - Directorio: {tour_dir}")


            # Copiar la imagen del tour, si existe
            if tour.imagen:
                source_key = str(tour.imagen)
                image_name = os.path.basename(source_key)
                destination_key = f"{tour_dir}/{image_name}"

                if tour.imagen.name != destination_key:
                    copy_source = {'Bucket': source_bucket, 'Key': source_key}
                    print(f"Copiando imagen del tour: {source_key} a {destination_key}")

                    # Comprobar si el objeto existe antes de copiarlo
                    try:
                        s3.head_object(Bucket=source_bucket, Key=source_key)
                        s3.copy_object(
                            CopySource=copy_source,
                            Bucket=destination_bucket,
                            Key=destination_key,
                            MetadataDirective='REPLACE',
                            Metadata={'x-amz-meta-copied': 'true'}  # Cambiar metadatos para permitir la copia
                        )

                        # Actualizar el path en la base de datos
                        tour.imagen.name = destination_key
                        tour.save()
                        print(f"Path actualizado en la DB para tour ID: {tour.id} - Nuevo path: {tour.imagen.name}")
                    except s3.exceptions.NoSuchKey:
                        print(f"El archivo {source_key} no existe en el bucket {source_bucket}.")
                    except Exception as e:
                        print(f"Error al copiar {source_key} a {destination_key}: {e}")
            
            # Obtener todos los pasos asociados al tour
            pasos = Paso.objects.filter(tour=tour)

            for paso in pasos:
                # Crear la ruta del directorio del paso
                paso_dir = f"{tour_dir}/{str(paso.step_number).zfill(5)}"
                print(f"Procesando paso ID: {paso.id} - Directorio: {paso_dir}")

                # Copiar la imagen del paso, si existe
                if paso.image:
                    source_key = str(paso.image)
                    image_name = os.path.basename(source_key)
                    destination_key = f"{paso_dir}/{image_name}"

                    if paso.image.name != destination_key:
                        copy_source = {'Bucket': source_bucket, 'Key': source_key}
                        print(f"Copiando imagen del paso: {source_key} a {destination_key}")

                        # Comprobar si el objeto existe antes de copiarlo
                        try:
                            s3.head_object(Bucket=source_bucket, Key=source_key)
                            s3.copy_object(
                                CopySource=copy_source,
                                Bucket=destination_bucket,
                                Key=destination_key,
                                MetadataDirective='REPLACE',
                                Metadata={'x-amz-meta-copied': 'true'}  # Cambiar metadatos para permitir la copia
                            )

                            # Actualizar el path en la base de datos
                            paso.image.name = destination_key
                            paso.save()
                            print(f"Path actualizado en la DB para paso ID: {paso.id} - Nuevo path: {paso.image.name}")
                        except s3.exceptions.NoSuchKey:
                            print(f"El archivo {source_key} no existe en el bucket {source_bucket}.")
                        except Exception as e:
                            print(f"Error al copiar {source_key} a {destination_key}: {e}")
                else:
                    print("ya esta modificado")
    print("llegamos")

    return "Imágenes copiadas y paths actualizados correctamente"



def copy_images_view(request):
    result = copy_tour_images_to_s3()
    return JsonResponse({'message': result})


def copy_tour_audio_to_s3():
    # Configuración de AWS S3
    bucket_name = 'bucket-test-west2'
    region_name = 'eu-west-2'
    source_bucket = 'bucket-test-west2'
    destination_bucket = 'bucket-test-west2'
    s3 = boto3.client('s3', region_name=region_name)
    base_path = 'Tour_audio'

    # Obtener todos los tours
    tours = Tour.objects.all()

    with transaction.atomic():
        for tour in tours:

            # Crear la ruta del directorio del tour
            tour_dir = f"{base_path}/{str(tour.id).zfill(5)}"
            print(f"Procesando tour ID: {tour.id} - Directorio: {tour_dir}")

            # Copiar el audio del tour, si existe
            if tour.audio:
                source_key = str(tour.audio)
                audio_name = os.path.basename(source_key)
                destination_key = f"{tour_dir}/{audio_name}"

                if tour.audio.name != destination_key:
                    copy_source = {'Bucket': source_bucket, 'Key': source_key}
                    print(f"Copiando audio del tour: {source_key} a {destination_key}")

                    # Comprobar si el objeto existe antes de copiarlo
                    try:
                        s3.head_object(Bucket=source_bucket, Key=source_key)
                        s3.copy_object(
                            CopySource=copy_source,
                            Bucket=destination_bucket,
                            Key=destination_key,
                            MetadataDirective='REPLACE',
                            Metadata={'x-amz-meta-copied': 'true'}  # Cambiar metadatos para permitir la copia
                        )

                        # Actualizar el path en la base de datos
                        tour.audio.name = destination_key
                        tour.save()
                        print(f"Path actualizado en la DB para tour ID: {tour.id} - Nuevo path: {tour.audio.name}")
                    except s3.exceptions.NoSuchKey:
                        print(f"El archivo {source_key} no existe en el bucket {source_bucket}.")
                    except Exception as e:
                        print(f"Error al copiar {source_key} a {destination_key}: {e}")

            # Obtener todos los pasos asociados al tour
            pasos = Paso.objects.filter(tour=tour)

            for paso in pasos:
                # Crear la ruta del directorio del paso
                paso_dir = f"{tour_dir}/{str(paso.step_number).zfill(5)}"
                print(f"Procesando paso ID: {paso.id} - Directorio: {paso_dir}")

                # Copiar el audio del paso, si existe
                if paso.audio:
                    source_key = str(paso.audio)
                    audio_name = os.path.basename(source_key)
                    destination_key = f"{paso_dir}/{audio_name}"

                    if paso.audio.name != destination_key:
                        copy_source = {'Bucket': source_bucket, 'Key': source_key}
                        print(f"Copiando audio del paso: {source_key} a {destination_key}")

                        # Comprobar si el objeto existe antes de copiarlo
                        try:
                            s3.head_object(Bucket=source_bucket, Key=source_key)
                            s3.copy_object(
                                CopySource=copy_source,
                                Bucket=destination_bucket,
                                Key=destination_key,
                                MetadataDirective='REPLACE',
                                Metadata={'x-amz-meta-copied': 'true'}  # Cambiar metadatos para permitir la copia
                            )

                            # Actualizar el path en la base de datos
                            paso.audio.name = destination_key
                            paso.save()
                            print(f"Path actualizado en la DB para paso ID: {paso.id} - Nuevo path: {paso.audio.name}")
                        except s3.exceptions.NoSuchKey:
                            print(f"El archivo {source_key} no existe en el bucket {source_bucket}.")
                        except Exception as e:
                            print(f"Error al copiar {source_key} a {destination_key}: {e}")
                else:
                    print("ya esta modificado")
    print("llegamos")

    return "Audios copiados y paths actualizados correctamente"

def copy_audios_view(request):
    result = copy_tour_audio_to_s3()
    return JsonResponse({'message': result})



def get_next_id():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT last_value + increment_by AS next_id
            FROM pg_sequences
            WHERE schemaname = 'public' AND sequencename = 'LTtApp_tour_id_seq';
        """)
        row = cursor.fetchone()
    return row[0] if row else None

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_validated_field(request, tour_id):
    tour = get_object_or_404(Tour, id=tour_id)

    if request.method == 'PUT':
        if not request.user.is_authenticated:
            return Response({'error': 'Usuario no autenticado'}, status=401)
        
        validado = request.data.get('validado', None)
        if validado is None:
            return Response({'error': 'El campo "validado" es requerido'}, status=400)
        
        tour.validado = validado
        tour.save()

        if validado:
            # Verificar si ya existe una relación entre los tours en español e inglés
            existing_relation = TourRelation.objects.filter(tour_es_id=tour.id).first()
            
            if not existing_relation:
                # Si no existe una relación, buscar por el tour en inglés relacionado
                existing_relation = TourRelation.objects.filter(tour_en_id=tour.id).first()
            
            if existing_relation:
                return Response({'message': 'El tour ya tiene una traducción existente, no se creó una nueva traducción.'}, status=200)

            # Crear la traducción solo si no existe una relación
            tour_destino = "en"

            tour_en = Tour(
                user=tour.user,
                imagen=tour.imagen,
                audio=tour.audio,
                tipo_de_tour=tour.tipo_de_tour,
                recorrido=tour.recorrido,
                duracion=tour.duracion,
                validado=True,
                descripcion=translate_text(tour.descripcion, tour.idioma, tour_destino),
                titulo=translate_text(tour.titulo, tour.idioma, tour_destino)
            )
            tour_en.save()

            for paso_es in Paso.objects.filter(tour=tour):
                paso_en = Paso(
                    tour=tour_en,
                    description=translate_text(paso_es.description, tour.idioma, tour_destino),
                    tittle=translate_text(paso_es.tittle, tour.idioma, tour_destino),
                    latitude=paso_es.latitude,
                    longitude=paso_es.longitude,
                    audio=paso_es.audio,
                    image=paso_es.image
                )
                paso_en.save()

            tour_relation = TourRelation(tour_es=tour if tour.idioma == "es" else tour_en,
                                         tour_en=tour_en if tour.idioma == "es" else tour)
            tour_relation.save()

        try:
            relation = TourRelation.objects.filter(tour_es_id=tour_id).first()
            if relation:
                if tour.idioma == "en":                
                    related_tour = relation.tour_en_id
                else:
                    related_tour = tour_id
            else:
                relation = TourRelation.objects.filter(tour_en_id=tour_id).first()
                if relation:
                    if tour.idioma == "es":             
                        related_tour = relation.tour_es_id
                    else:
                        related_tour = relation.tour_en_id
                else:
                    related_tour = tour_id

            tour_related = get_object_or_404(Tour, pk=related_tour)
            tour_related.validado = validado
            tour_related.save()
        except TourRelation.DoesNotExist:
            pass
        except Exception as e:
            return Response({'error': f"Excepción inesperada: {e}"}, status=500)

        return Response({'message': 'Campo "validado" actualizado correctamente en ambos tours y traducción creada si corresponde'}, status=200)
    else:
        return Response({'error': 'Método no permitido'}, status=405)

def start_keep_alive_timer():
    def insert_keep_alive():
        # Crear una nueva fila en la tabla KeepAlive
        KeepAlive.objects.create()
        print("Keep-alive row inserted automatically.")
        # Reprogramar la función para que se ejecute nuevamente después de 24 horas
        Timer(86400, insert_keep_alive).start()  # 86400 segundos = 24 horas
    insert_keep_alive

