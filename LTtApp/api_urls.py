# LTtApp/api_urls.py
from django.urls import path
from LTtApp import views
from rest_framework_simplejwt.views import TokenRefreshView
from LTtApp.views import CustomTokenObtainPairView

urlpatterns = [
    # ---------------------------------------------------------------- AUTH
    path('token/',            CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/',    TokenRefreshView.as_view(),    name='token_refresh'),
    path('test_auth/',        views.test_auth,               name='test_auth'),
    path('verify-email/<uuid:token>/', views.verify_email,  name='verify_email'),

    # ---------------------------------------------------------------- USER
    path('register/',                     views.register_view),           # POST JSON
    path('login/',                        views.login_view),              # POST form-data
    path('profile/update/',               views.update_profile),          # PUT/POST form-data
    path('profile/upload_image/',         views.upload_profile_image),    # POST file
    path('profile/get/',                  views.search_user_by_id),
    path('get_user_tours',                views.get_user_tours),
    path('create-tour-record/',           views.create_tour_record),
    path('get_user_tour_records',         views.get_user_tour_records),

    # ---------------------------------------------------------------- TOURS (listado y detalle)
    path('get_latest_tours/',             views.get_latest_tours),
    path('get_random_tours/',             views.get_random_tours),
    path('get_nearest_tours/',            views.get_nearest_tours),
    path('get_nearest_tours_all/',        views.get_nearest_tours_all),
    path('get_tour_distance/',            views.get_tour_distance),
    path('get_tour_with_steps/<int:tour_id>/<str:languaje>/',
                                         views.get_tour_with_steps),
    path('tour-locations/<int:tour_id>/', views.get_tour_locations),
    path('tours/<int:tour_id>/validado/', views.update_validated_field),

    # ---------------------------------------------------------------- TOURS (creación / edición)
    path('profile/upload_tour/',          views.upload_tours),
    path('edit_tour/<int:tour_id>/<int:size>/', views.edit_tour),
    path('translate_and_save_tour/<int:tour_id>/',
                                         views.translate_and_save_tour),

    # ---------------------------------------------------------------- PASOS
    path('tour/<int:tour_id>/step/<int:step_id>/',  views.next_step),

    # ---------------------------------------------------------------- VALORACIONES / ENCUESTA
    path('crear_valoracion',              views.crear_valoracion),
    path('encuesta/',                     views.upload_encuesta),
    path('tour/<int:tour_id>/media-valoracion/', views.media_valoracion_tour),
    path('tour/<int:tour_id>/valoraciones/', views.get_valoraciones_tour),

    # ---------------------------------------------------------------- RUTAS & MAPAS
    path('get_routes',                    views.get_routes),
    path('csrf-token/',                   views.csrf_token_view),

    # ---------------------------------------------------------------- S3 / IA / AUDIO – solo si las usas vía front
    path('start_transcription_job/<int:tour_id>/', views.start_transcription_job),
    path('translate_transcription/<int:tour_id>/', views.translate_transcription),
    path('convert_text_to_audio/<int:tour_id>/',  views.convert_text_to_audio),
    path('copy-audios/',                  views.copy_audios_view),
    path('copy-images/',                  views.copy_images_view),

    # ---------------------------------------------------------------- CHECKOUT
    path('create-checkout-session/',      views.create_checkout_session),

    # ---------------------------------------------------------------- ADMIN
    path('admin/stats/',                              views.admin_stats),
    path('admin/pending_tours/',                      views.admin_pending_tours),
    path('admin/published_tours/',                    views.admin_published_tours),
    path('admin/tours/<int:tour_id>/delete/',         views.admin_delete_tour),
    path('admin/users/',                              views.admin_users),
    path('admin/users/<int:user_id>/toggle_active/',  views.admin_toggle_user_active),
]
