from django.utils import timezone
from rest_framework import serializers
from django.templatetags.static import static
import bleach

from .models import Comment


class AuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    profile_picture = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile:
            return profile.profile_picture_url
        return static('img/default-profile.svg')


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'content_type', 'object_id', 'parent', 'body', 'is_edited', 'is_deleted',
            'is_pinned', 'is_flagged', 'like_count', 'reply_count', 'created_at', 'updated_at',
            'author', 'user_has_liked', 'time_ago'
        ]
        read_only_fields = [
            'is_edited', 'is_deleted', 'is_pinned', 'is_flagged', 'like_count', 'reply_count',
            'created_at', 'updated_at', 'author', 'user_has_liked', 'time_ago'
        ]

    def validate_body(self, value):
        cleaned = bleach.clean(value or '', tags=[], attributes={}, strip=True).strip()
        if not cleaned:
            raise serializers.ValidationError('Comment body cannot be empty.')
        if len(cleaned) > 2000:
            raise serializers.ValidationError('Comment body must be 2000 characters or fewer.')
        return cleaned

    def get_author(self, obj):
        return AuthorSerializer(obj.user).data

    def get_user_has_liked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        prefetched_likes = getattr(obj, '_prefetched_objects_cache', {}).get('likes')
        if prefetched_likes is not None:
            return any(like.user_id == request.user.id for like in prefetched_likes)
        return obj.likes.filter(user=request.user).exists()

    def get_time_ago(self, obj):
        delta = timezone.now() - obj.created_at
        secs = int(delta.total_seconds())
        if secs < 60:
            return 'just now'
        if secs < 3600:
            return f'{secs // 60}m ago'
        if secs < 86400:
            return f'{secs // 3600}h ago'
        return f'{secs // 86400}d ago'
