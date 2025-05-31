from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, Patient, MedicalRecord

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('role',)

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    role = serializers.ChoiceField(choices=Profile.USER_ROLES, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'role')
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role')
        validated_data.pop('password2') # Remove password2
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        Profile.objects.create(user=user, role=role)
        return user


class PatientSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True) # Display creator's username/email

    class Meta:
        model = Patient
        fields = ('id', 'name', 'age', 'gender', 'address', 'created_by', 'created_at')
        read_only_fields = ('created_at',)

    def validate_age(self, value):
        if value <= 0:
            raise serializers.ValidationError("Age must be greater than 0.")
        return value

class MedicalRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.name', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = ('id', 'patient', 'patient_name', 'symptoms', 'diagnosis', 'treatment', 'created_at')
        read_only_fields = ('created_at',)

    def validate_patient(self, value):
        # Ensure the patient exists and belongs to the current doctor if not an admin
        request = self.context.get('request')
        if request and request.user and not request.user.is_superuser and request.user.profile.role != 'admin':
            if not value.created_by == request.user:
                raise serializers.ValidationError("You can only add medical records to your own patients.")
        return value