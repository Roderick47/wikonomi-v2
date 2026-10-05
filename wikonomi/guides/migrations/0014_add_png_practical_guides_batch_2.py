from datetime import date

from django.db import migrations


GUIDES = [
    {
        "slug": "how-to-buy-and-enter-png-power-easipay",
        "title": "How to Buy and Enter PNG Power Easipay",
        "category": "Services & utilities",
        "summary": """A practical guide to buying PNG Power Easipay credit, receiving your token and loading it into your prepaid electricity meter.

## At a glance

- **Easipay is prepaid electricity**: you buy power before using it.
- PNG Power lists a **minimum purchase of K15**.
- You can buy through supported mobile/banking channels, PNG Power offices and authorised agents.
- You receive a **16–20 digit token** and enter it into the Easipay meter keypad.
- PNG Power's national call centre is **116**.

> **Important:** Always check the meter number before paying. An Easipay token is created for the meter number used in the purchase.

This guide is based on PNG Power's official Easipay information checked on **5 October 2026**.""",
        "steps": [
            ("Find your Easipay meter number", """Before buying power, locate the **meter number** for the Easipay meter you want to top up.

Use the number shown on the meter, a previous Easipay receipt/token, or the meter details provided for the property.

> **Double-check every digit.** If you buy against the wrong meter number, the token will normally only work on that meter."""),
            ("Choose where to buy Easipay", """PNG Power lists several purchase channels, including:

- Supported mobile phone services
- Banking apps/mobile banking
- PNG Power offices
- Authorised retail agents

PNG Power currently lists **K15 as the minimum Easipay purchase**.

Different channels can have different transaction limits and service fees, so check the amount shown before confirming."""),
            ("Buy the token", """Enter your Easipay **meter number** and the amount you want to buy in the selected channel.

Before confirming:

1. Re-check the meter number.
2. Re-check the amount.
3. Make sure you have enough balance to cover any channel fee.
4. Confirm the transaction only when the details are correct.

Keep the transaction reference until the power units have loaded successfully."""),
            ("Receive and save the Easipay token", """After a successful purchase, you should receive or see the Easipay token on screen, by SMS, or in the banking/app transaction record.

PNG Power describes Easipay tokens as **16–20 digits**.

> **Do not discard the token or transaction reference** until the meter accepts it."""),
            ("Enter the token into the meter", """At the Easipay meter:

1. Wake the keypad/display if necessary.
2. Enter the token digits carefully in order.
3. Confirm/submit using the meter keypad.
4. Wait for the meter to show that the token has been accepted and the units added.

If the token is rejected, check the digits and confirm the token belongs to that meter."""),
            ("Check your remaining power", """PNG Power says Easipay meters use indicator lights to help show remaining credit:

- **Green:** sufficient credit
- **Amber/orange:** roughly one week remaining
- **Red:** roughly three days remaining

Treat these as prompts to top up early rather than waiting for the power to run out."""),
            ("Fix a missing or rejected token", """If the token does not arrive or the meter rejects it:

- Check the transaction history or SMS again.
- Check that the meter number used for the purchase matches the actual meter.
- Re-enter the token carefully.
- Keep the transaction reference and token number.
- Contact PNG Power on **116** if the problem continues.

> If you used the wrong meter number, contact PNG Power as soon as possible with the transaction reference. Do not assume the token can simply be moved to another meter."""),
        ],
        "refs": [
            ("EasiPay Prepaid Power", "https://www.pngpower.com.pg/help/easipay", "PNG Power Limited"),
        ],
        "source_note": "Official PNG Power Easipay information checked 5 October 2026.",
    },
    {
        "slug": "how-to-register-a-sim-card-in-papua-new-guinea",
        "title": "How to Register a SIM Card in Papua New Guinea",
        "category": "Services & utilities",
        "summary": """A practical guide to registering and activating a mobile SIM card in Papua New Guinea, with a note on the coming SevisPass-based registration changes.

## At a glance

- Mobile SIMs must be registered before normal service is activated.
- Operators currently require you to be **physically present** and provide an **original valid ID** or approved identity verification.
- Vodafone PNG lists accepted IDs including NID, driver's licence, passport, birth certificate, baptism certificate, student ID, marriage certificate and superannuation-fund ID.
- NICTA completed consultation in 2026 on a new system that would integrate **SevisPass digital identity**.

> **Current-vs-upcoming:** This guide separates the process mobile operators publish **now** from the SevisPass changes proposed/finalised through the 2026 regulatory process. Check your operator before travelling to register.

Sources checked **5 October 2026**.""",
        "steps": [
            ("Go to an authorised operator registration point", """Buy or take your SIM to an authorised outlet, kiosk, roadshow team or other registration point published by your mobile operator.

For example, Vodafone PNG states that a new SIM is registered and activated through its retail outlets, kiosks and roadshows.

> Avoid handing identity documents to unofficial sellers who cannot show that they are authorised to register SIMs."""),
            ("Take an original valid ID", """Take the strongest government-issued identity document you have.

Vodafone PNG currently lists examples including:

- National ID (NID) card
- Driver's licence
- Passport
- Birth certificate
- Baptism certificate
- Student ID
- Marriage certificate
- Superannuation fund ID

Operator requirements can differ, so **NID or passport** is the safest option when available."""),
            ("Provide your registration details in person", """The operator may record details such as your:

- Full name
- Gender
- Date of birth
- Residential address
- Nationality
- Place of origin
- Occupation

Vodafone's published process also says a copy/image of the ID and a **facial photo** are retained for customer records."""),
            ("If you do not have standard ID, ask about verifier options", """Some operator rules provide alternatives where a person does not have a normal identification document.

Vodafone describes an option involving a reputable person who presents their own identification and verifies the applicant's identity, such as certain community officials, disciplinary-force members, village-court magistrates or registered church pastors.

> Do not assume every operator or outlet will accept the same verifier process. Ask first."""),
            ("Wait for activation and test the SIM", """Once registration is successfully completed, the operator activates the SIM for use.

Before leaving the outlet:

1. Confirm the SIM shows network signal.
2. Make a test call or check data if possible.
3. Confirm the number registered is the one you were issued.
4. Keep the SIM pack or account details in case you later need a replacement SIM."""),
            ("Be aware of the SevisPass transition", """NICTA concluded nationwide consultation in **March 2026** on a consolidated SIM-registration regulation intended to integrate **SevisPass** and stronger digital identity verification.

The policy direction includes linking adult SIM registration with SevisPass-based identity verification.

> Because the regulatory rollout is still evolving, follow the process your operator is actually implementing on the day you register. Do not rely on an older social-media post or assume every outlet has moved to the new system at the same time."""),
        ],
        "refs": [
            ("Vodafone PNG SIM Registration Process", "https://vodafone.com.pg/about/about-us/customer-care/registration-process", "Vodafone PNG"),
            ("SIM Card Registration (Amendment and Consolidation) Regulation 2026 Consultation", "https://www.nicta.gov.pg/public-consultation-on-the-sim-card-registration-amendment-and-consolidation-regulation-2026/", "NICTA"),
            ("SevisPass to be used for SIM Card Registration", "https://www.ict.gov.pg/sevispass-to-be-used-for-sim-card-registration-nicta-concludes-consultation-on-sim-card-registration-regulation-with-stakeholders/", "Department of ICT"),
        ],
        "source_note": "Official NICTA/DICT and operator SIM-registration sources checked 5 October 2026.",
    },
    {
        "slug": "how-to-register-a-birth-and-get-a-birth-certificate-in-png",
        "title": "How to Register a Birth and Get a Birth Certificate in PNG",
        "category": "Services & utilities",
        "summary": """A practical guide to birth registration and obtaining a birth certificate through the Papua New Guinea Civil and Identity Registry (PNGCIR).

## At a glance

- Birth registration creates the official civil record of a person's birth.
- PNGCIR provides a **Birth & National Identity Registration Form** for registration.
- For adults, birth registration is closely linked with the NID process.
- Supporting records are especially important when a birth was not registered soon after it occurred.

> If you are **18 or older and have never been registered**, also read Wikonomi's NID guide because PNGCIR registers adults for birth and NID together.

Official PNGCIR sources checked **5 October 2026**.""",
        "steps": [
            ("Work out whether the birth is already registered", """First determine whether PNGCIR already has a civil-registration record for the person.

If you already have a birth certificate or NID record, you may need a **certificate/reprint, correction or amendment** rather than a fresh registration.

If there has never been a registration, proceed with birth registration."""),
            ("Download or obtain the birth registration form", """PNGCIR provides the **Birth & National Identity Registration Form** in its Downloads section.

Complete the form carefully using the person's details **as they were at birth**, including the correct name, date and place of birth and parent information.

> Spelling matters. A small error in a name or date of birth can later affect NID, passport, banking, school and employment records."""),
            ("Gather supporting birth and identity records", """Useful supporting records can include:

- Clinic or health record book
- Baptism record
- School records
- Existing passport or ID
- Parent or guardian identity documents
- Existing birth/NID records for close family members
- Informant, verifier or witness documentation where PNGCIR requires it

The exact evidence depends on when and where the birth occurred and whether it was recorded at the time."""),
            ("Arrange a verifier if the birth was never formally documented", """For late or poorly documented registrations, PNGCIR may require stronger evidence and a verifier/witness process.

Examples in PNGCIR guidance include community or local officials and other recognised persons who can verify identity or birth information.

> Ask PNGCIR what applies to your case before paying for declarations or collecting documents you may not need."""),
            ("Submit the registration through PNGCIR", """Take the completed form and supporting evidence to the appropriate **PNG Civil and Identity Registry** registration point.

For adult NID registration, in-person biometric capture is required, so an online/downloaded form is preparation—not a full online registration."""),
            ("Check the details before the record is finalised", """Before leaving, check the key details recorded for the person:

- Full name and spelling
- Date of birth
- Place of birth
- Parent names
- Sex/gender entry

If anything is wrong, raise it immediately. Formal amendments later can require a separate process."""),
            ("Keep your receipt/reference and follow up", """Keep any lodgement slip, reference or receipt provided by PNGCIR.

Use PNGCIR's official contact channels to follow up if the birth certificate is delayed or if you are told further evidence is required.

> Avoid creating a duplicate registration unless PNGCIR specifically instructs you to do so."""),
        ],
        "refs": [
            ("PNGCIR Downloads", "https://pngcir.gov.pg/downloads/", "PNG Civil and Identity Registry"),
            ("What is Birth Registration?", "https://pngcir.gov.pg/faq/what-is-birth-registration/", "PNG Civil and Identity Registry"),
            ("NID Registration Information", "https://pngcir.gov.pg/nid-registration-information/", "PNG Civil and Identity Registry"),
        ],
        "source_note": "Official PNG Civil and Identity Registry birth-registration sources checked 5 October 2026.",
    },
    {
        "slug": "how-to-register-a-marriage-in-papua-new-guinea",
        "title": "How to Register a Marriage in Papua New Guinea",
        "category": "Services & utilities",
        "summary": """A practical guide to civil marriage registration in Papua New Guinea and the official recording needed for a marriage certificate.

## At a glance

- PNGCIR describes marriage registration as the **official recording of a marriage event**.
- A civil/state marriage is conducted by a registered celebrant or authorised official under PNG marriage law.
- PNG law requires marriages solemnised in PNG to be registered.
- The authorised celebrant is required to notify the Registrar-General, and the registration form is signed by the couple and **two witnesses**.

> **Customary and civil/state marriage are not the same process.** This guide focuses on obtaining an official civil-registration record/certificate.

Official sources checked **5 October 2026**.""",
        "steps": [
            ("Decide whether you need to solemnise a marriage or register an existing one", """There are two different situations:

### You are planning a civil/state marriage
Arrange the marriage through an authorised/registered celebrant or appropriate government official.

### You are already married
If a marriage event has already occurred but is not properly recorded, ask PNGCIR what registration process and evidence are required for that marriage."""),
            ("Use an authorised celebrant for a civil/state marriage", """PNGCIR explains that a **civil/state marriage** is conducted by a registered celebrant or a Provincial Administrator under the Marriage Act framework.

Confirm the celebrant is authorised before paying fees or making arrangements.

> A ceremony by itself does not replace the civil-registration requirements needed for an official government marriage record."""),
            ("Prepare the couple's identity details and witnesses", """Have the identification and civil-status details requested by the celebrant/PNGCIR ready.

The registration process requires the couple's assent/signatures and **two witnesses** on the marriage registration form.

Bring original identification where requested and make sure names match your NID, birth or passport records."""),
            ("Complete the marriage registration form", """PNGCIR provides a **Civil Marriage Registration Form** in its Downloads section.

The authorised celebrant records the marriage information and completes the notification/registration requirements.

Under PNG's civil-registration law, an authorised celebrant who solemnises a marriage must notify the Registrar-General within the required period."""),
            ("Make sure the celebrant submits the registration", """PNG law places the notification duty on the authorised celebrant and requires the marriage to be notified to the Registrar-General.

Before you leave the process, ask:

- Has the registration form been fully signed?
- Are both witnesses recorded?
- Who submits the form to PNGCIR?
- What reference or proof can you keep while waiting for the certificate?"""),
            ("Apply for or collect the official marriage certificate", """Once the marriage is registered, the official civil record supports the issue of a marriage certificate.

A registered marriage certificate can be important for:

- Legal proof of marriage
- Travel/immigration matters
- Inheritance
- Benefits and entitlements
- Nationality/citizenship matters
- Other government or financial processes

Keep the certificate secure and use certified copies where organisations allow them."""),
        ],
        "refs": [
            ("PNGCIR Downloads – Civil Marriage Registration Form", "https://pngcir.gov.pg/downloads/", "PNG Civil and Identity Registry"),
            ("What is Marriage?", "https://pngcir.gov.pg/faq/what-is-marriage/", "PNG Civil and Identity Registry"),
            ("Civil and Identity Registration Act – Registration of Marriages", "https://www.parliament.gov.pg/uploads/acts/24A-21.pdf", "National Parliament of Papua New Guinea"),
        ],
        "source_note": "Official PNGCIR and PNG legislation sources checked 5 October 2026.",
    },
    {
        "slug": "how-to-register-or-renew-a-motor-vehicle-in-png",
        "title": "How to Register or Renew a Motor Vehicle in Papua New Guinea",
        "category": "Automotive & transport",
        "summary": """A practical guide to first-time vehicle registration and registration renewal in Papua New Guinea, including roadworthiness and third-party insurance requirements.

## At a glance

- The **Road Traffic Authority (RTA)** has overall responsibility for vehicle registration.
- Registration services are delivered through **MVIL and some Provincial Governments**.
- First registration requires identity/owner details, a **roadworthiness certificate issued within 30 days**, current third-party insurance and the prescribed fee.
- Renewal also requires a current roadworthiness certificate, third-party insurance and the renewal fee.
- Registration is generally valid for **12 months** under the current rules.

Official RTA information checked **5 October 2026**.""",
        "steps": [
            ("Use the correct registration service provider", """RTA has overall responsibility for vehicle registration, but its official page states that service delivery is currently carried out by **Motor Vehicles Insurance Limited (MVIL)** and some Provincial Governments.

Contact the relevant service-delivery office for your location before travelling, especially if you need an inspection or first registration."""),
            ("Get the vehicle roadworthiness certificate", """For first registration and renewal, RTA requires a **certificate of roadworthiness issued within the 30 days immediately before the application**.

Arrange the required roadworthiness inspection through the authorised service process.

> Do this close enough to your registration date that the certificate is still within the 30-day window."""),
            ("Arrange current third-party insurance", """RTA also requires **evidence of current third-party insurance** for the vehicle.

Make sure the insurance details identify the correct vehicle and remain valid when you lodge the registration or renewal."""),
            ("Complete Form 7 and prepare owner details", """RTA says a person may apply for first registration or renewal using **Form 7**.

For first registration, prepare details including:

- Owner's full name
- Residential/business address in PNG
- PNG postal address if different
- Date of birth if the owner is an individual
- Evidence of identity such as a driver's licence or passport
- Vehicle information/documents requested by the authority"""),
            ("Submit the application and pay the prescribed fee", """Lodge the application with the relevant registration service provider together with:

- Completed application
- Required owner/vehicle documents
- Roadworthiness certificate
- Current third-party insurance evidence
- Prescribed registration/renewal fee

Fees vary by vehicle class and service, so confirm the current amount with the service provider rather than relying on an old fee table."""),
            ("Present the vehicle if an inspection is required", """The registration authority may direct that the vehicle be **produced for inspection**.

RTA rules allow limited circumstances where production can be waived if it is unreasonable or impracticable and sufficient evidence of fitness for registration is provided.

Do not assume a waiver applies—follow the service provider's instruction."""),
            ("Receive the registration documents and plates", """On registration, the authority issues the applicable registration documents and number plate(s).

Keep the certificate and registration details safe and ensure the plate(s) are properly displayed as required.

Public motor vehicles, private hire cars and taxis have additional licensing/registration requirements beyond ordinary private-vehicle registration."""),
            ("Renew before expiry", """Current RTA guidance states that registration is generally valid for **12 months** unless cancelled or suspended sooner.

For renewal, again prepare:

- A roadworthiness certificate issued within 30 days
- Current third-party insurance
- The prescribed renewal fee

Renew on time so you do not create avoidable registration or insurance problems."""),
        ],
        "refs": [
            ("Vehicle Registration", "https://www.rta.gov.pg/licences-approvals/vehicle-registration/", "Road Traffic Authority PNG"),
        ],
        "source_note": "Official Road Traffic Authority vehicle-registration information checked 5 October 2026.",
    },
]


def add_guides(apps, schema_editor):
    Guide = apps.get_model("guides", "Guide")
    GuideVersion = apps.get_model("guides", "GuideVersion")
    GuideReference = apps.get_model("guides", "GuideReference")
    Step = apps.get_model("guides", "Step")
    BusinessCategory = apps.get_model("categories", "BusinessCategory")

    author_guide = Guide.objects.filter(created_by_id__isnull=False).order_by("id").first()
    author_id = author_guide.created_by_id if author_guide else None

    for data in GUIDES:
        if Guide.objects.filter(slug=data["slug"]).exists():
            continue

        category = BusinessCategory.objects.filter(name=data["category"]).first()
        guide = Guide.objects.create(
            title=data["title"],
            slug=data["slug"],
            summary=data["summary"],
            category=category,
            created_by_id=author_id,
            created_via="mcp",
            ai_assisted=True,
            ai_provider="OpenAI",
            ai_model="GPT-5.6 Sol",
            ai_source_note=data["source_note"],
        )

        version = GuideVersion.objects.create(
            guide=guide,
            edited_by_id=author_id,
            status="published",
            edit_summary=f"Initial guide: {data['title']}",
            created_via="mcp",
            ai_assisted=True,
            ai_provider="OpenAI",
            ai_model="GPT-5.6 Sol",
            ai_source_note=data["source_note"],
        )

        for position, (title, instruction) in enumerate(data["steps"], start=1):
            Step.objects.create(
                version=version,
                position=float(position),
                title=title,
                instruction=instruction,
            )

        for title, url, publisher in data["refs"]:
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
        ("guides", "0013_add_police_tin_ipa_guides"),
    ]

    operations = [
        migrations.RunPython(add_guides, migrations.RunPython.noop),
    ]
