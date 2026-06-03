from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthenticatedForWrite(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


class IsAuthorOrStaffForModify(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.method == 'DELETE':
            return bool(request.user and request.user.is_authenticated and (obj.user_id == request.user.id or request.user.is_staff))
        return bool(request.user and request.user.is_authenticated and obj.user_id == request.user.id)


class CanPinComment(BasePermission):
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        target = obj.content_object
        owner = getattr(target, 'user_id', None) or getattr(target, 'created_by_id', None)
        return owner == request.user.id
