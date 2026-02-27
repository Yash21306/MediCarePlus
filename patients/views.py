from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import PatientForm
from .models import Patient
from django.db.models import Q
from django.views.generic import DetailView
from accounts.mixins import RoleRequiredMixin
from consultations.models import Consultation

@login_required
def add_patient(request):

    # Allow only Doctor & Pharmacist
    if request.user.role not in ['DOCTOR', 'PHARMACIST']:
        return redirect('home')

    if not request.user.is_approved:
        return redirect('pending')

    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.created_by = request.user
            patient.save()
            return redirect('home')  # we will improve this later
    else:
        form = PatientForm()

    return render(request, 'patients/add_patient.html', {'form': form})

@login_required
def patient_list(request):

    if request.user.role not in ['DOCTOR', 'PHARMACIST']:
        return redirect('home')

    if not request.user.is_approved:
        return redirect('pending')

    query = request.GET.get('q')

    patients = request.user.created_patients.all()

    if query:
        patients = patients.filter(
            Q(full_name__icontains=query) |
            Q(phone__icontains=query) |
            Q(medical_history__icontains=query) |
            Q(city__name__icontains=query)
        )

    context = {
        'patients': patients
    }

    return render(request, 'patients/patient_list.html', context) 

@login_required
def edit_patient(request, pk):

    patient = get_object_or_404(Patient, pk=pk)

    # Security check
    if patient.created_by != request.user:
        return redirect('patient_list')

    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            return redirect('patient_list')
    else:
        form = PatientForm(instance=patient)

    return render(request, 'patients/edit_patient.html', {'form': form})

@login_required
def delete_patient(request, pk):

    patient = get_object_or_404(Patient, pk=pk)

    # Security check
    if patient.created_by != request.user:
        return redirect('patient_list')

    if request.method == 'POST':
        patient.delete()
        return redirect('patient_list')

    return render(request, 'patients/delete_patient.html', {'patient': patient})

class PatientDetailView(RoleRequiredMixin, DetailView):
    model = Patient
    template_name = 'patients/patient_detail.html'
    context_object_name = 'patient'

    allowed_roles = ['DOCTOR', 'PHARMACIST']

    def get_queryset(self):
        # Security: Only allow users to see their own created patients
        return Patient.objects.filter(created_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['consultations'] = Consultation.objects.filter(
            patient=self.object
        )
        return context