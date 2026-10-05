from datetime import date

from django.db import migrations


GUIDE_SLUG = "how-to-get-an-nid-card-in-papua-new-guinea"

SUMMARY = """A practical guide to registering for a Papua New Guinea National Identification (NID) card and birth record through the PNG Civil and Identity Registry (PNGCIR).

## At a glance

- **Normal NID registration is free** according to PNGCIR.
- **Adults aged 18 and over register for both birth registration and NID.**
- **You must attend in person** for fingerprint and photo capture; full online registration is not available.
- You can download the **Birth & National Identity Registration Form** before visiting PNGCIR.
- Bring supporting documents that help prove your identity, birth details and family information.

This guide is based on official PNG Civil and Identity Registry information checked on **5 October 2026**. Office procedures and supporting-document requirements can vary depending on your circumstances, so confirm with PNGCIR if your records are incomplete or unusual."""

STEPS = [
    (
        "Work out what you are registering for",
        """For PNG citizens, birth registration and NID are linked.

### If you are under 18
PNGCIR states that persons below 18 register their **birth**.

### If you are 18 or older
PNGCIR states that adults aged 18 and over register for **both their birth and National Identity Document (NID)**.

If you already have a registered birth but need an NID card, take any existing birth certificate or NID-related records with you so PNGCIR can match your record.""",
    ),
    (
        "Download and complete the Birth & NID registration form",
        """Download PNGCIR's **Birth & National Identity Registration Form (Form 1)** from the official PNGCIR website.

PNGCIR's instructions say to:
- print the form on **both sides of the paper**;
- complete it using a **blue biro**;
- provide information that matches your details at birth, especially your name, date of birth and place of birth.

For applicants aged 18 and over, the form also includes NID-specific information such as your place of origin, current residential address and, where applicable, a preferred spouse family name.""",
    ),
    (
        "Gather documents that support your identity and birth details",
        """PNGCIR lists several types of records that can support birth and NID registration. Depending on your circumstances, useful documents include:

- Clinic book or health record book
- Baptism record
- Employment ID card
- Passport
- School records
- Existing NID card or birth certificate
- Written statement from an informant/notifier
- Primary Verifier documentation where required

You may not need every item on this list. The purpose is to give PNGCIR enough reliable evidence to verify your identity and birth details.

> **Practical tip:** Take originals plus photocopies where possible. If your birth was never formally recorded, expect PNGCIR to require stronger supporting evidence or a verifier.""",
    ),
    (
        "Use a verifier or witness when your birth records are limited",
        """PNGCIR uses verifier and witness information in cases where normal birth records are limited.

For example, its registration guidance says a **Primary Verifier Form** may be used in some village-birth cases, with verification by people such as a ward recorder, ward councillor, pastor/religious leader or an NID card holder.

Witness identification may also be required, such as a driver's licence, work ID, passport copy or NID card.

The exact evidence depends on how and where the birth occurred, so ask PNGCIR what applies to your case before arranging statutory declarations or other documents unnecessarily.""",
    ),
    (
        "Visit a PNGCIR office in person",
        """Take the completed form and supporting documents to your nearest **PNG Civil and Identity Registry office**.

PNGCIR states that full online NID registration is not possible because every citizen must provide **fingerprints and an identity/photo capture in person**.

That means an online form or downloaded application can save preparation time, but it does **not** replace the physical registration visit.""",
    ),
    (
        "Complete fingerprint and photo capture",
        """At the registration point, PNGCIR staff will process your application and capture the biometric information required for NID registration.

This includes the in-person fingerprint and identity/photo capture referred to by PNGCIR.

Before leaving, confirm that your name, date of birth and other key details have been recorded correctly. Errors can create problems later when using the NID for passports, banking, education or other services.""",
    ),
    (
        "Do not pay anyone for normal NID registration",
        """PNGCIR states that **NID registration is 100% free** and that no fee is charged for normal NID registration.

There are regulated fees for some other civil-registry services, such as urgent processing or amendments, but those are separate from normal NID registration.

> **Warning:** Do not give unofficial payments or gifts to people claiming they can register you faster. PNGCIR also publishes a **No Gift Policy**.""",
    ),
    (
        "Follow up if your card or birth certificate is delayed",
        """Keep any registration receipt, reference number or other paperwork you receive.

If your birth certificate or NID card is delayed, use PNGCIR's official contact channels or collection/enquiry services rather than starting a duplicate registration unless PNGCIR tells you to do so.

PNGCIR currently lists these contact details:
- Landline: **(+675) 313 3000**
- Mobile: **7651 9974 / 7256 1350**
- Email: **helpdesk@pngcir.gov.pg**

Because collection arrangements and processing times can change, confirm the current process directly with PNGCIR.""",
    ),
]

REFERENCES = [
    (
        "NID Registration Information",
        "https://pngcir.gov.pg/nid-registration-information/",
        "PNG Civil and Identity Registry",
    ),
    (
        "Birth & National Identity Registration Form",
        "https://pngcir.gov.pg/wp-content/uploads/2020/01/Form-1-Birth.pdf",
        "PNG Civil and Identity Registry",
    ),
    (
        "PNGCIR Downloads",
        "https://pngcir.gov.pg/downloads/",
        "PNG Civil and Identity Registry",
    ),
    (
        "PNGCIR Information Booklet",
        "https://www.pngcir.gov.pg/wp-content/uploads/2020/01/PNGCIR-Information.pdf",
        "PNG Civil and Identity Registry",
    ),
    (
        "NID Registration is Free / EFTPOS Notice",
        "https://pngcir.gov.pg/eftpos-machines-installed/",
        "PNG Civil and Identity Registry",
    ),
    (
        "PNGCIR Contact",
        "https://pngcir.gov.pg/contact/",
        "PNG Civil and Identity Registry",
    ),
]


def add_png_nid_guide(apps, schema_editor):
    Guide = apps.get_model("guides", "Guide")
    GuideVersion = apps.get_model("guides", "GuideVersion")
    GuideReference = apps.get_model("guides", "GuideReference")
    Step = apps.get_model("guides", "Step")
    BusinessCategory = apps.get_model("categories", "BusinessCategory")

    if Guide.objects.filter(slug=GUIDE_SLUG).exists():
        return

    passport_guide = Guide.objects.filter(
        slug="how-to-get-a-new-papua-new-guinea-png-passport"
    ).first()
    category = BusinessCategory.objects.filter(name="Services & utilities").first()

    guide = Guide.objects.create(
        title="How to Get an NID Card in Papua New Guinea",
        slug=GUIDE_SLUG,
        summary=SUMMARY,
        category=category,
        created_by_id=passport_guide.created_by_id if passport_guide else None,
        created_via="mcp",
        ai_assisted=True,
        ai_provider="OpenAI",
        ai_model="GPT-5.6 Sol",
        ai_source_note="Official PNG Civil and Identity Registry sources checked 5 October 2026.",
    )

    version = GuideVersion.objects.create(
        guide=guide,
        edited_by_id=guide.created_by_id,
        status="published",
        edit_summary="Initial PNG NID registration guide based on official PNGCIR sources",
        created_via="mcp",
        ai_assisted=True,
        ai_provider="OpenAI",
        ai_model="GPT-5.6 Sol",
        ai_source_note="Official PNG Civil and Identity Registry sources checked 5 October 2026.",
    )

    for position, (title, instruction) in enumerate(STEPS, start=1):
        Step.objects.create(
            version=version,
            position=float(position),
            title=title,
            instruction=instruction,
        )

    for title, url, publisher in REFERENCES:
        GuideReference.objects.create(
            version=version,
            title=title,
            url=url,
            publisher=publisher,
            accessed_at=date(2026, 10, 5),
        )

    guide.current_version_id = version.id
    guide.save(update_fields=["current_version"])


class Migration(migrations.Migration):
    dependencies = [
        ("guides", "0011_refresh_png_passport_guide"),
    ]

    operations = [
        migrations.RunPython(add_png_nid_guide, migrations.RunPython.noop),
    ]
