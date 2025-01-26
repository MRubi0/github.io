from django.apps import AppConfig
from django.db.models.signals import post_migrate
from threading import Timer

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'LTtApp'  # Asegúrate de usar el nombre correcto de tu app

    def ready(self):
        from django.db.models.signals import post_migrate

        def start_timer(sender, **kwargs):
            def insert_keep_alive():
                from .models import KeepAlive
                KeepAlive.objects.create()
                print("Keep-alive row inserted successfully.")
                # Reprogramar el temporizador para que se ejecute cada 24 horas
                Timer(86400, insert_keep_alive).start()

            # Iniciar el temporizador con un retardo inicial (5 segundos para pruebas)
            Timer(5, insert_keep_alive).start()

        # Conecta la señal post_migrate para asegurarte de que las migraciones se han aplicado
        post_migrate.connect(start_timer, sender=self)
