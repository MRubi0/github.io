from django.urls import path
from . import views

app_name = 'LTtApp' # It's good practice to have an app_name for namespacing

# Existing urlpatterns
urlpatterns = [
    path('login/', views.login_view, name='login'), # Assuming this is for web, not API
    path('register/', views.register_view, name='register'), # Assuming this is for web, not API
    path('', views.index, name='index'),
    path('index/', views.index, name='index_explicit'), # Added explicit name for clarity

    # Traditional Django views (non-API, if any beyond index/auth)
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile_page'), # Web page for editing profile
    path('registration/success/', views.registration_success, name='registration_success'),
    path('tours/<int:tour_id>/', views.tour_detail, name='tour_detail_page'), # Web page
    path('tours/<int:tour_id>/directions/', views.directions, name='directions_page'), # Web page
    path('tours/map/', views.map_view, name='map_page'), # Web page for map, if get_tour_data is fixed
    path('tours/debug/<int:tour_id>/', views.debug_tour, name='debug_tour'), # Debug view
    path('tours/step/<int:tour_id>/<int:step_id>/', views.step_detail, name='step_detail_page'), # Web page
    path('tours/all/', views.all_tours, name='all_tours_page'), # Web page
    path('custom-tours/', views.custom_tours_page, name='custom_tours_page'),
]

# API specific urlpatterns
api_urlpatterns = [
    # Refactored views
    path('api/user-tours/', views.list_user_tours, name='list_user_tours'),
    path('api/tours/latest-by-category/', views.list_latest_tours_by_category, name='list_latest_tours_by_category'),
    path('api/tours/random-by-category/', views.list_random_tours_by_category, name='list_random_tours_by_category'),
    path('api/tours/distance/', views.retrieve_tour_distance, name='retrieve_tour_distance'), # Expects tour_id, language, lat, lon as query params
    path('api/tours/all/', views.list_all_tours_sorted, name='list_all_tours_sorted'), # Expects language, optional lat/lon, page, page_size
    path('api/tours/<int:tour_id>/<str:language>/details/', views.retrieve_tour_with_steps, name='retrieve_tour_with_steps'),
    path('api/users/profile/', views.retrieve_user_profile, name='retrieve_user_profile'), # Expects user_id as query param

    # Other existing API views (using assumed or existing names)
    path('api/checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('api/test-auth/', views.test_auth, name='test_auth'),
    path('api/csrf-token/', views.csrf_token_view, name='csrf_token'),
    path('api/tours/upload/', views.upload_tours, name='upload_tours'),
    path('api/survey/upload/', views.upload_encuesta, name='upload_encuesta'),

    # get_nearest_tours might be superseded by list_all_tours_sorted with location,
    # but keeping its specific "one per category" logic if distinct.
    path('api/tours/nearest-per-category/', views.get_nearest_tours, name='get_nearest_tours'),

    path('api/tours/<int:tour_id>/locations/', views.get_tour_locations, name='get_tour_locations'),
    path('api/tours/record/', views.create_tour_record, name='create_tour_record'),

    # get_user_tour_records - name implies it gets records of tours a user took, but fetches tours created by user + their ratings
    # This might need further clarification or renaming in views.py itself. For now, mapping as is.
    path('api/users/created-tours-with-ratings/', views.get_user_tour_records, name='get_user_created_tours_with_ratings'),

    path('api/routes/', views.get_routes, name='get_routes'),
    path('api/ratings/create/', views.crear_valoracion, name='crear_valoracion'),
    path('api/tours/<int:tour_id>/average-rating/', views.media_valoracion_tour, name='media_valoracion_tour'),
    path('api/profile/update/', views.update_profile, name='update_profile_api'), # API endpoint for profile update
    path('api/profile/upload-image/', views.upload_profile_image, name='upload_profile_image_api'),

    path('api/tours/<int:tour_id>/edit/<int:size>/', views.edit_tour, name='edit_tour_api'), # size in URL is unusual
    path('api/tours/<int:tour_id>/translate-and-save/', views.translate_and_save_tour, name='translate_and_save_tour'),

    # AWS related tasks - consider if these should be user-facing APIs or internal tasks
    path('api/tours/<int:tour_id>/transcribe/start/', views.start_transcription_job, name='start_transcription_job'),
    path('api/tours/<int:tour_id>/transcribe/translate/', views.translate_transcription, name='translate_transcription'),
    path('api/tours/<int:tour_id>/synthesize-audio/', views.convert_text_to_audio, name='convert_text_to_audio'),

    # Admin/Utility - should be protected
    path('api/admin/copy-images/', views.copy_images_view, name='copy_images_view'),
    path('api/admin/copy-audios/', views.copy_audios_view, name='copy_audios_view'),
    path('api/tours/<int:tour_id>/validate/', views.update_validated_field, name='update_validated_field'),

    # Note: Some views like login_view and register_view are in the main urlpatterns.
    # Depending on whether they are part of a DRF setup (e.g. using DRF's LoginView/RegisterView)
    # or traditional Django form views, they might also belong in api_urlpatterns or stay as is.
    # For now, leaving them in urlpatterns as they were.
]

# Combine all urlpatterns
urlpatterns += api_urlpatterns
