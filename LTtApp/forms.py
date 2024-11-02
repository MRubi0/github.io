from django import forms
from .models import Guide, AudioFile, ImageFile, Location, CustomUser, Tour, Paso, Valoracion
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import UserChangeForm
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

class GuideForm(forms.ModelForm):
    class Meta:
        model = Guide
        fields = ('title', 'description',) # y otros campos relevantes

class AudioFileForm(forms.ModelForm):
    class Meta:
        model = AudioFile
        fields = ('audio_file',)

class ImageFileForm(forms.ModelForm):
    class Meta:
        model = ImageFile
        fields = ('image_file',)

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'latitude', 'longitude']

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    avatar = forms.ImageField(required=False)
    bio = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "password1", "password2", "avatar", "bio")

    def save(self, commit=True):
        user = super().save(commit=False) 
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.avatar = self.cleaned_data["avatar"]
        user.bio = self.cleaned_data["bio"]
        if commit:
            user.save()
        return user

class EditProfileForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'avatar', 'bio')

class TourForm(forms.ModelForm):
    class Meta:
        model = Tour
        fields = ['titulo', 'imagen', 'descripcion', 'audio', 'latitude', 'longitude', 'tipo_de_tour', 'duracion', 'recorrido', 'original']


class PasoForm(forms.ModelForm):
    class Meta:
        model = Paso
        fields = ['image', 'audio', 'latitude', 'longitude', 'description']


class ValoracionForm(forms.ModelForm):
    class Meta:
        model = Valoracion
        fields = ['puntuacion', 'comentario']


class EncuestaForm(forms.Form):
    pregunta1 = forms.CharField(label='1. Edad', max_length=100)
    pregunta2 = forms.ChoiceField(
        label='2. Género', 
        choices=[
            ('Masculino', 'Masculino'), 
            ('Femenino', 'Femenino'), 
            ('Prefiero no decirlo', 'Prefiero no decirlo')
        ]
    )
    pregunta3 = forms.ChoiceField(
        label='3. Nacionalidad', 
        choices=[
            ('Española', 'Española'), 
            ('Otra', 'Otra')
        ], 
        widget=forms.RadioSelect
    )
    subpregunta3_1 = forms.CharField(label='Si es otra, ¿Cuál?', max_length=100, required=False)
    pregunta4 = forms.ChoiceField(
        label='4. ¿Cuántos viajes haces al año?', 
        choices=[
            ('Menos de 3', 'Menos de 3'), 
            ('Entre 3 y 5', 'Entre 3 y 5'), 
            ('Más de 5', 'Más de 5')
        ], 
        widget=forms.RadioSelect
    )
    pregunta5 = forms.ChoiceField(
        label='5. ¿Y cuántos tours haces al año?', 
        choices=[
            ('Menos de 3', 'Menos de 3'), 
            ('Entre 3 y 5', 'Entre 3 y 5'), 
            ('Más de 5', 'Más de 5')
        ], 
        widget=forms.RadioSelect
    )
    pregunta6 = forms.ChoiceField(
        label='6. Valora el tour realizado:', 
        choices=[
            ('Muy poco satisfecho', 'Muy poco satisfecho'), 
            ('Poco satisfecho', 'Poco satisfecho'), 
            ('Normal', 'Normal'), 
            ('Satisfecho', 'Satisfecho'), 
            ('Muy satisfecho', 'Muy satisfecho')
        ], 
        widget=forms.RadioSelect
    )
    pregunta7 = forms.ChoiceField(
        label='7. Valora el contenido del tour realizado:', 
        choices=[
            ('Muy poco satisfecho', 'Muy poco satisfecho'), 
            ('Poco satisfecho', 'Poco satisfecho'), 
            ('Normal', 'Normal'), 
            ('Satisfecho', 'Satisfecho'), 
            ('Muy satisfecho', 'Muy satisfecho')
        ]
    )
    subpregunta7 = forms.CharField(label='a. ¿Qué otro tipo de contenido te gustaría encontrar en la App?', widget=forms.Textarea, required=False)
    pregunta8 = forms.ChoiceField(
        label='8. Valora el formato en el que se ha presentado el tour:', 
        choices=[
            ('Muy poco satisfecho', 'Muy poco satisfecho'), 
            ('Poco satisfecho', 'Poco satisfecho'), 
            ('Normal', 'Normal'), 
            ('Satisfecho', 'Satisfecho'), 
            ('Muy satisfecho', 'Muy satisfecho')
        ]
    )
    subpregunta8_1 = forms.CharField(label='¿Qué es lo que más te ha gustado?', widget=forms.Textarea, required=False)
    subpregunta8_2 = forms.CharField(label='¿Y lo que menos?', widget=forms.Textarea, required=False)
    pregunta9 = forms.ChoiceField(
        label='9. Valora la duración del tour:', 
        choices=[
            ('Largo', 'Largo'), 
            ('Adecuado', 'Adecuado'), 
            ('Corto', 'Corto')
        ], 
        widget=forms.RadioSelect
    )
    pregunta10 = forms.CharField(label='10. ¿Cuál crees que sería la duración óptima para este tipo de tours?', max_length=100, required=False)
    pregunta11 = forms.ChoiceField(
        label='11. ¿El producto te ayuda a lograr tus objetivos?', 
        choices=[
            ('Sí', 'Sí'), 
            ('No', 'No')
        ], 
        widget=forms.RadioSelect
    )
    pregunta12 = forms.CharField(label='12. ¿Qué características del producto consideras más valiosas?', widget=forms.Textarea, max_length=100, required=False)
    pregunta13 = forms.CharField(label='13. ¿Y la menos valiosa?', widget=forms.Textarea, max_length=100, required=False)
    pregunta14 = forms.CharField(label='14. ¿Qué puntos de fricción has encontrado al usar el producto? Si pudieras, ¿qué mejorarías?', widget=forms.Textarea, max_length=100, required=False)
    pregunta15 = forms.ChoiceField(
        label='15. ¿Utilizarías el producto en tus próximas vacaciones?', 
        choices=[
            ('Sí', 'Sí'), 
            ('No', 'No')
        ], 
        widget=forms.RadioSelect
    )
    pregunta16 = forms.ChoiceField(
        label='16. ¿Qué tan probable es que recomiendes "Let\'s Tour Tec" a otras personas?', 
        choices=[
            ('Muy improbable', 'Muy improbable'), 
            ('Improbable', 'Improbable'), 
            ('Normal', 'Normal'), 
            ('Probable', 'Probable'), 
            ('Muy probable', 'Muy probable')
        ], 
        widget=forms.RadioSelect
    )
    pregunta17 = forms.ChoiceField(
        label='17. ¿Qué probabilidad hay de que vuelvas a realizar un tour con "Let\'s Tour Tec"?', 
        choices=[
            ('Muy improbable', 'Muy improbable'), 
            ('Improbable', 'Improbable'), 
            ('Normal', 'Normal'), 
            ('Probable', 'Probable'), 
            ('Muy probable', 'Muy probable')
        ], 
        widget=forms.RadioSelect
    )
    pregunta18 = forms.ChoiceField(
        label='18. ¿Crees que la flexibilidad de horarios e idioma es una ventaja competitiva respecto a los tours convencionales?', 
        choices=[
            ('Sí', 'Sí'), 
            ('No', 'No')
        ], 
        widget=forms.RadioSelect
    )
    pregunta19 = forms.ChoiceField(
        label='19. ¿Cuál crees que es la mejor manera de tener acceso a este tipo de tours?', 
        choices=[
            ('Pagar antes de realizar el tour una cantidad fija', 'Pagar antes de realizar el tour una cantidad fija'), 
            ('Pagar al final del tour la cantidad que consideres', 'Pagar al final del tour la cantidad que consideres'), 
            ('Poder tener otras opciones de pagar el tour. Por ejemplo, viendo anuncios.', 'Poder tener otras opciones de pagar el tour. Por ejemplo, viendo anuncios.'), 
            ('Pagar una suscripción mensual', 'Pagar una suscripción mensual')
        ], 
        widget=forms.RadioSelect
    )
    subpregunta19_1 = forms.CharField(label='Si es otro, ¿Cual?', widget=forms.Textarea, required=False)
    pregunta20 = forms.CharField(label='20. ¿Cuánto estarías dispuesto a pagar por uno de estos tours?', max_length=100,  required=False)
    pregunta21 = forms.ChoiceField(
        label='21. ¿Le gustaría que la aplicación tuviera formato red social para poder compartir o encontrar los viajes y tours que mejor se adaptan a su estilo de vida?', 
        choices=[
            ('Sí', 'Sí'), 
            ('No', 'No')
        ], 
        widget=forms.RadioSelect
    )
    pregunta22 = forms.EmailField(label='22. Si quisieras mantenerte al tanto de nuestras actualizaciones, nos encantaría disponer de tu correo electrónico:', required=False)
    id = forms.CharField( max_length=100,  required=False)
