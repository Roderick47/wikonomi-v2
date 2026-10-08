"""Add five researched PNG guides to Wikonomi V2 without changing existing data.

A data-only and idempotent migration; atomic on PostgreSQL. Existing user guides,
accounts, prices and other content are never updated or deleted.
"""
from datetime import date
from django.db import migrations

GUIDES = [
  {
    "slug": "register-company-ipa-png",
    "title": "How to Register a Company with IPA in Papua New Guinea",
    "category": "Professional & business services",
    "summary": "Learn how to reserve a company name, incorporate a PNG company online through IPA, obtain your certificate, and complete the next compliance steps. This is for a new PNG-incorporated company—not merely a business-name registration.\n\n## At a glance: fees and deadlines\n\nPublished IPA web fees: N-1 company-name reservation K50; A-1 online incorporation K400; budget K450 in official filing fees if both apply. Annual company return AR-1 K250 after incorporation. Foreign-enterprise certification, if required, is a separate process and fee (IPA lists K2,000 for applicable initial foreign-enterprise filings). Confirm the checkout total before paying. No guaranteed approval time is published here.\n\n## Before you start\n\n- A proposed company name and a backup name.\n- Working email, telephone, and PNG business/registered office and service/postal addresses.\n- Names and particulars of all proposed directors, shareholders, and any secretary; planned share structure.\n- Primary business activity and the decision whether the company will adopt a constitution.\n- Government-issued photo ID to create the IPA registry account, plus supporting documents requested by the registry.\n- Payment method accepted by IPA; consider professional advice for foreign ownership or unusual shareholding arrangements.\n\n## Common mistakes to avoid\n\n- Confusing a business-name certificate with a company incorporation certificate.\n- Entering informal names or incorrect addresses for directors/shareholders.\n- Assuming the company can charge GST immediately after IPA registration.\n- Forgetting annual returns, other business licensing, or the company TIN.\n\n> **Community guide:** Information checked on 8 October 2026. Fees, forms, and procedures can change. Confirm current requirements with the organisations linked below before paying or filing. This guide is not official advice.",
    "steps": [
      [
        "Choose the right registration type",
        "A company is a separate legal entity. A business name is not the same as a company. Choose incorporation if you need a company (for example, a limited-liability business with directors and shareholders); check the implications of liabilities and ongoing filings before applying."
      ],
      [
        "Create an IPA registry account",
        "Go to https://www.ipa.gov.pg/ and choose Create Account / Business Entities account. Enter your contact and account information. The registry requires a scanned government-issued photo ID for the account administrator. Keep your login details secure."
      ],
      [
        "Search and reserve the company name",
        "Use the IPA Business Entities registry name search. Submit a company-name reservation (N-1), pay the displayed fee, and wait until the name is approved. The published online N-1 fee is K50. Do not order branding or promise the name is yours before approval."
      ],
      [
        "Collect director, shareholder and company details",
        "Confirm spelling and identity details against official IDs. Enter registered office, service and postal addresses, business activity, directors, any secretary, and the proposed shares/shareholders. Decide whether to adopt a constitution; get appropriate advice if the ownership structure is complicated."
      ],
      [
        "Complete IPA incorporation Form A-1",
        "After the name reservation is approved, select Register a PNG Company and complete Form A-1 online. Fill every required section, including shares, addresses, constitution, primary business activity and declaration. Use Save Draft to pause and check all entries before checkout."
      ],
      [
        "Pay and await the incorporation decision",
        "Submit the application and pay the web fee listed by IPA (K400 for A-1 on the current fee schedule). Check email for IPA queries and respond to requested corrections. The Certificate of Incorporation is emailed after approval, not merely after payment."
      ],
      [
        "Obtain the TIN and complete operating requirements",
        "Register the new company with IRC for a Taxpayer Identification Number (TIN), confirm any Certificate of Compliance requirements, then arrange its business bank account. Separately check local trading licences, sector permits, employer/SWT registration and GST registration if applicable. An IPA certificate alone is not permission to carry on every regulated activity."
      ],
      [
        "Keep the company in good standing",
        "Store incorporation documents and a record of directors/shareholders. Track annual IPA filings and changes to registered details. IPA lists K250 for an AR-1 annual return; other filings and late fees may apply."
      ]
    ],
    "references": [
      [
        "IPA — incorporation walkthrough",
        "https://www.ipa.gov.pg/public/howto.aspx?cn=AccessBusinessEntities&lang=en-US",
        "Investment Promotion Authority"
      ],
      [
        "IPA — prescribed fees (N-1, A-1 and AR-1)",
        "https://www.ipa.gov.pg/public/prescribedforms.aspx",
        "Investment Promotion Authority"
      ],
      [
        "IPA — create registry account",
        "https://www.ipa.gov.pg/public/setupaccount.aspx?lang=en-US",
        "Investment Promotion Authority"
      ],
      [
        "PNG National Trade Portal — doing business",
        "https://nto.gov.pg/doing-business-in-png/",
        "nto.gov.pg"
      ]
    ]
  },
  {
    "slug": "transfer-vehicle-ownership-png",
    "title": "How to Transfer Ownership of a Vehicle in PNG",
    "category": "Transport & logistics",
    "summary": "Buyer and seller checklist for transferring the registration of a private motor vehicle through the RTA system, with forms, published fee, time limits and MVIL service information.\n\n## At a glance: fees and deadlines\n\nRTA’s published Road Traffic (Fees and Charges) Regulation 2017, Schedule 1 item 24, specifies K115 for transfer of registration. Confirm today’s payable amount with MVIL or the registration service office; insurance, inspection, replacement documents and renewal may cost extra. Both original seller and buyer generally have 14 days from sale/disposal for their required notifications/applications. If a person sells as the owner’s agent, the agent’s notice obligation is 7 days.\n\n## Before you start\n\n- Original/current vehicle registration certificate and its reverse-side transfer details.\n- Registration number; make, model, colour, engine number, chassis number, year and other vehicle particulars.\n- Buyer’s full name, contact and PNG residential/postal address; acceptable ID as requested by the service agent.\n- Seller’s particulars, signed sale agreement/receipt recording date and vehicle identity (recommended evidence).\n- Payment for the transfer; check whether insurance, roadworthiness or registration renewal needs attention.\n- A written authorisation if someone is disposing of the vehicle on behalf of the owner.\n\n## Common mistakes to avoid\n\n- Handing over money without checking the seller’s identity or chassis/engine numbers.\n- Keeping the registration in the old owner’s name after the sale.\n- Confusing private ownership transfer with a PMV/taxi operating-licence transfer.\n- Assuming the published K115 covers unpaid registration renewal, insurance or other service costs.\n\n> **Community guide:** Information checked on 8 October 2026. Fees, forms, and procedures can change. Confirm current requirements with the organisations linked below before paying or filing. This guide is not official advice.",
    "steps": [
      [
        "Check the vehicle and paperwork before paying",
        "Compare the engine and chassis identifiers on the vehicle against the registration certificate. Check that the person selling is the registered owner, confirm registration and insurance status, and ask about finance/security interests. A signed sale receipt is strongly recommended as evidence; it is not a substitute for transfer."
      ],
      [
        "Write a dated sale agreement/receipt",
        "Record both parties’ names and contact details, registration number, chassis/engine numbers, sale date, amount paid, and signatures. Keep a copy each. For agency sales, obtain written authority from the registered owner."
      ],
      [
        "Seller completes the registration certificate notice",
        "The registered seller should complete the back of the certificate of registration with the new owner’s name and address and submit/produce it to the registration authority within 14 days. Someone selling on behalf of an owner has a 7-day notification rule and must provide written authority."
      ],
      [
        "Buyer completes Form 8",
        "Download RTA Form 8: Application for Transfer of Registration of Motor Vehicle. Enter buyer and vehicle particulars accurately, sign in the presence of the required witness as indicated on the form, and check the fee. File within 14 days after purchase."
      ],
      [
        "Lodge with the service-delivery agent and pay",
        "The RTA sets the rules, while its published page identifies MVIL and some provincial governments as the service-delivery agents. Contact your local MVIL/registration office to confirm counter, appointment, required original documents, any identity/inspection requirements and current payment method. Pay the prescribed transfer fee and get a receipt."
      ],
      [
        "Collect proof registration was updated",
        "Confirm the registration record and new certificate show the buyer’s correct name and address. Keep a copy of the new certificate and the receipt; ensure third-party insurance and annual registration requirements remain up to date."
      ],
      [
        "Check special-use vehicles separately",
        "PMVs, taxis and private-hire vehicles can require a separate transport licence transfer and approval. Do not assume ordinary Form 8 alone authorises passenger transport work."
      ]
    ],
    "references": [
      [
        "RTA — Vehicle Registration and sale/transfer rules",
        "https://www.rta.gov.pg/licences-approvals/vehicle-registration/",
        "Road Traffic Authority"
      ],
      [
        "RTA — Form 8 (official PDF)",
        "https://rta.gov.pg/pdfs/forms/Form8.pdf",
        "Road Traffic Authority"
      ],
      [
        "RTA — Fees and Charges Regulation 2017 (schedule item 24)",
        "https://rta.gov.pg/pdfs/licences%26approvals/RT%28FeesAndCharges%29Regulation2017.pdf",
        "Road Traffic Authority"
      ],
      [
        "RTA — passenger vehicle licensing and transfers",
        "https://www.rta.gov.pg/licences-approvals/public-motor-vehicles-private-hire-cars-taxis/",
        "Road Traffic Authority"
      ]
    ]
  },
  {
    "slug": "file-monthly-swt-png",
    "title": "How to Prepare and File a Monthly SWT Return (Form S2) in PNG",
    "category": "Professional & business services",
    "summary": "An employer’s practical checklist for calculating, reconciling, lodging and paying monthly Salary and Wages Tax (SWT) to IRC using Form S2. Includes employees with no tax deducted.\n\n## At a glance: fees and deadlines\n\nMonthly SWT for payroll paid in a calendar month is ordinarily due by the 7th of the next month, or the next working day if the due date is a weekend/public holiday. Form S2 is the monthly group-employer remittance form. No fixed filing fee verified; late payment may incur penalties. Confirm tax calculations against 2026 law/tables—the Income Tax Act 2025 took effect 1 January 2026.\n\n## Before you start\n\n- Employer IRC TIN and group-employer registration details.\n- Payroll records and payslips for every pay date within the month (weekly, fortnightly and/or monthly).\n- List of ALL employees, including casual and those earning too little to have SWT deducted.\n- Gross salary/wages, taxable payments and benefits, deductions, tax withheld, and month-end headcount.\n- Current IRC tax tables/calculation guidance and current S2 filing instructions; myIRC access or the current approved lodgement channel.\n- Payment arrangements and a place to save lodgement acknowledgement/remittance evidence.\n\n## Common mistakes to avoid\n\n- Excluding low-paid employees from total headcount or gross-pay fields.\n- Reporting two fortnights without checking whether three pay dates fell in the month.\n- Confusing taxable salary totals with total gross salary or double-counting allowances.\n- Using old 2015 payroll tax examples as 2026 calculation rates.\n- Lodging a positive SWT return but forgetting to pay, or failing to keep receipts.\n\n> **Community guide:** Information checked on 8 October 2026. Fees, forms, and procedures can change. Confirm current requirements with the organisations linked below before paying or filing. This guide is not official advice.",
    "steps": [
      [
        "Confirm employer SWT registration",
        "An employer liable to withhold SWT should register with IRC as a group employer. Check the business TIN, registered employer/group number, and all applicable payroll establishments before preparing returns. Contact IRC if registration is incomplete."
      ],
      [
        "Select the month based on when wages were paid",
        "Pull every payroll payment date falling in the calendar month. A month may contain two or three fortnightly pay dates. Do not automatically use only the latest two fortnights; use the payroll actually paid during that month."
      ],
      [
        "Reconcile every employee’s gross pay and tax",
        "Combine the payroll registers across establishments. Include permanent, part-time and casual workers; record those whose tax withheld is K0. Check bonuses, commissions, allowances and taxable employment benefits against current IRC guidance. In 2026, the new Income Tax Act can change some benefit valuations."
      ],
      [
        "Fill employer details and reporting period on Form S2",
        "Use the current IRC-approved S2 form/online equivalent. Complete employer name, contact/address and TIN, any establishment field if relevant, and the correct reporting month/year."
      ],
      [
        "Complete the five numerical S2 fields",
        "Enter (2) employee count on payroll at month-end; (3) gross salary/wages paid to ALL employees; (4) count of employees from whom SWT was deducted; (5) gross salary/wages paid to the employees in field 4; and (6) total SWT actually deducted during the month. Field 3 is not the same as field 5 when some workers had no tax withheld."
      ],
      [
        "Cross-check before signing",
        "Reconcile field 3 to total monthly gross payroll, field 5 to the taxed-employee subset, and field 6 to the sum of payroll SWT deductions. Check field 4 does not exceed field 2 without an explained payroll timing/headcount exception. Investigate negative adjustments, terminations and payments to leavers before signing."
      ],
      [
        "Lodge and pay by the deadline",
        "Lodge through myIRC or the current IRC-approved remittance process and pay the SWT liability. IRC communications in 2026 caution that positive SWT remittances must be accompanied by payment. Keep both submission acknowledgement and bank/payment evidence; a submission without settlement may not satisfy the remittance requirement."
      ],
      [
        "Handle a NIL month properly and retain records",
        "If the employer has no SWT due, confirm and follow IRC’s current NIL-return instructions. The published S2 notes call for NIL submission where no deductions were made, and 2026 professional guidance says NIL remittances continue to be accepted. Archive S2, payroll summaries, and payment receipts for reconciliation and annual employee statements."
      ]
    ],
    "references": [
      [
        "IRC — Official Form S2 (older published PDF; verify current version)",
        "https://static.irc.gov.pg/2021/December/VG5U6R-media-2016-01-27-S2-Salary-Wages-Tax-Remittance-by-Group-Employer.pdf",
        "PNG Internal Revenue Commission"
      ],
      [
        "IRC — myIRC portal",
        "https://irc.gov.pg/",
        "PNG Internal Revenue Commission"
      ],
      [
        "IRC — official 2026 reminder on SWT reporting and dates",
        "https://www.linkedin.com/posts/internal-revenue-commission-png_friendly-reminder-salary-wages-tax-swt-activity-7414493331319250944-Essw",
        "Publisher named in linked post"
      ],
      [
        "PwC PNG — March 2026 compliance update (S2, dates, nil returns)",
        "https://www.pwc.com/pg/en/newsletters/epb-newsletters/Private%20Newsletter%20-%20Issue%2014%20%28March%202026%29.pdf",
        "pwc.com"
      ],
      [
        "PwC PNG — September 2026 income-tax developments",
        "https://taxsummaries.pwc.com/papua-new-guinea/individual/significant-developments",
        "taxsummaries.pwc.com"
      ]
    ]
  },
  {
    "slug": "register-for-gst-irc-png",
    "title": "How to Register for GST with IRC in Papua New Guinea",
    "category": "Professional & business services",
    "summary": "Check whether your business must register for Goods and Services Tax (GST), prepare the evidence IRC needs, obtain registration under your TIN, and begin compliant invoicing and returns.\n\n## At a glance: fees and deadlines\n\nNormal GST rate: 10% on taxable sales, subject to zero-rated and exempt categories. Compulsory registration generally applies when annual taxable supplies exceed K250,000, measured across the relevant 12-month historical or expected period; voluntary registration may be available below the threshold. Most monthly Form G1 returns are due on the 21st of the following month or next working day; IRC also provides a quarterly G1 version for taxpayers on an approved quarterly schedule. A separate GST-registration application charge could not be verified; check directly with IRC.\n\n## Before you start\n\n- Business registration details and IPA certificate/extract where applicable.\n- Taxpayer Identification Number (TIN) and proof of registered business identity/contact details.\n- Records supporting actual taxable sales over the preceding 12 months and a forecast for the next 12 months.\n- Description of business operations and what products/services are taxable, zero-rated or exempt.\n- Owner/director identification and authorised contact details, plus current business address and bank details if requested.\n- Examples of sales invoices and purchases/expenses, and a bookkeeping system capable of recording GST.\n\n## Common mistakes to avoid\n\n- Using profit instead of turnover to test the threshold.\n- Charging 10% GST without an approved GST registration.\n- Treating exempt sales the same as zero-rated sales.\n- Claiming GST on all purchases without testing credit eligibility.\n- Using obsolete G1 forms or overlooking special temporary zero-rating on basic goods.\n\n> **Community guide:** Information checked on 8 October 2026. Fees, forms, and procedures can change. Confirm current requirements with the organisations linked below before paying or filing. This guide is not official advice.",
    "steps": [
      [
        "Calculate taxable turnover accurately",
        "Add taxable supplies (not business profit) over the relevant rolling 12 months; examine realistic expected sales for the next 12 months. IRC public guidance identifies K250,000 as the compulsory GST-registration threshold. Exempt supplies need separate treatment. If uncertain, ask IRC or a registered tax agent before deciding you are below threshold."
      ],
      [
        "Check whether voluntary registration makes sense",
        "If your taxable turnover is below K250,000, you may be eligible to register voluntarily if conducting a taxable activity. Registration creates return-filing and invoicing duties even when sales are small. Consider whether your customers need GST tax invoices and whether you will make significant creditable purchases."
      ],
      [
        "Make sure you have a business TIN",
        "If not registered with IRC, first obtain the appropriate TIN for the company or individual business. A company’s IPA incorporation alone does not automatically create its GST registration. Keep the IPA document, TIN confirmation and ownership/identification documents ready."
      ],
      [
        "Apply for GST registration with IRC",
        "Ask IRC to open/register the GST tax account under your existing TIN. Begin from https://irc.gov.pg/ (myIRC) or the nearest IRC Tax Centre, and request the current application process/form and submission channel. Provide business details, commencement date and proof of turnover as instructed. The exact 2026 registration interface and required form name could not be independently verified, so do not rely on an unconfirmed menu sequence."
      ],
      [
        "Wait for confirmation before charging GST",
        "Keep the registration approval and effective date. Do NOT add a GST line to invoices merely because the IPA business is registered or an application is pending. IRC warns that businesses charging GST without registration can face penalties."
      ],
      [
        "Configure invoices and accounting",
        "For standard-rated sales, GST is generally 10% of the GST-exclusive price (or 1/11 of a GST-inclusive amount). Separate taxable, zero-rated and exempt sales; record purchases and eligible input GST. Check current temporary zero-rating measures for designated essential household goods through 31 December 2026 rather than assuming all shop goods are charged 10%."
      ],
      [
        "Confirm your return frequency and file Form G1",
        "Ask IRC whether you are assigned monthly or approved quarterly GST reporting. For monthly filers, the G1 and payment ordinarily fall due by the 21st of the following month. Use the current approved G1 (the 2024-dated G1 2023 V1.2 for monthly returns in the 2026 compliance guidance; current quarterly version where applicable). Keep sales and purchase records."
      ],
      [
        "Pay or claim correctly and keep proof",
        "Reconcile output GST on taxable sales against eligible input credits. Lodge each required return by the due date, pay any net GST, and retain confirmation of submission and settlement. A refundable balance does not automatically mean an immediate cash refund; follow IRC procedures."
      ]
    ],
    "references": [
      [
        "IRC — official GST rate, registration threshold and filing reminder",
        "https://www.linkedin.com/posts/internal-revenue-commission-png_friendly-gst-reminder-to-all-taxpayers-activity-7407633536318365696-G24u",
        "Publisher named in linked post"
      ],
      [
        "IRC — myIRC portal",
        "https://irc.gov.pg/",
        "PNG Internal Revenue Commission"
      ],
      [
        "IRC — G1 return and notes (published 2024 version)",
        "https://static.irc.gov.pg/2023/October/P0Jjks-media-g1_2023.pdf",
        "PNG Internal Revenue Commission"
      ],
      [
        "PwC PNG — March 2026 note on correct monthly/quarterly G1 forms",
        "https://www.pwc.com/pg/en/newsletters/epb-newsletters/Private%20Newsletter%20-%20Issue%2014%20%28March%202026%29.pdf",
        "pwc.com"
      ],
      [
        "PNG Treasury — 2026 Budget, basic-goods zero-rating",
        "https://www.treasury.gov.pg/wp-content/uploads/2025/11/eVolume-1-2026-.pdf",
        "treasury.gov.pg"
      ]
    ]
  },
  {
    "slug": "open-business-bank-account-png",
    "title": "How to Open a Business Bank Account in PNG (BSP, Kina and Westpac)",
    "category": "Financial services",
    "summary": "Prepare the right company or sole-trader paperwork, compare BSP, Kina Bank and Westpac, and submit an application without unnecessary trips to the bank.\n\n## At a glance: fees and deadlines\n\nPublished examples: Kina Business Account has no monthly maintenance fee; its Aug 2025 schedule lists a K10 minimum-monthly-balance fee when below K500 and allows a nil opening deposit at branch subject to a three-day funding condition. Westpac Business Transaction Account lists K100 opening deposit and K10 monthly maintenance in its published fee guide. BSP offers several different business accounts with different terms; verify the exact selected product and fee schedule with BSP. Fees and eligibility can change.\n\n## Before you start\n\n- IPA company certificate or registered business-name certificate/extract (as applicable).\n- Business TIN; IRC Certificate of Compliance if required by the chosen bank and account type.\n- Current primary IDs for directors, account signatories and other relevant owners; Kina lists two accepted primary IDs.\n- Registered office/business address and evidence such as utility bill, rental agreement or bank statement.\n- Business activity, source-of-funds information, ownership/shareholding details and incorporation date/number.\n- Company resolution/mandate appointing authorised signatories if the bank requires it.\n- Initial funds for the opening deposit where applicable and the bank’s completed entity/associated-person forms.\n\n## Common mistakes to avoid\n\n- Arriving with only the IPA certificate and no TIN or director/signatory ID.\n- Assuming a no-monthly-fee product is free of other charges.\n- Using another person’s private bank account to hold company sales.\n- Not checking the identification requirements for each director, major shareholder and signatory.\n- Picking a savings/deposit product when the business needs daily payments and EFTPOS.\n\n> **Community guide:** Information checked on 8 October 2026. Fees, forms, and procedures can change. Confirm current requirements with the organisations linked below before paying or filing. This guide is not official advice.",
    "steps": [
      [
        "Choose the account for how you actually trade",
        "Compare how often you will deposit cash, make transfers, pay suppliers online, receive EFTPOS payments or use cheques. A personal savings account should not be used as a substitute for the business account where entity separation or banking rules require otherwise."
      ],
      [
        "Compare BSP, Kina and Westpac before visiting",
        "BSP: SME Business Current Account and other business products; the SME current account has a monthly fee and BSP provides an account fee schedule. Kina: Kina Business Account accepts eligible sole traders, partnerships and companies; no monthly maintenance fee but low-minimum-balance, dormancy and transaction charges may apply. Westpac: Business Transaction Account; published K100 minimum opening deposit, K10 monthly maintenance and five fee-free deposits per month."
      ],
      [
        "Confirm your business registration and tax documents",
        "For a company, bring the certificate of incorporation and details of registration and ownership; for a sole trader, take business-name registration if relevant. Banks may ask for a TIN, Certificate of Compliance, business licence (if any), source-of-funds and nature-of-business evidence."
      ],
      [
        "Gather IDs for everyone the bank needs to verify",
        "Kina asks for two valid forms of primary ID and accepts options such as passport, driver’s licence, NID, superannuation membership card or qualifying employment ID with confirmation letter. Westpac says directors, secretary, shareholders with 20% or more, and authorised signatories require identification and associated-party documentation. BSP outlines primary ID, address and income/source details for new customers, but company-specific documents should be checked with the branch."
      ],
      [
        "Prepare your signatory mandate and bank forms",
        "Decide who may open, operate and approve transactions and whether signing is singly or jointly authorised. Ask the bank for its current entity application and beneficial-owner or associated-party forms. Company-owned accounts may require director resolution/mandate and supporting corporate records."
      ],
      [
        "Submit at a branch and satisfy opening requirements",
        "BSP and Kina publish branch-based business account opening instructions; Westpac asks for signed company and associated-party forms and identification. Present originals for verification and copies if required. Deposit the applicable initial amount and ask when the account becomes operational."
      ],
      [
        "Set up secure payments and keep the documentation",
        "Activate the bank’s approved online/mobile banking, request business debit card/EFTPOS options if suitable, set account signatory permissions, and preserve the account confirmation. Keep credentials private and regularly reconcile the bank statement to business records."
      ],
      [
        "Review your charges after opening",
        "Check monthly maintenance, minimum-balance, cash-handling, transfer, card, cheque and dormant-account fees against actual use. For example, a no-monthly-maintenance product may still charge a low-balance or counter withdrawal fee."
      ]
    ],
    "references": [
      [
        "BSP — SME Business Current Account",
        "https://www.bsp.com.pg/business-banking/business-accounts-cards/sme-business-current-account/",
        "BSP Financial Group"
      ],
      [
        "BSP — business account options",
        "https://www.bsp.com.pg/business-banking/business-accounts-cards/",
        "BSP Financial Group"
      ],
      [
        "Kina Bank — Kina Business Account, ID requirements",
        "https://www.kinabank.com.pg/business-banking/kina-business-account/",
        "Kina Bank"
      ],
      [
        "Kina Bank — Aug 2025 published fees",
        "https://www.kinabank.com.pg/wp-content/uploads/2025/10/2504070_KB_Fees-and-Charges-Document-August-2025.pdf",
        "Kina Bank"
      ],
      [
        "Westpac PNG — Business Transaction Account and ID requirements",
        "https://www.westpac.com.pg/business/business-bank-accounts/business-cheque-account/",
        "westpac.com.pg"
      ],
      [
        "Westpac PNG — PNG fees and charges",
        "https://www.westpac.com.pg/content/dam/public/png/documents/png_customer_service_fees_and_charges.pdf",
        "westpac.com.pg"
      ]
    ]
  }
]


def add_batch1_guides(apps, schema_editor):
    alias = schema_editor.connection.alias
    Guide = apps.get_model("guides", "Guide")
    GuideVersion = apps.get_model("guides", "GuideVersion")
    GuideReference = apps.get_model("guides", "GuideReference")
    Step = apps.get_model("guides", "Step")
    BusinessCategory = apps.get_model("categories", "BusinessCategory")

    for item in GUIDES:
        # Never replace a community-created guide with the same slug.
        if Guide.objects.using(alias).filter(slug=item["slug"]).exists():
            continue
        category = BusinessCategory.objects.using(alias).filter(name=item["category"]).first()
        guide = Guide.objects.using(alias).create(
            title=item["title"], slug=item["slug"], summary=item["summary"],
            category_id=category.id if category else None,
            created_by_id=None, created_via="mcp", ai_assisted=True,
            ai_provider="OpenAI", ai_model="GPT-6",
            ai_source_note="Official PNG and bank sources checked 8 October 2026; confirm live fees and forms.",
        )
        version = GuideVersion.objects.using(alias).create(
            guide_id=guide.id, edited_by_id=None, status="published",
            edit_summary="Initial PNG guide with sources and review caveats",
            created_via="mcp", ai_assisted=True,
            ai_provider="OpenAI", ai_model="GPT-6",
            ai_source_note="Official PNG and bank sources checked 8 October 2026; confirm live fees and forms.",
        )
        for position, (title, instruction) in enumerate(item["steps"], start=1):
            Step.objects.using(alias).create(
                version_id=version.id, position=float(position),
                title=title, instruction=instruction,
            )
        for title, url, publisher in item["references"]:
            GuideReference.objects.using(alias).create(
                version_id=version.id, title=title, url=url,
                publisher=publisher, accessed_at=date(2026, 10, 8),
            )
        # This is the newly created guide, not an existing user's record.
        guide.current_version_id = version.id
        guide.save(using=alias, update_fields=["current_version"])


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("guides", "0014_add_png_practical_guides_batch_2")]
    operations = [migrations.RunPython(add_batch1_guides, migrations.RunPython.noop)]
