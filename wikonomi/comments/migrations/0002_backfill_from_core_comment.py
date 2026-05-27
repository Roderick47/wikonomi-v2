from django.db import migrations


def backfill_core_comments(apps, schema_editor):
    CoreComment = apps.get_model('core', 'Comment')
    Comment = apps.get_model('comments', 'Comment')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    price_report_ct, _ = ContentType.objects.get_or_create(app_label='core', model='pricereport')
    business_ct, _ = ContentType.objects.get_or_create(app_label='core', model='business')

    id_map = {}
    for old in CoreComment.objects.filter(parent__isnull=True).order_by('id'):
        if old.price_report_id:
            ctype_id, obj_id = price_report_ct.id, old.price_report_id
        elif old.business_id:
            ctype_id, obj_id = business_ct.id, old.business_id
        else:
            continue
        new = Comment.objects.create(
            user_id=old.user_id,
            content_type_id=ctype_id,
            object_id=obj_id,
            body=old.body,
            created_at=old.created_at,
            updated_at=old.created_at,
        )
        id_map[old.id] = new.id

    for old in CoreComment.objects.filter(parent__isnull=False).order_by('id'):
        parent_new_id = id_map.get(old.parent_id)
        if not parent_new_id:
            continue
        parent = Comment.objects.get(id=parent_new_id)
        new = Comment.objects.create(
            user_id=old.user_id,
            content_type_id=parent.content_type_id,
            object_id=parent.object_id,
            parent_id=parent_new_id,
            body=old.body,
            created_at=old.created_at,
            updated_at=old.created_at,
        )
        id_map[old.id] = new.id


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('comments', '0001_initial'),
        ('core', '0005_alter_comment_user'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(backfill_core_comments, noop),
    ]
