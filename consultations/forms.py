from django import forms
# from .models import Consultation
from django.forms import inlineformset_factory
from .models import Diagnosis, Consultation, Prescription, PrescriptionItem

class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        exclude = ['visit_number', 'doctor', 'patient']
        widgets = {
            'consultation_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'follow_up_date': forms.DateInput(attrs={'type': 'date'}),
        }

class DiagnosisForm(forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ['name', 'description', 'is_primary']


DiagnosisFormSet = inlineformset_factory(
    Consultation,
    Diagnosis,
    form=DiagnosisForm,
    extra=3,   # show 3 empty rows initially
    can_delete=False
)        

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['notes']


PrescriptionItemFormSet = inlineformset_factory(
    Prescription,
    PrescriptionItem,
    fields=[
        'medicine',
        'dosage',
        'frequency',
        'duration_days',
        'quantity_prescribed',
        'instructions'
    ],
    extra=3,
    can_delete=False
)