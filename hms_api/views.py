from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler

from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.db import IntegrityError

from .serializers import (
    UserRegistrationSerializer, PatientSerializer, MedicalRecordSerializer
)
from .models import Profile, Patient, MedicalRecord
from .permissions import IsDoctor, IsAdmin, IsOwnerOrAdmin, IsPatientRecordOwnerOrAdmin


def custom_exception_handler(exc, context):
    # Call DRF's default exception handler first, to get the standard error response.
    response = drf_exception_handler(exc, context)

    # Now add the HTTP status code to the response data.
    if response is not None:
        if isinstance(exc, APIException):
            response.data['status_code'] = response.status_code
        else:
            # For non-APIException errors (e.g., Django's Http404),
            # provide a generic error message and status.
            response.data = {
                'detail': 'An unexpected error occurred.',
                'status_code': response.status_code
            }
    elif isinstance(exc, IntegrityError):
        # Handle database integrity errors specifically
        response = Response(
            {'detail': 'A database integrity error occurred. This might be due to duplicate entry or related data issues.',
             'status_code': status.HTTP_400_BAD_REQUEST},
            status=status.HTTP_400_BAD_REQUEST
        )
    return response


# --- Authentication Views ---

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    Registers a new user (doctor or admin).
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'User registered successfully. Please login to get your token.',
                'user_id': user.id,
                'username': user.username,
                'role': user.profile.role
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({'detail': 'Username or email already exists.', 'status_code': status.HTTP_400_BAD_REQUEST},
                            status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Logs in a user and returns an authentication token.
    """
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(request, username=username, password=password)

    if user is not None:
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'user_id': user.id,
            'username': user.username,
            'role': user.profile.role
        }, status=status.HTTP_200_OK)
    else:
        return Response({'detail': 'Invalid credentials', 'status_code': status.HTTP_401_UNAUTHORIZED},
                        status=status.HTTP_401_UNAUTHORIZED)


# --- Patient Views ---

class PatientListCreateView(generics.ListCreateAPIView):
    """
    API endpoint for doctors to create new patients and list their own patients.
    Admins can list all patients.
    """
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated, (IsDoctor | IsAdmin)]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or (hasattr(user, 'profile') and user.profile.role == 'admin'):
            return Patient.objects.all()
        # Doctors can only see patients they created
        return Patient.objects.filter(created_by=user)

    def perform_create(self, serializer):
        # Ensure only doctors can create patients
        if not (self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'doctor')):
            raise APIException("Only doctors can create patients.", code=status.HTTP_403_FORBIDDEN)
        serializer.save(created_by=self.request.user)


class PatientDetailView(generics.RetrieveAPIView):
    """
    API endpoint for doctors to view details of their own patients.
    Admins can view any patient.
    """
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin] # Ensures doctor can only view their own

# --- Medical Record Views ---

class MedicalRecordAddView(generics.CreateAPIView):
    """
    API endpoint for doctors to add medical records to their patients.
    """
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated, IsDoctor] # Only doctors can add records

    def perform_create(self, serializer):
        patient_id = self.request.data.get('patient')
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            raise APIException("Patient not found.", code=status.HTTP_404_NOT_FOUND)

        # Ensure the doctor is adding a record for their own patient
        if not (self.request.user.is_superuser or (hasattr(self.request.user, 'profile') and self.request.user.profile.role == 'admin')):
            if patient.created_by != self.request.user:
                raise APIException("You can only add medical records to your own patients.", code=status.HTTP_403_FORBIDDEN)

        serializer.save(patient=patient)


class PatientMedicalRecordListView(generics.ListAPIView):
    """
    API endpoint to view all medical records for a specific patient.
    Doctors can only view records for their own patients.
    Admins can view records for any patient.
    """
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated, IsPatientRecordOwnerOrAdmin] # Custom permission to check patient ownership

    def get_queryset(self):
        patient_id = self.kwargs['pk']
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            raise APIException("Patient not found.", code=status.HTTP_404_NOT_FOUND)

        # Check object level permission for the patient
        self.check_object_permissions(self.request, patient)

        return MedicalRecord.objects.filter(patient=patient)