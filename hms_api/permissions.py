from rest_framework import permissions

class IsDoctor(permissions.BasePermission):
    """
    Custom permission to only allow doctors to access.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.profile.role == 'doctor'

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admins (superusers or users with admin role) to access.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.profile.role == 'admin')

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object (or admin) to view/edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can always view/edit
        if request.user.is_superuser or request.user.profile.role == 'admin':
            return True
        # Doctors can only see/edit their own patients/records
        return obj.created_by == request.user

class IsPatientRecordOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow a doctor to view/add records for their patients, or admin to view any.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can always view/edit
        if request.user.is_superuser or request.user.profile.role == 'admin':
            return True
        # Doctors can only see/add records for their own patients
        # 'obj' here is a MedicalRecord, so we check its patient's created_by
        return obj.patient.created_by == request.user

    def has_permission(self, request, view):
        # This is for list view permissions or creating new records.
        # Doctors can access if they are interacting with their own patient context.
        # Admins can access all records.
        if request.user.is_superuser or request.user.profile.role == 'admin':
            return True
        return request.user and request.user.is_authenticated and request.user.profile.role == 'doctor'