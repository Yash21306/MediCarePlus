# from django.shortcuts import render
# from django.views.generic import DetailView
from django.views.generic import CreateView, DetailView
# from django.shortcuts import get_object_or_404
from django.urls import reverse
from accounts.mixins import RoleRequiredMixin
from patients.models import Patient
from .models import Consultation
from .forms import ConsultationForm, DiagnosisFormSet, PrescriptionForm, PrescriptionItemFormSet
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction

class ConsultationCreateView(RoleRequiredMixin, CreateView):
    model = Consultation
    form_class = ConsultationForm
    template_name = 'consultations/consultation_form.html'

    allowed_roles = ['DOCTOR']

    def dispatch(self, request, *args, **kwargs):
        self.patient = get_object_or_404(Patient, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.patient = self.patient
        form.instance.doctor = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('patient_detail', args=[self.patient.pk])
    
class ConsultationDetailView(RoleRequiredMixin, DetailView):
    model = Consultation
    template_name = 'consultations/consultation_detail.html'
    context_object_name = 'consultation'

    allowed_roles = ['DOCTOR', 'PHARMACIST']

    def get_queryset(self):
        # Only allow access to consultations of patients created by user
        return Consultation.objects.filter(
            patient__created_by=self.request.user
        )    
    
class AddDiagnosisView(RoleRequiredMixin, View):
    allowed_roles = ['DOCTOR']

    def get(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)

        if consultation.status != "OPEN":
            return redirect('consultation_detail', pk=pk)

        formset = DiagnosisFormSet(instance=consultation)

        return render(request, 'consultations/add_diagnosis.html', {
            'consultation': consultation,
            'formset': formset
        })

    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)

        if consultation.status != "OPEN":
            return redirect('consultation_detail', pk=pk)

        formset = DiagnosisFormSet(request.POST, instance=consultation)

        if formset.is_valid():
            formset.save()
            return redirect('consultation_detail', pk=pk)

        return render(request, 'consultations/add_diagnosis.html', {
            'consultation': consultation,
            'formset': formset
        })    
    
class AddPrescriptionView(RoleRequiredMixin, View):
    allowed_roles = ['DOCTOR']

    def get(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)

        if consultation.status != "OPEN":
            return redirect('consultation_detail', pk=pk)

        form = PrescriptionForm()
        formset = PrescriptionItemFormSet()

        return render(request, 'consultations/add_prescription.html', {
            'consultation': consultation,
            'form': form,
            'formset': formset
        })

    @transaction.atomic
    def post(self, request, pk):
        consultation = get_object_or_404(Consultation, pk=pk)

        if consultation.status != "OPEN":
            return redirect('consultation_detail', pk=pk)

        form = PrescriptionForm(request.POST)
        formset = PrescriptionItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            prescription = form.save(commit=False)
            prescription.consultation = consultation
            prescription.save()

            items = formset.save(commit=False)
            for item in items:
                item.prescription = prescription
                item.save()

            return redirect('consultation_detail', pk=pk)

        return render(request, 'consultations/add_prescription.html', {
            'consultation': consultation,
            'form': form,
            'formset': formset
        })    