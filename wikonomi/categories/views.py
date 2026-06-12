from django.http import JsonResponse
from .models import Subcategory, BusinessSubcategory


def subcategories_json(request):
    cat_id = request.GET.get('category_id')
    subs = Subcategory.objects.filter(category_id=cat_id).values('id', 'name', 'examples', 'is_png_specific')
    return JsonResponse({'subcategories': list(subs)})


def business_subcategories_json(request):
    cat_id = request.GET.get('category_id')
    subs = BusinessSubcategory.objects.filter(category_id=cat_id).values('id', 'name')
    return JsonResponse({'subcategories': list(subs)})
