from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User
from hms_api.models import Patient, MedicalRecord, Profile
from rest_framework.authtoken.models import Token

class AuthTests(APITestCase):
    def setUp(self):
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')

    def test_signup_doctor(self):
        """
        Ensure we can create a new doctor user.
        """
        data = {
            'username': 'testdoctor',
            'email': 'doctor@example.com',
            'password': 'password123',
            'password2': 'password123',
            'role': 'doctor'
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testdoctor')
        self.assertEqual(User.objects.get().profile.role, 'doctor')

    def test_signup_admin(self):
        """
        Ensure we can create a new admin user.
        """
        data = {
            'username': 'testadmin',
            'email': 'admin@example.com',
            'password': 'password123',
            'password2': 'password123',
            'role': 'admin'
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(User.objects.count(), 1) # Only one user at this point if run alone
        self.assertEqual(User.objects.get().username, 'testadmin')
        self.assertEqual(User.objects.get().profile.role, 'admin')

    def test_signup_mismatched_passwords(self):
        """
        Ensure signup fails with mismatched passwords.
        """
        data = {
            'username': 'failuser',
            'email': 'fail@example.com',
            'password': 'password123',
            'password2': 'wrongpass',
            'role': 'doctor'
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertEqual(User.objects.count(), 0)

    def test_signup_duplicate_username(self):
        """
        Ensure signup fails with a duplicate username.
        """
        self.client.post(self.signup_url, {
            'username': 'testuser', 'email': 'user1@example.com',
            'password': 'password123', 'password2': 'password123', 'role': 'doctor'
        }, format='json')
        data = {
            'username': 'testuser', 'email': 'user2@example.com',
            'password': 'password123', 'password2': 'password123', 'role': 'doctor'
        }
        response = self.client.post(self.signup_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'Username or email already exists.')

    def test_login_success(self):
        """
        Ensure a registered user can log in and obtain a token.
        """
        # First, register a user
        self.client.post(self.signup_url, {
            'username': 'loginuser', 'email': 'login@example.com',
            'password': 'securepassword', 'password2': 'securepassword', 'role': 'doctor'
        }, format='json')

        # Then, attempt to log in
        response = self.client.post(self.login_url, {
            'username': 'loginuser', 'password': 'securepassword'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('username', response.data)
        self.assertEqual(response.data['username'], 'loginuser')
        self.assertIn('role', response.data)
        self.assertEqual(response.data['role'], 'doctor')

    def test_login_failure_invalid_credentials(self):
        """
        Ensure login fails with invalid credentials.
        """
        response = self.client.post(self.login_url, {
            'username': 'nonexistent', 'password': 'wrongpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'Invalid credentials')


class PatientMedicalRecordTests(APITestCase):
    def setUp(self):
        # Create doctor 1
        self.doctor1 = User.objects.create_user(username='doctor1', password='doc1pass')
        Profile.objects.create(user=self.doctor1, role='doctor')
        self.token1 = Token.objects.create(user=self.doctor1)

        # Create doctor 2
        self.doctor2 = User.objects.create_user(username='doctor2', password='doc2pass')
        Profile.objects.create(user=self.doctor2, role='doctor')
        self.token2 = Token.objects.create(user=self.doctor2)

        # Create an admin user (superuser)
        self.admin_user = User.objects.create_superuser(username='admin', password='adminpass')
        # Profile for superuser is created by signal, ensure role is 'admin' for clarity/consistency
        self.admin_user.profile.role = 'admin'
        self.admin_user.profile.save()
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.patient_list_create_url = reverse('patient-list-create')
        self.add_record_url = reverse('medical-record-add')

        # Doctor 1 creates patients
        self.patient1_doc1 = Patient.objects.create(
            name='Patient A', age=30, gender='Male', address='123 Main St', created_by=self.doctor1
        )
        self.patient2_doc1 = Patient.objects.create(
            name='Patient B', age=45, gender='Female', address='456 Oak Ave', created_by=self.doctor1
        )

        # Doctor 2 creates a patient
        self.patient3_doc2 = Patient.objects.create(
            name='Patient C', age=25, gender='Other', address='789 Pine Rd', created_by=self.doctor2
        )

        # Add some medical records for doctor1's patients
        self.record1_doc1 = MedicalRecord.objects.create(
            patient=self.patient1_doc1, symptoms='Fever', diagnosis='Flu', treatment='Rest'
        )
        self.record2_doc1 = MedicalRecord.objects.create(
            patient=self.patient1_doc1, symptoms='Cough', diagnosis='Cold', treatment='Medication'
        )

    # --- Patient Creation Tests ---
    def test_patient_creation_by_doctor(self):
        """
        Ensure a doctor can create a patient.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        data = {
            'name': 'New Patient',
            'age': 28,
            'gender': 'Female',
            'address': 'New Patient Address'
        }
        response = self.client.post(self.patient_list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Patient.objects.count(), 4) # 3 existing + 1 new
        self.assertEqual(Patient.objects.get(name='New Patient').created_by, self.doctor1)

    def test_patient_creation_by_admin(self):
        """
        Ensure an admin can create a patient (though usually doctors do this).
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        data = {
            'name': 'Admin Patient',
            'age': 50,
            'gender': 'Male',
            'address': 'Admin Patient Address'
        }
        response = self.client.post(self.patient_list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Patient.objects.count(), 4)
        self.assertEqual(Patient.objects.get(name='Admin Patient').created_by, self.admin_user)

    def test_patient_creation_without_authentication(self):
        """
        Ensure unauthenticated user cannot create a patient.
        """
        data = {
            'name': 'Unauthorized Patient',
            'age': 20,
            'gender': 'Male',
            'address': 'Some Address'
        }
        response = self.client.post(self.patient_list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Patient.objects.count(), 3) # No new patient created

    def test_patient_creation_with_invalid_age(self):
        """
        Ensure patient creation fails with age <= 0.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        data = {
            'name': 'Invalid Age Patient',
            'age': 0, # Invalid age
            'gender': 'Male',
            'address': 'Some Address'
        }
        response = self.client.post(self.patient_list_create_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('age', response.data)
        self.assertEqual(Patient.objects.count(), 3)

    # --- Doctor's Ability to View Only Their Own Patients' Records ---
    def test_doctor_views_own_patients(self):
        """
        Ensure doctor1 can only see patients they created.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        response = self.client.get(self.patient_list_create_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2) # Doctor 1 has 2 patients
        patient_names = [p['name'] for p in response.data['results']]
        self.assertIn('Patient A', patient_names)
        self.assertIn('Patient B', patient_names)
        self.assertNotIn('Patient C', patient_names)

    def test_doctor_cannot_view_other_doctors_patient_records(self):
        """
        Ensure doctor1 cannot view medical records of a patient created by doctor2.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        # Try to access records for patient3_doc2 (created by doctor2)
        url = reverse('patient-medical-records', kwargs={'pk': self.patient3_doc2.id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'You do not have permission to perform this action.')

    def test_doctor_can_view_own_patient_records(self):
        """
        Ensure doctor1 can view medical records of their own patient.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        url = reverse('patient-medical-records', kwargs={'pk': self.patient1_doc1.id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2) # patient1_doc1 has 2 records
        symptoms = [r['symptoms'] for r in response.data['results']]
        self.assertIn('Fever', symptoms)
        self.assertIn('Cough', symptoms)

    # --- Restricts Access to Records Created by Someone Else ---
    def test_doctor_cannot_add_record_to_other_doctors_patient(self):
        """
        Ensure doctor1 cannot add a medical record to a patient created by doctor2.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        data = {
            'patient': self.patient3_doc2.id, # patient3_doc2 belongs to doctor2
            'symptoms': 'Headache',
            'diagnosis': 'Migraine',
            'treatment': 'Painkillers'
        }
        response = self.client.post(self.add_record_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'You can only add medical records to your own patients.')
        self.assertEqual(MedicalRecord.objects.count(), 2) # No new record should be created

    def test_doctor_can_add_record_to_own_patient(self):
        """
        Ensure doctor1 can add a medical record to their own patient.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token1.key)
        data = {
            'patient': self.patient2_doc1.id, # patient2_doc1 belongs to doctor1
            'symptoms': 'Rash',
            'diagnosis': 'Allergy',
            'treatment': 'Antihistamines'
        }
        response = self.client.post(self.add_record_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicalRecord.objects.count(), 3) # 2 existing + 1 new
        new_record = MedicalRecord.objects.get(symptoms='Rash')
        self.assertEqual(new_record.patient, self.patient2_doc1)

    def test_admin_can_view_all_patients(self):
        """
        Ensure an admin can view all patients, regardless of who created them.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        response = self.client.get(self.patient_list_create_url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3) # All 3 patients
        patient_names = {p['name'] for p in response.data['results']}
        self.assertIn('Patient A', patient_names)
        self.assertIn('Patient B', patient_names)
        self.assertIn('Patient C', patient_names)

    def test_admin_can_view_any_patient_records(self):
        """
        Ensure an admin can view medical records for any patient.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        # Access records for patient3_doc2 (created by doctor2)
        url = reverse('patient-medical-records', kwargs={'pk': self.patient3_doc2.id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Patient C has no records initially, so list should be empty
        self.assertEqual(len(response.data['results']), 0)

        # Access records for patient1_doc1 (created by doctor1)
        url = reverse('patient-medical-records', kwargs={'pk': self.patient1_doc1.id})
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_admin_can_add_record_to_any_patient(self):
        """
        Ensure admin can add a medical record to any patient.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        data = {
            'patient': self.patient3_doc2.id, # patient3_doc2 belongs to doctor2
            'symptoms': 'Admin added symptoms',
            'diagnosis': 'Admin diagnosis',
            'treatment': 'Admin treatment'
        }
        response = self.client.post(self.add_record_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(MedicalRecord.objects.count(), 3)
        self.assertTrue(MedicalRecord.objects.filter(patient=self.patient3_doc2, symptoms='Admin added symptoms').exists())

    def test_unauthenticated_access(self):
        """
        Ensure unauthenticated users cannot access patient or record endpoints.
        """
        response = self.client.get(self.patient_list_create_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(self.add_record_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)