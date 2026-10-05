from datetime import date

from django.db import migrations


GUIDES = [
    {
        "slug": "how-to-get-a-police-clearance-in-papua-new-guinea",
        "title": "How to Get a Police Clearance in Papua New Guinea",
        "summary": """A practical guide to getting a **PNG Police Character Check / Police Clearance** through the Royal Papua New Guinea Constabulary (RPNGC).

## At a glance

- **Standard PNG Police Character Check fee:** K65
- **Indicative processing time:** about **1 week** for the standard PNG character check
- **Online service:** currently available for **NCD and Central Province** through the government portal
- **Online applicants still attend in person** for payment verification and ten-fingerprint biometric capture
- **Port Moresby biometric location:** Gordons Police Station

> **Important:** Police clearance procedures can differ by purpose (employment, visa, expatriate, PMV, firearms, crime report). Select the correct service before paying.

Official RPNGC information checked **5 October 2026**.""",
        "source_note": "Official RPNGC police-clearance sources checked 5 October 2026.",
        "steps": [
            ("Choose the correct type of police clearance", """RPNGC lists several different character-check services.

### For most PNG citizens
Use the **Papua New Guinea Police Character Check** for general employment and character-check purposes.

### Other services
- PMV Character Check
- Firearms Character Check
- Expatriate in PNG Character Check
- Expatriate Overseas Character Check
- Police Crime Report

> **Do not assume every service has the same requirements or processing time.** This guide focuses mainly on the standard PNG Police Character Check and the newer online process."""),
            ("Decide whether to use the online or manual process", """### Online process
RPNGC says the **Online Police Clearance** service is available for **NCD and Central Province**. You begin through the PNG Government Portal and then attend in person for biometric capture.

### Manual process
You can download or collect a police clearance form, pay the prescribed fee, attach the receipt and lodge it with the National Criminal Records Office (NCRO) or the instructed police location.

> If the online service is not available in your province, use the current manual procedure published by RPNGC or ask your nearest police station/NCRO office."""),
            ("Create your government portal profile for an online application", """For the online route, go to the PNG Government Portal and create an account.

RPNGC says the profile asks for details including:
- Full name
- Date and place of birth
- Village, district and province
- Phone number and email
- Residential address
- Passport number
- NID number
- A clear passport-sized profile photo

> **Use your NID number in the NID field.** RPNGC specifically warns not to enter a driver's licence number there."""),
            ("Start the Police Clearance service and select your purpose", """After logging into the Government Portal:

1. Open **Police Clearance Services**.
2. Check that your profile information is correct.
3. Select the **purpose** of the police clearance.
4. Continue to the payment instructions.

Use names and identity details that match your official documents. Differences in spelling or dates can create verification problems later."""),
            ("Pay the correct fee and keep the receipt number", """For a standard **PNG Police Character Check**, RPNGC lists a fee of **K65**.

For the online service, RPNGC directs applicants to the Finance E-Receipting portal and says the emailed receipt number (for example an `ERG...` number) must be entered into the police-clearance application.

### Online-payment warning
RPNGC says:
- the online process currently uses the Finance E-Pay/BSP Pay service;
- third-party payments may not be recognised;
- an EFTPOS payment does **not** substitute for the required online receipt workflow.

> **Keep your receipt.** Payment evidence is part of the application process."""),
            ("Attend Gordons for fingerprint capture if using the online service", """The online application is **not fully remote**.

RPNGC instructs online applicants to attend the **NCRO Online Services Desk at Gordons Police Station** for:
- receipt/payment verification;
- **ten-fingerprint biometric capture**;
- profile verification; and
- final online lodgement.

RPNGC's online page currently lists fingerprint collection/payment verification **Monday to Friday, 9:00 am–3:00 pm**.

> Check the RPNGC page shortly before travelling because counter schedules can change."""),
            ("Wait for vetting and receive the clearance", """After lodgement, the NCRO vetting team checks the application and the Officer in Charge reviews it.

For the online route, RPNGC says successful applicants receive an **email notification with the Police Clearance attached**, including a verification barcode.

For the standard manual PNG Police Character Check, RPNGC currently states an indicative processing period of **about one week**.

Keep the digital and/or printed certificate safely, especially if it is required for an employer, visa, licence or government application."""),
        ],
        "references": [
            ("Police Clearance", "https://rpngc.gov.pg/advice-services/police-clearance/", "Royal Papua New Guinea Constabulary"),
            ("Online Police Clearance", "https://rpngc.gov.pg/advice-services/epolice-clearance/", "Royal Papua New Guinea Constabulary"),
            ("RPNGC Advice & Services", "https://rpngc.gov.pg/advice-services/", "Royal Papua New Guinea Constabulary"),
        ],
    },
    {
        "slug": "how-to-get-a-tin-in-papua-new-guinea",
        "title": "How to Get a TIN in Papua New Guinea",
        "summary": """A practical guide to registering for a **Taxpayer Identification Number (TIN)** with the Papua New Guinea Internal Revenue Commission (IRC).

## At a glance

- **Individuals:** use **Form TIN2**
- **Businesses / companies / other entities:** use **Form TIN1**
- IRC's forms say **incomplete applications will not be processed**
- Individual applicants must provide acceptable proof of identity
- Non-PNG citizens must provide passport details and a passport copy for individual registration

> **TIN is not the same thing as business registration.** IPA registers the business/entity; IRC registers the taxpayer.

This guide uses official IRC forms and taxpayer guidance checked **5 October 2026**.""",
        "source_note": "Official PNG IRC TIN forms and taxpayer guidance checked 5 October 2026.",
        "steps": [
            ("Choose the correct TIN form", """The IRC separates TIN registration into two main application types.

### Individual — Form TIN2
Use **TIN2** if you are registering yourself as an individual taxpayer.

### Non-individual — Form TIN1
Use **TIN1** for an enterprise or other non-individual taxpayer, including a business entity.

Both forms can also be used for certain registration changes, closure of a taxpayer file, or a request to reprint a TIN certificate.

> If you are starting a business, do not use the individual form simply because you personally own the business. Check which taxpayer/entity type IRC requires for your structure."""),
            ("Download the official form and taxpayer guide", """Download the current form from the **PNG Internal Revenue Commission** website.

For individuals, use **TIN2 – Individual TIN Application**. IRC also publishes a taxpayer guide explaining how to complete the TIN registration fields.

For businesses/entities, use **TIN1 – Non-Individual TIN Application**.

> **Avoid old forms copied from social media or third-party sites** when an official IRC copy is available."""),
            ("Prepare your identity documents for an individual TIN", """Form TIN2 requires at least one acceptable form of identification and provides fields for items such as:

- Passport
- National ID (NID) card
- Driver's licence
- Birth certificate
- Other identification such as an employee or student ID where accepted under IRC's proof-of-identity guidance

The form asks for identifying details including document number, issue/expiry information and issuing authority where applicable.

### Non-PNG citizens
IRC's individual form states that non-PNG citizens must provide **passport details and a photocopy of the passport** for registration."""),
            ("Prepare enterprise details for a business or organisation", """Form TIN1 is for **non-individual taxpayers**.

Be ready to provide accurate enterprise information, including the registered/trading identity and relevant registration details. The form asks whether you are registering an enterprise, changing registration information, closing a taxpayer file, or requesting a reprint.

If the entity is already registered with IPA, make sure the name and registration information you give IRC match the official IPA record.

> **Consistency matters:** mismatched entity names, dates or registration details can delay processing."""),
            ("Complete every compulsory field", """IRC's TIN forms explicitly warn that **incomplete forms will not be processed**.

Before lodging:
- Check spelling of legal names
- Check dates of birth and identity-document numbers
- Provide current contact details
- Complete all compulsory/yellow fields on the form
- Sign declarations where required
- Attach the supporting documents relevant to your application

> Do a final line-by-line check before submission. A missing compulsory field can turn a simple registration into a repeat visit."""),
            ("Lodge the application with IRC", """Submit the completed TIN application and supporting documents through the current IRC lodgement channel available to you.

Because IRC service channels and office procedures can change, confirm the current lodgement method on **irc.gov.pg** or with your nearest IRC office before travelling.

Keep a copy of the completed form and any acknowledgement or receipt you receive."""),
            ("Keep your TIN details and update IRC when your information changes", """Once registered, keep your TIN certificate/number with your tax and business records.

The same registration forms also provide for changes to taxpayer contact or registration details and requests for a TIN certificate reprint.

For businesses, remember that obtaining a TIN does not by itself complete every tax obligation. Depending on your activities and thresholds, additional registrations or returns may apply."""),
        ],
        "references": [
            ("TIN2 – Individual TIN Application", "https://static.irc.gov.pg/2021/December/dBO0N5-media-2016-03-17-TIN2-Individual-TIN-Application.pdf", "PNG Internal Revenue Commission"),
            ("TIN1 – Non-Individual TIN Application", "https://static.irc.gov.pg/2021/December/u0GmyZ-media-2016-03-17-TIN1-Non-Individual-TIN-Application.pdf", "PNG Internal Revenue Commission"),
            ("TIN Form Taxpayer Guide", "https://static.irc.gov.pg/2021/December/3D9gmK-media-2016-TPG-TIN1-03-TIN-Form-Taxpayer-Guide.pdf", "PNG Internal Revenue Commission"),
            ("PNG Internal Revenue Commission", "https://irc.gov.pg/", "PNG Internal Revenue Commission"),
        ],
    },
    {
        "slug": "how-to-register-a-business-name-with-ipa-png",
        "title": "How to Register a Business Name with IPA PNG",
        "summary": """A practical guide to registering a **business name** with Papua New Guinea's Investment Promotion Authority (IPA) through the online Business Entity Registry.

## At a glance

- **Online business-name registration fee:** K150
- **Paper fee shown by IPA:** K200
- You need an **IPA registry account** to apply online
- You may enter **up to 3 proposed names**
- IPA emails the **Certificate of Registration** after approval
- A business name **does not create a separate legal entity**
- Current **business-name renewal fee:** K150

> **Business name or company?** A business-name registration is not the same as incorporating a company. Choose the structure you actually need before filing.

Official IPA registry information and fee schedules checked **5 October 2026**.""",
        "source_note": "Official PNG IPA Business Entity Registry sources and fee schedule checked 5 October 2026.",
        "steps": [
            ("Decide whether a business name is the right structure", """IPA states that a **Business Name must be registered by anyone carrying on business under a name other than their own**.

A business-name certificate lets you trade under that registered name, but under the Business Names Act it **does not create a separate legal entity**.

### Consider a company instead if you need
- a separate incorporated legal entity;
- a shareholding structure;
- directors and formal company governance; or
- the liability/ownership structure of a company.

> This guide covers **business-name registration**, not company incorporation."""),
            ("Create an IPA Business Entity Registry account", """To register online, create a client account in IPA's **Business Entity Registry**.

After creating the account:
1. Log in.
2. Select **Business Entities**.
3. Open the business-name registration process.

Use an email address you can reliably access because IPA uses email for application communication and the registration certificate."""),
            ("Choose up to three proposed business names", """IPA allows you to enter **up to 3 potential business names**.

The proposed name cannot be the same as, or nearly the same as, another registered entity name.

Providing alternatives is useful because if your first choice is rejected, the application may still proceed using the next acceptable choice.

> **Tip:** Search the registry before applying and avoid names that could easily be confused with an existing business."""),
            ("Gather the owner and business details", """IPA says the online application collects information including:

- Name and address of the applicant
- Names and addresses of each owner
- Registration number if an owner is an existing IPA-registered entity
- Principal place of business
- Additional business locations, if applicable
- Postal address
- Primary business activity
- Foreign-investor status where applicable

If an owner is a foreign investor, IPA notes that **foreign investor certification** may also be required."""),
            ("Complete and review the online application", """Work through each section of the online filing carefully.

You can use **Save Draft** if you need to stop and return later. When all required information is complete, review the application and select **Complete** / the relevant submission action.

The filing includes a declaration that the information submitted is true.

> Before submitting, make sure owner names, addresses and the business activity are correct. These details become part of the official registry record."""),
            ("Pay the registration fee", """IPA's current prescribed-forms fee schedule lists **Form A-17 – Application for registration of business name** at:

- **K150 web fee**
- **K200 paper fee**

Use the fee shown by IPA at the time you submit, because prescribed fees can change.

> Do not confuse the initial registration fee with later renewal, penalty or restoration fees."""),
            ("Wait for Registrar review and receive your certificate", """After submission, IPA sends the application to the Registrar for review.

### If more information is needed
The application may be placed in **pending** status until you provide what the Registrar requests.

### If approved
IPA says the **Certificate of Registration of a Business Name** is emailed to you.

Keep the certificate and your registry login details safely. You will need the registry again for future filings and renewals."""),
            ("Renew the business name and keep the registry record current", """IPA's current registry guidance lists a **K150 renewal fee** for business-name registration.

If ownership, address or business details change, use the appropriate IPA filing to update the record.

Late or lapsed registrations can attract additional restoration and penalty costs, so do not ignore renewal notices.

> **Practical rule:** treat your IPA account, certificate and renewal date as permanent business records—not one-time setup paperwork."""),
        ],
        "references": [
            ("Registering a Business Name", "https://www.ipa.gov.pg/public/howto.aspx?cn=AccessBusinessEntities&lang=en-US", "Investment Promotion Authority"),
            ("IPA Prescribed Forms and Fees", "https://www.ipa.gov.pg/public/prescribedforms.aspx", "Investment Promotion Authority"),
            ("IPA Forms for Download", "https://www.ipa.gov.pg/public/help.aspx?cn=FormsForDownload", "Investment Promotion Authority"),
            ("Business Names Act 2014", "https://www.ipa.gov.pg/Documentation/PG/ActsAndRegulations/Bus-Names-Act-2014.pdf", "Investment Promotion Authority"),
        ],
    },
]


def add_guides(apps, schema_editor):
    Guide = apps.get_model("guides", "Guide")
    GuideVersion = apps.get_model("guides", "GuideVersion")
    GuideReference = apps.get_model("guides", "GuideReference")
    Step = apps.get_model("guides", "Step")
    BusinessCategory = apps.get_model("categories", "BusinessCategory")

    passport_guide = Guide.objects.filter(slug="how-to-get-a-new-papua-new-guinea-png-passport").first()
    category = BusinessCategory.objects.filter(name="Services & utilities").first()

    for data in GUIDES:
        if Guide.objects.filter(slug=data["slug"]).exists():
            continue

        guide = Guide.objects.create(
            title=data["title"],
            slug=data["slug"],
            summary=data["summary"],
            category=category,
            created_by_id=passport_guide.created_by_id if passport_guide else None,
            created_via="mcp",
            ai_assisted=True,
            ai_provider="OpenAI",
            ai_model="GPT-5.6 Sol",
            ai_source_note=data["source_note"],
        )

        version = GuideVersion.objects.create(
            guide=guide,
            edited_by_id=guide.created_by_id,
            status="published",
            edit_summary=f"Initial {data['title']} guide based on official PNG sources",
            created_via="mcp",
            ai_assisted=True,
            ai_provider="OpenAI",
            ai_model="GPT-5.6 Sol",
            ai_source_note=data["source_note"],
        )

        for position, (title, instruction) in enumerate(data["steps"], start=1):
            Step.objects.create(version=version, position=float(position), title=title, instruction=instruction)

        for title, url, publisher in data["references"]:
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
    dependencies = [("guides", "0012_add_png_nid_guide")]

    operations = [migrations.RunPython(add_guides, migrations.RunPython.noop)]
