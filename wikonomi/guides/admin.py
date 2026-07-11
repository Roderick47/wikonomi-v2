from django.contrib import admin

from .models import Guide, GuideRating, GuideVersion, Step, StepTip, StepTipVote


class StepInline(admin.TabularInline):
    model = Step
    extra = 0


@admin.register(GuideVersion)
class GuideVersionAdmin(admin.ModelAdmin):
    list_display = ('guide', 'status', 'edited_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('guide__title', 'edit_summary')
    inlines = [StepInline]


@admin.register(Guide)
class GuideAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'category', 'created_by', 'created_at')
    list_filter = ('category', 'created_at')
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
