from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from LTtApp.views import edit_tour, register_view,  test_auth
from LTtApp.views import upload_tours, crear_valoracion
from LTtApp import views
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from LTtApp.views import create_checkout_session
#app_name = 'LTtApp'

urlpatterns = [

    # TODO: toda la lógica JSON está centralizada aquí
    path('api/', include('LTtApp.api_urls')),          # <-- único include para la API
    #path('', include('LTtApp.urls')),

    # ---------------------------------------------------------------- ADMIN
    path('admin/', admin.site.urls),

    # ---------------------------------------------------------------- AUTENTICACIÓN (HTML)
    # Usa tu propia vista o las genéricas de Django según necesites
    path('login/',  views.login_view,        name='login'),      # si usas form propio
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', register_view,   name='register'),

    # ---------------------------------------------------------------- PÁGINAS / TEMPLATES
    path('', include('LTtApp.urls')),                       # index, etc. (HTML)
    path('profile/',            views.profile,          name='profile'),
    path('profile/edit/',       views.edit_profile,     name='edit_profile'),
    path('profile/get/',        views.search_user_by_id),
    path('profile/update/',               views.update_profile),          
    path('profile/upload_image/',         views.upload_profile_image),   

    path('tour/<int:tour_id>/', views.tour_detail,      name='tour_detail'),
    path('directions/<int:tour_id>/', views.directions, name='directions'),
    path('api/tour/<int:tour_id>/step/<int:step_id>/', views.next_step, name='next_step'),

    path('step/<int:tour_id>/<int:step_id>/', views.next_step, name='next_step'),
    path('all_tours/',          views.all_tours,        name='all_tours'),
    path('custom_tours_page/',  views.custom_tours_page,name='custom_tours_page'),
    path('registration_success/', views.registration_success, name='registration_success'),
    
    path('ruta-para-actualizar-perfil', views.update_profile, name='update_profile'),
    path('ruta-para-actualizar-imagen', views.upload_profile_image, name='upload_profile_image'),

    path('accounts/', include('django.contrib.auth.urls')),

    path('csrf-token/', views.csrf_token_view, name='csrf_token')
    

    ]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

#else:
    #urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
