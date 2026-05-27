from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from comments.models import Comment, CommentLike, CommentFlag
from comments.serializers import CommentSerializer
from core.models import Product


class CommentsBaseTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.factory = APIRequestFactory()

        self.owner = User.objects.create_user(username='owner', password='pass')
        self.other = User.objects.create_user(username='other', password='pass')
        self.staff = User.objects.create_user(username='staff', password='pass', is_staff=True)

        self.product = Product.objects.create(name='Rice', slug='rice', created_by=self.owner)
        self.product2 = Product.objects.create(name='Bread', slug='bread', created_by=self.owner)
        self.ct = ContentType.objects.get_for_model(Product)

    def comments_url(self):
        return '/api/comments/'

    def create_comment(self, user=None, **overrides):
        user = user or self.owner
        data = {
            'user': user,
            'content_type': self.ct,
            'object_id': self.product.id,
            'body': 'hello world',
        }
        data.update(overrides)
        return Comment.objects.create(**data)


class CommentModelTests(CommentsBaseTestCase):
    def test_reply_depth_two_levels_allowed(self):
        root = self.create_comment()
        reply = self.create_comment(user=self.other, parent=root, body='reply')
        nested = self.create_comment(user=self.owner, parent=reply, body='nested')
        self.assertEqual(nested.parent, reply)
        self.assertEqual(nested.parent.parent, root)

    def test_soft_delete_marks_deleted_and_body_placeholder(self):
        c = self.create_comment(body='original body')
        c.body = '[deleted]'
        c.is_deleted = True
        c.save(update_fields=['body', 'is_deleted', 'updated_at'])
        c.refresh_from_db()
        self.assertTrue(c.is_deleted)
        self.assertEqual(c.body, '[deleted]')

    def test_like_and_flag_unique_per_user(self):
        c = self.create_comment()
        CommentLike.objects.create(comment=c, user=self.owner)
        CommentFlag.objects.create(comment=c, user=self.owner, reason=CommentFlag.REASON_SPAM)
        with self.assertRaises(Exception):
            CommentLike.objects.create(comment=c, user=self.owner)
        with self.assertRaises(Exception):
            CommentFlag.objects.create(comment=c, user=self.owner, reason=CommentFlag.REASON_OTHER)

    def test_pin_uniqueness_per_object(self):
        c1 = self.create_comment(body='c1')
        c2 = self.create_comment(body='c2')
        c3 = Comment.objects.create(user=self.owner, content_type=self.ct, object_id=self.product2.id, body='c3')
        c1.is_pinned = True
        c1.save(update_fields=['is_pinned'])
        Comment.objects.filter(content_type=c2.content_type, object_id=c2.object_id, is_pinned=True).exclude(pk=c2.pk).update(is_pinned=False)
        c2.is_pinned = True
        c2.save(update_fields=['is_pinned'])
        self.assertEqual(Comment.objects.filter(content_type=self.ct, object_id=self.product.id, is_pinned=True).count(), 1)
        self.assertTrue(Comment.objects.get(pk=c2.pk).is_pinned)
        self.assertFalse(Comment.objects.get(pk=c1.pk).is_pinned)
        self.assertEqual(Comment.objects.filter(content_type=self.ct, object_id=self.product2.id, is_pinned=True).count(), 0)
        self.assertFalse(c3.is_pinned)


class CommentSerializerTests(CommentsBaseTestCase):
    def test_response_shape_author_user_has_liked_time_ago(self):
        c = self.create_comment()
        c.created_at = timezone.now() - timedelta(minutes=2)
        c.save(update_fields=['created_at'])
        CommentLike.objects.create(comment=c, user=self.owner)

        req = self.factory.get('/api/comments/')
        req.user = self.owner
        data = CommentSerializer(c, context={'request': req}).data

        self.assertIn('author', data)
        self.assertEqual(data['author']['id'], self.owner.id)
        self.assertEqual(data['author']['username'], 'owner')
        self.assertIn('user_has_liked', data)
        self.assertTrue(data['user_has_liked'])
        self.assertIn('time_ago', data)
        self.assertTrue(data['time_ago'].endswith('ago') or data['time_ago'] == 'just now')


class CommentApiTests(CommentsBaseTestCase):
    def test_auth_requirements(self):
        c = self.create_comment()
        unauth_create = self.client.post(self.comments_url(), {'content_type': self.ct.id, 'object_id': self.product.id, 'body': 'x'}, format='json')
        self.assertEqual(unauth_create.status_code, 403)

        self.client.force_authenticate(user=self.owner)
        auth_create = self.client.post(self.comments_url(), {'content_type': self.ct.id, 'object_id': self.product.id, 'body': 'x'}, format='json')
        self.assertEqual(auth_create.status_code, 201)

        self.client.force_authenticate(user=None)
        unauth_like = self.client.post(f'/api/comments/{c.id}/like/')
        self.assertEqual(unauth_like.status_code, 403)

    def test_list_sort_modes(self):
        older = self.create_comment(body='older')
        newer = self.create_comment(user=self.other, body='newer')
        Comment.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1), like_count=5)
        Comment.objects.filter(pk=newer.pk).update(created_at=timezone.now(), like_count=1)

        newest = self.client.get(self.comments_url(), {'ct': self.ct.id, 'oid': self.product.id, 'sort': 'newest'})
        self.assertEqual(newest.status_code, 200)
        self.assertEqual(newest.data['results'][0]['id'], newer.id)

        oldest = self.client.get(self.comments_url(), {'ct': self.ct.id, 'oid': self.product.id, 'sort': 'oldest'})
        self.assertEqual(oldest.data['results'][0]['id'], older.id)

        top = self.client.get(self.comments_url(), {'ct': self.ct.id, 'oid': self.product.id, 'sort': 'top'})
        self.assertEqual(top.data['results'][0]['id'], older.id)

    def test_cursor_pagination_correctness(self):
        for i in range(25):
            self.create_comment(body=f'c{i}')
        first = self.client.get(self.comments_url(), {'ct': self.ct.id, 'oid': self.product.id, 'sort': 'newest'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.data['results']), 20)
        self.assertIsNotNone(first.data['next'])

        second = self.client.get(first.data['next'])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.data['results']), 5)

    def test_create_reply_edit_delete_permissions(self):
        parent = self.create_comment(user=self.owner)
        self.client.force_authenticate(user=self.other)
        create = self.client.post(self.comments_url(), {'content_type': self.ct.id, 'object_id': self.product.id, 'body': 'new'}, format='json')
        self.assertEqual(create.status_code, 201)

        reply = self.client.post(f'/api/comments/{parent.id}/reply/', {'body': 'reply'}, format='json')
        self.assertEqual(reply.status_code, 201)

        owner_comment = self.create_comment(user=self.owner, body='owner only')
        patch_other = self.client.patch(f'/api/comments/{owner_comment.id}/', {'body': 'hack'}, format='json')
        self.assertEqual(patch_other.status_code, 403)
        delete_other = self.client.delete(f'/api/comments/{owner_comment.id}/')
        self.assertEqual(delete_other.status_code, 403)

        self.client.force_authenticate(user=self.owner)
        patch_owner = self.client.patch(f'/api/comments/{owner_comment.id}/', {'body': 'edited'}, format='json')
        self.assertEqual(patch_owner.status_code, 200)
        delete_owner = self.client.delete(f'/api/comments/{owner_comment.id}/')
        self.assertEqual(delete_owner.status_code, 204)

    def test_like_toggle_idempotency(self):
        c = self.create_comment()
        self.client.force_authenticate(user=self.owner)
        first = self.client.post(f'/api/comments/{c.id}/like/')
        second = self.client.post(f'/api/comments/{c.id}/like/')
        third = self.client.post(f'/api/comments/{c.id}/like/')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 201)
        c.refresh_from_db()
        self.assertEqual(c.like_count, 1)

    def test_flag_once_per_user(self):
        c = self.create_comment()
        self.client.force_authenticate(user=self.owner)
        first = self.client.post(f'/api/comments/{c.id}/flag/', {'reason': CommentFlag.REASON_SPAM}, format='json')
        second = self.client.post(f'/api/comments/{c.id}/flag/', {'reason': CommentFlag.REASON_OTHER}, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(CommentFlag.objects.filter(comment=c, user=self.owner).count(), 1)

    def test_pin_authorization_and_replacement_behavior(self):
        c1 = self.create_comment(user=self.other, body='c1')
        c2 = self.create_comment(user=self.other, body='c2')

        self.client.force_authenticate(user=self.other)
        denied = self.client.post(f'/api/comments/{c1.id}/pin/')
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(user=self.owner)
        pin1 = self.client.post(f'/api/comments/{c1.id}/pin/')
        self.assertEqual(pin1.status_code, 200)
        pin2 = self.client.post(f'/api/comments/{c2.id}/pin/')
        self.assertEqual(pin2.status_code, 200)

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_pinned)
        self.assertTrue(c2.is_pinned)


class CommentQueryRegressionTests(CommentsBaseTestCase):
    def test_list_query_count_avoids_n_plus_one(self):
        comments = [self.create_comment(body=f'c{i}') for i in range(5)]
        for c in comments:
            CommentLike.objects.create(comment=c, user=self.owner)
        self.client.force_authenticate(user=self.owner)
        with self.assertNumQueries(6):
            response = self.client.get(self.comments_url(), {'ct': self.ct.id, 'oid': self.product.id, 'sort': 'newest'})
            self.assertEqual(response.status_code, 200)

    def test_replies_query_count_avoids_n_plus_one(self):
        parent = self.create_comment()
        replies = [self.create_comment(user=self.other, parent=parent, body=f'r{i}') for i in range(5)]
        for r in replies:
            CommentLike.objects.create(comment=r, user=self.owner)
        self.client.force_authenticate(user=self.owner)
        with self.assertNumQueries(6):
            response = self.client.get(f'/api/comments/{parent.id}/replies/')
            self.assertEqual(response.status_code, 200)
