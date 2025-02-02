# from django.apps import AppConfig
# from django.db.models.signals import post_migrate
# from threading import Timer

# class MyAppConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'LTtApp'  # Asegúrate de usar el nombre correcto de tu app

#     def ready(self):
#         from django.db.models.signals import post_migrate

#         def start_timer(sender, **kwargs):
#             def insert_keep_alive():
#                 from .models import KeepAlive
#                 KeepAlive.objects.create()
#                 print("Keep-alive row inserted successfully.")
#                 # Reprogramar el temporizador para que se ejecute cada 24 horas
#                 Timer(86400, insert_keep_alive).start()

#             # Iniciar el temporizador con un retardo inicial (5 segundos para pruebas)
#             Timer(5, insert_keep_alive).start()

#         # Conecta la señal post_migrate para asegurarte de que las migraciones se han aplicado
#         post_migrate.connect(start_timer, sender=self)
import threading
from django.apps import AppConfig
from django.conf import settings

# Variable global para evitar programar múltiples timers en el mismo proceso
TIMER_STARTED = False

def schedule_keep_alive():
    """Inserta una fila 'keep-alive' y reprograma el Timer para dentro de 24 horas."""
    from .models import KeepAlive
    KeepAlive.objects.create()
    print("Keep-alive row inserted successfully.")

    # Reprogramar el Timer para dentro de 24 horas (86400 seg)
    t = threading.Timer(86400, schedule_keep_alive)
    t.daemon = True  # Para que no impida que el proceso se cierre
    t.start()

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'LTtApp'  # Usa el nombre de tu aplicación correcto

    def ready(self):
        global TIMER_STARTED

        # Asegurarnos de no arrancar otro Timer si ya está en marcha
        if not TIMER_STARTED:
            TIMER_STARTED = True

            # Solo iniciamos el primer "disparo" con un retardo de 5 segundos
            t = threading.Timer(5, schedule_keep_alive)
            t.daemon = True
            t.start()