from django.contrib import admin

from .models import (
    Guide,
    GuideAnswer,
    GuideQuestion,
    GuideRating,
    GuideReference,
    GuideVersion,
    Step,
    StepTip,
    StepTipVote,
)


class StepInline(admin.TabularInline):
    model = Step
    extra = 0


class GuideReferenceInline(admin.TabularInline):
    model = GuideReference
    extra = 0


@admin.register(GuideVersion)
class GuideVersionAdmin(admin.ModelAdmin):
    list_display = ('guide', 'status', 'edited_by', 'ai_assisted', 'created_via', 'created_at')
    list_filter = ('status', 'ai_assisted', 'created_via', 'created_at')
    search_fields = ('guide__title', 'edit_summary')
    inlines = [StepInline, GuideReferenceInline]


@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'category', 'created_by', 'ai_assisted', 'created_via', 'created_at')
    list_filter = ('category', 'ai_assisted', 'created_via', 'created_at')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'summary', 'organization__name')


@admin.register(StepTip)
class StepTipAdmin(admin.ModelAdmin):
    list_display = ('body', 'step', 'submitted_by', 'upvotes', 'downvotes', 'created_at')
    search_fields = ('body',)


admin.site.register(StepTipVote)


@admin.register(GuideRating)
class GuideRatingAdmin(admin.ModelAdmin):
    list_display = ('guide', 'user', 'score', 'created_at')


@admin.register(GuideQuestion)
class GuideQuestionAdmin(admin.ModelAdmin):
    list_display = ('guide', 'author', 'step', 'created_at')
    search_fields = ('body', 'guide__title')


@admin.register(GuideAnswer)
class GuideAnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'author', 'is_accepted', 'created_at')
    list_filter = ('is_accepted',)
    search_fields = ('body', 'question__body')
