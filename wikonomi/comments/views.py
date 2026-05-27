from django.contrib.contenttypes.models import ContentType
from django.db.models import F
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination

from .models import Comment, CommentLike, CommentFlag
from .permissions import IsAuthenticatedForWrite, IsAuthorOrStaffForModify, CanPinComment
from .serializers import CommentSerializer
from .throttles import CommentCreateThrottle


class TopLevelCommentPagination(CursorPagination):
    page_size = 20
    ordering = '-created_at'
    cursor_query_param = 'cursor'


class RepliesPagination(CursorPagination):
    page_size = 5
    ordering = 'created_at'
    cursor_query_param = 'cursor'


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    queryset = Comment.objects.select_related('user', 'content_type', 'parent').prefetch_related('likes').all()
    permission_classes = [IsAuthenticatedForWrite, IsAuthorOrStaffForModify]

    def get_throttles(self):
        if self.action in ['create', 'reply']:
            return [CommentCreateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            ct = self.request.query_params.get('ct')
            oid = self.request.query_params.get('oid')
            if not ct or not oid:
                return qs.none()
            qs = qs.filter(content_type_id=ct, object_id=oid, parent__isnull=True)
            sort = self.request.query_params.get('sort', 'top')
            if sort == 'newest':
                return qs.order_by('-created_at', '-id')
            if sort == 'oldest':
                return qs.order_by('created_at', 'id')
            return qs.order_by('-is_pinned', '-like_count', '-created_at', '-id')
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        paginator = TopLevelCommentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(is_edited=True)

    def perform_destroy(self, instance):
        instance.body = '[deleted]'
        instance.is_deleted = True
        instance.save(update_fields=['body', 'is_deleted', 'updated_at'])

    @action(detail=True, methods=['get'], url_path='replies')
    def replies(self, request, pk=None):
        parent = self.get_object()
        qs = parent.replies.select_related('user').prefetch_related('likes').order_by('created_at', 'id')
        paginator = RepliesPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='reply')
    def reply(self, request, pk=None):
        parent = self.get_object()
        data = request.data.copy()
        data['parent'] = parent.id
        data['content_type'] = parent.content_type_id
        data['object_id'] = parent.object_id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(user=request.user)
        Comment.objects.filter(pk=parent.pk).update(reply_count=F('reply_count') + 1)
        return Response(self.get_serializer(comment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='like')
    def like(self, request, pk=None):
        comment = self.get_object()
        like, created = CommentLike.objects.get_or_create(comment=comment, user=request.user)
        if created:
            Comment.objects.filter(pk=comment.pk).update(like_count=F('like_count') + 1)
            return Response({'liked': True}, status=status.HTTP_201_CREATED)
        like.delete()
        Comment.objects.filter(pk=comment.pk, like_count__gt=0).update(like_count=F('like_count') - 1)
        return Response({'liked': False}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='pin')
    def pin(self, request, pk=None):
        comment = self.get_object()
        if not CanPinComment().has_object_permission(request, self, comment):
            raise PermissionDenied('Not allowed to pin this comment.')
        if not comment.is_pinned:
            Comment.objects.filter(
                content_type=comment.content_type,
                object_id=comment.object_id,
                is_pinned=True,
            ).exclude(pk=comment.pk).update(is_pinned=False)
        comment.is_pinned = not comment.is_pinned
        comment.save(update_fields=['is_pinned', 'updated_at'])
        return Response({'is_pinned': comment.is_pinned})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated], url_path='flag')
    def flag(self, request, pk=None):
        comment = self.get_object()
        reason = request.data.get('reason') or CommentFlag.REASON_OTHER
        valid_reasons = {choice[0] for choice in CommentFlag.REASON_CHOICES}
        if reason not in valid_reasons:
            raise ValidationError({'reason': 'Invalid reason.'})
        _, created = CommentFlag.objects.get_or_create(comment=comment, user=request.user, defaults={'reason': reason})
        if created:
            comment.is_flagged = True
            comment.save(update_fields=['is_flagged', 'updated_at'])
        return Response({'flagged': True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
