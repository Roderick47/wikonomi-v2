from datetime import date

from django.db import migrations


GUIDE_SLUG = "how-to-get-a-new-papua-new-guinea-png-passport"
EDIT_SUMMARY = "Updated PNG passport requirements, fees, damaged-passport guidance and official ICA sources"


SUMMARY = """A practical, current guide to getting, renewing or replacing a Papua New Guinea passport through the Immigration & Citizenship Authority (ICA).

## At a glance

- **Standard ordinary passport fee:** K100
- **Normal processing:** ICA's checklist states about **7 working days**
- **Fast-track processing:** **K200 extra**, with ICA's checklist stating about **2 working days / 48 hours**
- **Port Moresby lodgement:** ICA Head Office, Central Government Office, Waigani
- **Bring complete documents:** ICA warns that incomplete applications may not be accepted

> **Lost, stolen or damaged passport?** ICA uses a separate checklist and charges additional reissue fees. See the dedicated replacement step below.

This guide is based on official ICA passport pages, application forms, checklists and fee notices checked on **21 September 2026**. Requirements can change, so confirm with ICA before paying or travelling."""


STEPS = [
    (
        "Choose the right passport process",
        """Before filling anything in, work out which type of application you are making.

### First-time ordinary passport
Use the standard PNG passport application process and the **FA 81 Application for a Travel Document**.

### Renewal
Use FA 81 and follow ICA's renewal checklist. Your previous passport is normally required.

### Lost, stolen or damaged passport
Use FA 81 **plus ICA's separate lost/stolen/damaged passport checklist**.

> **Important:** A damaged passport is not treated exactly the same as a normal renewal. ICA applies a separate reissue fee schedule for lost, stolen and damaged passports.

Official forms and checklists are linked in the **Sources** section at the bottom of this guide.""",
    ),
    (
        "Complete the FA 81 application form",
        """Download and complete the **FA 81 – Application for a Travel Document**.

You can type into the fillable PDF using Adobe Reader and then print it, or print it first and complete it neatly in **black ink**.

### Before you submit
- Complete a separate application for each person.
- Sign both signature boxes using a ball-point pen and stay inside the borders.
- If you cannot sign, put a line through both signature boxes.
- Make sure the declaration section is signed.
- ICA advises applicants to complete the process well before intended travel.

> **Do not provide false or misleading information.** The application form warns that doing so is a criminal offence.""",
    ),
    (
        "Prepare citizenship and identity documents",
        """The documents depend on the type of application.

### First-time adult application
ICA's checklist requires:
- Completed **FA 81**
- Certified/notarized copy of your **NID Birth Certificate**
- NID card copy is listed as optional on the first-time adult checklist
- Original MSF payment receipt

ICA's general passport page also says applicants should provide evidence of PNG citizenship, such as a **birth certificate or citizenship certificate**.

### Renewal
Provide your previous passport as required by ICA's renewal checklist. ICA's general guidance says the previous travel document should be attached unless it has been lost, stolen or destroyed.

### Lost passport
ICA's lost/stolen/damaged checklist requires:
- Certified copy of the lost valid passport/document if available
- **Statutory Declaration** explaining how the passport was lost
- **Police report**

### Damaged passport
Take the damaged passport with you. Because ICA treats damaged passports under its lost/stolen/damaged reissue process, use that checklist rather than relying only on the normal renewal requirements.

> Bring originals where ICA requires them and certified copies where the checklist specifically says certified/notarized.""",
    ),
    (
        "Get two passport photos and complete certification",
        """Provide **2 recent passport photographs**.

ICA's current checklist specifies:
- **45 mm × 35 mm**
- Head-and-shoulders
- Full face
- **White background**
- No tinted glasses
- Neutral expression
- **No smiling or showing teeth**

### Commissioner for Oaths / certification
ICA's current passport material requires the application to be properly certified.

The general passport page says the person completing the Certificate Regarding Applicant must have known you for at least **3 years**, and the same person should endorse the back of one photograph with wording confirming that it is a genuine photograph of you.

ICA's stricter process notice says passport applications must be certified by an approved Commissioner for Oaths, such as an authorised court official or legal officer with Commissioner for Oaths status.

> **Practical tip:** Before leaving the certifier, check that every required signature, contact detail and photo endorsement has been completed. Missing certification can cause ICA to reject the application at the counter.""",
    ),
    (
        "Pay the correct ICA passport fees",
        """Pay the prescribed fee and keep the **original MSF receipt** to attach to your application.

## Standard fees

- **Ordinary PNG passport:** K100
- **Fast-track processing:** K200 additional

ICA's adult checklist gives an indicative turnaround of:
- **Normal:** about 7 working days
- **Fast track:** about 2 working days / 48 hours

## Lost, stolen or damaged passport reissue fees

ICA's official checklist and fee notice list:

- **First loss / theft / damage:** K200
- **Second loss / theft / damage:** K1,000
- **Third loss / theft / damage:** K3,000

> ICA's lost/stolen/damaged checklist separately lists the **K100 normal lodgement fee** and the **reissue fee**. If you are replacing a damaged passport, confirm the total payable with ICA before making payment so you pay the correct amount.

ICA's fee notice also states that fees paid are **not refundable**.""",
    ),
    (
        "Lodge your application",
        """### Port Moresby
Lodge the application at:

**Immigration & Citizenship Authority (ICA) Head Office**  
Central Government Office  
Waigani, Port Moresby

### Outside Port Moresby
ICA's passport page says applications outside Port Moresby can be sent to:

**PNG Passports Branch**  
PNG ICA  
P.O. Box 1790  
Boroko, NCD

### Before you go
Check that you have:
- Completed FA 81
- Required citizenship/identity documents
- Previous or damaged passport where applicable
- 2 compliant photos
- Required certification
- Original MSF receipt
- Police report and statutory declaration if the passport was lost

> ICA's checklist says applicants must provide all listed requirements before lodgement and that incomplete applications may not be accepted.""",
    ),
    (
        "Collect your passport",
        """ICA says your completed passport may be sent by **registered post** unless you elect to collect it personally.

The current ICA passport page states that **agents may not collect passports on behalf of clients**.

If you choose personal collection, keep your lodgement/custody documentation safe and follow any collection instructions ICA gives you when you submit the application.""",
    ),
    (
        "Special notes for damaged, lost or urgent passports",
        """### If your passport was damaged
Do not throw it away. Take the damaged passport with you and use ICA's **lost/stolen/damaged passport checklist**. Even if the passport has not expired, damage can make it unsuitable for travel or identification.

### If your passport was lost or stolen
Prepare the required **Statutory Declaration** and **Police Report** before lodging.

### If you need the passport urgently
Fast-track processing is listed at **K200 in addition to the applicable passport fee**, with ICA's checklist stating approximately **2 working days / 48 hours**.

### If you are travelling soon
Do not depend on the minimum processing time alone. ICA's general guidance tells applicants to complete passport applications well before intended travel.

> **Best practice:** Check ICA's website or contact ICA shortly before lodging, especially for fees, payment arrangements, office procedures and processing times, because administrative requirements can change.""",
    ),
]


REFERENCES = [
    (
        "Applying for a PNG Passport",
        "https://ica.gov.pg/passport/applying-for-a-png-passport",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "FA 81 – Application for a Travel Document",
        "https://ica.gov.pg/uploads/media/post_file_5437896-passport-application-form-fillable-savable.pdf",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "Travel Document Checklists",
        "https://ica.gov.pg/passport/travel-document-checklists",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "PNG Passport Lost, Stolen & Damaged Checklist (19 years and older)",
        "https://ica.gov.pg/uploads/media/post_file_6393543-3.-checklist-for-png-passport---lost-and-stolen---19-years-and-older-1-.pdf",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "Ordinary PNG Passport First-Time Checklist (19 years and older)",
        "https://ica.gov.pg/uploads/media/post_file_6070572-6.-checklist---ordinary-png-passport-first-time-19-years-older-1-.pdf",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "Passport Fee Notice",
        "https://ica.gov.pg/uploads/media/public_notice_7804657-new-msf-fees-1-.pdf",
        "PNG Immigration & Citizenship Authority",
    ),
    (
        "Changes to PNG Passport Application Process",
        "https://ica.gov.pg/public-notices/2017/changes-to-png-passport-application-process",
        "PNG Immigration & Citizenship Authority",
    ),
]


def refresh_passport_guide(apps, schema_editor):
    Guide = apps.get_model("guides", "Guide")
    GuideVersion = apps.get_model("guides", "GuideVersion")
    GuideReference = apps.get_model("guides", "GuideReference")
    Step = apps.get_model("guides", "Step")
    StepPhoto = apps.get_model("guides", "StepPhoto")
    StepTip = apps.get_model("guides", "StepTip")
    GuideQuestion = apps.get_model("guides", "GuideQuestion")

    guide = Guide.objects.filter(slug=GUIDE_SLUG).first()
    if not guide:
        return

    if GuideVersion.objects.filter(guide=guide, edit_summary=EDIT_SUMMARY).exists():
        return

    old_steps = list(
        Step.objects.filter(version_id=guide.current_version_id).order_by("position", "id")
    ) if guide.current_version_id else []

    guide.title = "How to Get, Renew or Replace a Papua New Guinea (PNG) Passport"
    guide.summary = SUMMARY
    guide.ai_assisted = True
    guide.ai_provider = "OpenAI"
    guide.ai_model = "GPT-5.6 Sol"
    guide.ai_source_note = "Official PNG ICA sources checked 21 September 2026."
    guide.save(update_fields=[
        "title",
        "summary",
        "ai_assisted",
        "ai_provider",
        "ai_model",
        "ai_source_note",
    ])

    version = GuideVersion.objects.create(
        guide=guide,
        edited_by_id=guide.created_by_id,
        status="published",
        edit_summary=EDIT_SUMMARY,
        created_via="mcp",
        ai_assisted=True,
        ai_provider="OpenAI",
        ai_model="GPT-5.6 Sol",
        ai_source_note="Official PNG ICA sources checked 21 September 2026.",
    )

    new_steps = []
    for position, (title, instruction) in enumerate(STEPS, start=1):
        new_steps.append(
            Step.objects.create(
                version=version,
                position=float(position),
                title=title,
                instruction=instruction,
            )
        )

    # Preserve community contributions from the six original steps by moving
    # them to the closest matching step in the refreshed guide.
    old_to_new_positions = {
        0: 1,  # Complete application form -> Complete FA 81
        1: 2,  # Gather documentation -> Prepare documents
        2: 3,  # Photos/certification -> Photos/certification
        3: 4,  # Fees -> Fees
        4: 5,  # Lodge -> Lodge
        5: 6,  # Collection -> Collection
    }
    for old_index, new_index in old_to_new_positions.items():
        if old_index >= len(old_steps) or new_index >= len(new_steps):
            continue
        old_step = old_steps[old_index]
        new_step = new_steps[new_index]
        StepPhoto.objects.filter(step_id=old_step.id).update(step_id=new_step.id)
        StepTip.objects.filter(step_id=old_step.id).update(step_id=new_step.id)
        GuideQuestion.objects.filter(step_id=old_step.id).update(step_id=new_step.id)

    for title, url, publisher in REFERENCES:
        GuideReference.objects.create(
            version=version,
            title=title,
            url=url,
            publisher=publisher,
            accessed_at=date(2026, 9, 21),
        )

    guide.current_version_id = version.id
    guide.save(update_fields=["current_version"])


class Migration(migrations.Migration):
    dependencies = [
        ("guides", "0010_mcp_ai_provenance_and_references"),
    ]

    operations = [
        migrations.RunPython(refresh_passport_guide, migrations.RunPython.noop),
    ]
