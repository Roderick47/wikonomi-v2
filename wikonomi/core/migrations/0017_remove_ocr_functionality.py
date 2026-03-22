# Generated to remove OCR functionality

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_pricereport_ocr_confidence_and_more'),
    ]

    operations = [
        # Remove OCRProcessingLog model
        migrations.DeleteModel(
            name='OCRProcessingLog',
        ),
        
        # Remove all OCR fields from PriceReport
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_confidence',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_error_message',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_extracted_price',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_extracted_product_name',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_processed',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_processing_status',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_raw_text',
        ),
        migrations.RemoveField(
            model_name='pricereport',
            name='ocr_results',
        ),
    ]
