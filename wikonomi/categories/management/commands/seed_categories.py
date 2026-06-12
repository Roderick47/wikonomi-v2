from django.core.management.base import BaseCommand
from categories.models import Category, Subcategory, BusinessCategory, BusinessSubcategory


CONSUMER_CATEGORIES = [
  {"name":"Groceries & household","slug":"groceries-household","icon":"ti-basket","order":1,"subcategories":[
    {"name":"Fresh produce","slug":"fresh-produce","examples":"Fruit, vegetables, garden food, eggs, fresh meat, seafood","is_png_specific":False},
    {"name":"Buai & smokables","slug":"buai-smokables","examples":"Betelnut, mustard, lime, daka, tobacco","is_png_specific":True},
    {"name":"Pantry & staples","slug":"pantry-staples","examples":"Rice, flour, sugar, cooking oil, tinfish, noodles, sauces","is_png_specific":False},
    {"name":"Snacks & confectionery","slug":"snacks-confectionery","examples":"Mr Potato, biscuits, chocolates, sweets, popcorn","is_png_specific":False},
    {"name":"Beverages","slug":"beverages","examples":"Water, soft drinks, juice, coffee, tea, milk, energy drinks","is_png_specific":False},
    {"name":"Bakery & takeaway","slug":"bakery-takeaway","examples":"Bread, pies, cakes, kai bar meals, BBQ, PMV-side food","is_png_specific":True},
    {"name":"Household & cleaning","slug":"household-cleaning","examples":"Laundry powder, dish soap, garbage bags, tissues, insect spray","is_png_specific":False},
    {"name":"Baby & kids","slug":"baby-kids","examples":"Diapers, baby wipes, formula, baby food, baby accessories","is_png_specific":False},
  ]},
  {"name":"Electronics & appliances","slug":"electronics-appliances","icon":"ti-device-mobile","order":2,"subcategories":[
    {"name":"Phones & tablets","slug":"phones-tablets","examples":"Smartphones, feature phones, tablets, smartwatches","is_png_specific":False},
    {"name":"Airtime & data","slug":"airtime-data","examples":"Digicel/Telikom credit, data bundles, SIM cards","is_png_specific":True},
    {"name":"Computers & accessories","slug":"computers-accessories","examples":"Laptops, printers, keyboards, mice, USBs, hard drives","is_png_specific":False},
    {"name":"Audio & entertainment","slug":"audio-entertainment","examples":"Headphones, bluetooth speakers, TVs, gaming consoles","is_png_specific":False},
    {"name":"Home appliances","slug":"home-appliances","examples":"Fridges, microwaves, blenders, kettles, washing machines, fans","is_png_specific":False},
    {"name":"Cameras & drones","slug":"cameras-drones","examples":"Action cameras, DSLRs, DJI drones, gimbals, GoPros","is_png_specific":False},
    {"name":"Solar & power backup","slug":"solar-power-backup","examples":"Solar panels, batteries, inverters, power banks, UPS","is_png_specific":True},
  ]},
  {"name":"Hardware, building & tools","slug":"hardware-building-tools","icon":"ti-building","order":3,"subcategories":[
    {"name":"Structural materials","slug":"structural-materials","examples":"Cement, timber, roofing iron, bricks, sand, gravel","is_png_specific":False},
    {"name":"Plumbing & water","slug":"plumbing-water","examples":"Pipes, fittings, taps, tanks, water pumps, guttering","is_png_specific":True},
    {"name":"Electrical & lighting","slug":"electrical-lighting","examples":"Wiring, switches, lightbulbs, extension cords, circuit breakers","is_png_specific":False},
    {"name":"Hand & power tools","slug":"hand-power-tools","examples":"Drills, circular saws, grinders, hammers, pliers, wrenches","is_png_specific":False},
    {"name":"Paint & finishing","slug":"paint-finishing","examples":"Interior/exterior paint, varnish, tiles, putty, sandpaper","is_png_specific":False},
    {"name":"Garden & outdoor","slug":"garden-outdoor","examples":"Lawn mowers, hoses, wheelbarrows, sprayers, outdoor stoves","is_png_specific":False},
  ]},
  {"name":"Health, beauty & personal care","slug":"health-beauty-personal-care","icon":"ti-heart-rate-monitor","order":4,"subcategories":[
    {"name":"Personal hygiene","slug":"personal-hygiene","examples":"Soap, shampoo, toothpaste, deodorant, shaving needs","is_png_specific":False},
    {"name":"Cosmetics & skincare","slug":"cosmetics-skincare","examples":"Makeup, lotions, perfumes, hair styling products","is_png_specific":False},
    {"name":"Medicines & wellness","slug":"medicines-wellness","examples":"OTC vitamins, pain relief, antimalarials, first aid, prescriptions","is_png_specific":False},
    {"name":"Traditional medicine","slug":"traditional-medicine","examples":"Herbal remedies, bush medicine, traditional healer fees","is_png_specific":True},
    {"name":"Hair & beauty services","slug":"hair-beauty-services","examples":"Haircuts, braiding, nail care, waxing, barbershop rates","is_png_specific":False},
  ]},
  {"name":"Clothing, footwear & accessories","slug":"clothing-footwear-accessories","icon":"ti-shirt","order":5,"subcategories":[
    {"name":"Men's clothing","slug":"mens-clothing","examples":"Shirts, trousers, shorts, uniforms, traditional dress","is_png_specific":False},
    {"name":"Women's clothing","slug":"womens-clothing","examples":"Dresses, blouses, meri blouses, skirts, laplap","is_png_specific":True},
    {"name":"Children's clothing","slug":"childrens-clothing","examples":"School uniforms, kids' casual wear, infant clothing","is_png_specific":False},
    {"name":"Second-hand clothing","slug":"second-hand-clothing","examples":"Market laplap, imported bundles, used shoes","is_png_specific":True},
    {"name":"Footwear","slug":"footwear","examples":"Sandals, sports shoes, boots, formal shoes, thongs","is_png_specific":False},
    {"name":"Accessories","slug":"accessories","examples":"Bags, backpacks, sunglasses, jewellery, belts, hats","is_png_specific":False},
  ]},
  {"name":"Automotive & transport","slug":"automotive-transport","icon":"ti-car","order":6,"subcategories":[
    {"name":"Vehicles for sale","slug":"vehicles-for-sale","examples":"Cars, motorbikes, trucks, PMVs, boats for sale","is_png_specific":False},
    {"name":"Spare parts & accessories","slug":"spare-parts-accessories","examples":"Tyres, batteries, engine oil, filters, car mats, wipers","is_png_specific":False},
    {"name":"Fuel & gas","slug":"fuel-gas","examples":"Petrol, diesel, LPG cylinders, kerosene, aviation fuel","is_png_specific":False},
    {"name":"PMV & public transport fares","slug":"pmv-public-transport-fares","examples":"Town PMV, route bus, hire car, taxi rates","is_png_specific":True},
    {"name":"Domestic flights","slug":"domestic-flights","examples":"Air Niugini, PNG Air fares, charter flight rates","is_png_specific":True},
    {"name":"Boats & marine transport","slug":"boats-marine-transport","examples":"Dinghy hire, outboard motors, passenger boat fares","is_png_specific":True},
  ]},
  {"name":"Services & utilities","slug":"services-utilities","icon":"ti-briefcase","order":7,"subcategories":[
    {"name":"Utilities","slug":"utilities","examples":"PNG Power (Easipay), Water PNG bills, internet packages","is_png_specific":True},
    {"name":"Mobile & internet plans","slug":"mobile-internet-plans","examples":"Digicel/Telikom broadband, Starlink, hotspot rental","is_png_specific":False},
    {"name":"Professional services","slug":"professional-services","examples":"Legal fees, accounting, business consulting, surveying","is_png_specific":False},
    {"name":"Government & admin fees","slug":"government-admin-fees","examples":"IPA registration, IRC, land titles, permits, birth certificates","is_png_specific":True},
    {"name":"Financial services","slug":"financial-services","examples":"Bank fees, mobile money (MiCash), loans, insurance premiums","is_png_specific":False},
    {"name":"Health services","slug":"health-services","examples":"Clinic/hospital fees, dental, lab tests, pharmacy consultations","is_png_specific":False},
    {"name":"Printing & media","slug":"printing-media","examples":"Printing, photocopying, signage, radio/newspaper advertising","is_png_specific":False},
    {"name":"Security services","slug":"security-services","examples":"Guard hire, alarm systems, cash-in-transit rates","is_png_specific":False},
  ]},
  {"name":"Education & training","slug":"education-training","icon":"ti-school","order":8,"subcategories":[
    {"name":"School fees","slug":"school-fees","examples":"Primary, secondary, boarding, bus fees, stationery levies","is_png_specific":True},
    {"name":"TVET & vocational","slug":"tvet-vocational","examples":"NiHT, Don Bosco, TVET colleges, trade certificates","is_png_specific":True},
    {"name":"University & tertiary","slug":"university-tertiary","examples":"UPNG, Unitech, DWU, Pacific Adventist tuition","is_png_specific":True},
    {"name":"Tutoring & coaching","slug":"tutoring-coaching","examples":"Private tutoring, exam prep, remedial classes","is_png_specific":False},
    {"name":"Stationery & office supplies","slug":"stationery-office-supplies","examples":"Books, pens, paper, folders, ink, school bags","is_png_specific":False},
  ]},
  {"name":"Food businesses & catering","slug":"food-businesses-catering","icon":"ti-chef-hat","order":9,"subcategories":[
    {"name":"Restaurant & café meals","slug":"restaurant-cafe-meals","examples":"Town restaurants, hotel dining, café prices","is_png_specific":False},
    {"name":"Market & canteen food","slug":"market-canteen-food","examples":"Market stall prices, office canteens, tuck shops","is_png_specific":True},
    {"name":"Catering services","slug":"catering-services","examples":"Event catering, buffet packages, corporate catering","is_png_specific":False},
    {"name":"Takeaway & fast food","slug":"takeaway-fast-food","examples":"Jollibee, KFC, Pizza Hut, local takeaways","is_png_specific":False},
  ]},
  {"name":"Property & accommodation","slug":"property-accommodation","icon":"ti-map-pin","order":10,"subcategories":[
    {"name":"Residential rentals","slug":"residential-rentals","examples":"House, flat, compound housing monthly rents","is_png_specific":True},
    {"name":"Commercial rentals","slug":"commercial-rentals","examples":"Shop, office, warehouse, market stall lease rates","is_png_specific":False},
    {"name":"Land transactions","slug":"land-transactions","examples":"State lease, customary land sales, clan land deals","is_png_specific":True},
    {"name":"Hotels & guesthouses","slug":"hotels-guesthouses","examples":"Nightly rates, weekly rates, conference packages","is_png_specific":False},
    {"name":"Short-stay & Airbnb","slug":"short-stay-airbnb","examples":"Short-term furnished accommodation rates","is_png_specific":False},
  ]},
  {"name":"Agriculture & fishing","slug":"agriculture-fishing","icon":"ti-plant","order":11,"subcategories":[
    {"name":"Farm inputs","slug":"farm-inputs","examples":"Seeds, fertiliser, pesticides, farming tools, sprayers","is_png_specific":False},
    {"name":"Livestock & poultry","slug":"livestock-poultry","examples":"Live pigs, chickens, cattle, goats, feed, vaccines","is_png_specific":False},
    {"name":"Cash crop prices","slug":"cash-crop-prices","examples":"Copra, cocoa, coffee, vanilla, betelnut wholesale prices","is_png_specific":True},
    {"name":"Fish & seafood","slug":"fish-seafood","examples":"Fresh fish, crayfish, crab, prawn market prices","is_png_specific":True},
    {"name":"Fishing gear & boats","slug":"fishing-gear-boats","examples":"Nets, hooks, outboard motors, dinghy fuel, ice","is_png_specific":True},
    {"name":"Agro-processing","slug":"agro-processing","examples":"Milling, copra drying, coffee hulling, vanilla curing fees","is_png_specific":True},
  ]},
  {"name":"Freight, shipping & logistics","slug":"freight-shipping-logistics","icon":"ti-package","order":12,"subcategories":[
    {"name":"Domestic cargo","slug":"domestic-cargo","examples":"PMV cargo rates, coastal shipping, air cargo to provinces","is_png_specific":True},
    {"name":"International shipping","slug":"international-shipping","examples":"Sea freight, air freight, import/export charges","is_png_specific":False},
    {"name":"Courier & delivery","slug":"courier-delivery","examples":"DHL, EMS, local WhatsApp delivery services","is_png_specific":False},
    {"name":"Customs & quarantine","slug":"customs-quarantine","examples":"IRC import duties, NAQIA fees, quarantine charges","is_png_specific":True},
  ]},
  {"name":"Events & entertainment","slug":"events-entertainment","icon":"ti-confetti","order":13,"subcategories":[
    {"name":"Venue & hall hire","slug":"venue-hall-hire","examples":"Community halls, function centres, church venues","is_png_specific":False},
    {"name":"Entertainment hire","slug":"entertainment-hire","examples":"DJ, PA system, live bands, photo/video packages","is_png_specific":False},
    {"name":"Tourism & tours","slug":"tourism-tours","examples":"Tour operators, diving, trekking, cultural packages","is_png_specific":False},
    {"name":"Cultural & church events","slug":"cultural-church-events","examples":"Sing-sing hire, kastom fees, church function costs","is_png_specific":True},
  ]},
]

BUSINESS_CATEGORIES = [
  {"name":"Retail & trade stores","slug":"retail-trade-stores","icon":"ti-shopping-cart","order":1,"subcategories":[
    {"name":"Supermarket / grocery store","slug":"supermarket-grocery"},{"name":"Trade store / general store","slug":"trade-store-general"},{"name":"Hardware & building supply","slug":"hardware-building-supply"},{"name":"Pharmacy / chemist","slug":"pharmacy-chemist"},{"name":"Electronics & tech retail","slug":"electronics-tech-retail"},{"name":"Clothing & footwear retail","slug":"clothing-footwear-retail"},{"name":"Automotive parts & accessories","slug":"automotive-parts-accessories"},{"name":"Market stall / roadside vendor","slug":"market-stall-roadside"},]},
  {"name":"Food & beverage","slug":"food-beverage","icon":"ti-chef-hat","order":2,"subcategories":[
    {"name":"Restaurant / dine-in","slug":"restaurant-dine-in"},{"name":"Café / coffee shop","slug":"cafe-coffee-shop"},{"name":"Takeaway / fast food","slug":"takeaway-fast-food"},{"name":"Canteen / tuck shop","slug":"canteen-tuck-shop"},{"name":"Catering business","slug":"catering-business"},{"name":"Bakery","slug":"bakery"},{"name":"Market food vendor","slug":"market-food-vendor"},{"name":"Bar / nightclub","slug":"bar-nightclub"},]},
  {"name":"Professional & business services","slug":"professional-business-services","icon":"ti-briefcase","order":3,"subcategories":[
    {"name":"Legal firm / lawyer","slug":"legal-firm"},{"name":"Accounting / bookkeeping","slug":"accounting-bookkeeping"},{"name":"Business consulting","slug":"business-consulting"},{"name":"Real estate agency","slug":"real-estate-agency"},{"name":"Recruitment / HR services","slug":"recruitment-hr"},{"name":"Insurance broker / provider","slug":"insurance-provider"},{"name":"Marketing / advertising agency","slug":"marketing-advertising"},{"name":"Engineering / surveying","slug":"engineering-surveying"},]},
  {"name":"Financial services","slug":"financial-services-biz","icon":"ti-credit-card","order":4,"subcategories":[
    {"name":"Commercial bank","slug":"commercial-bank"},{"name":"Microfinance institution","slug":"microfinance-institution"},{"name":"Mobile money / fintech","slug":"mobile-money-fintech"},{"name":"Foreign exchange / remittance","slug":"forex-remittance"},{"name":"Superannuation fund","slug":"superannuation-fund"},{"name":"Insurance company","slug":"insurance-company"},]},
  {"name":"Health & medical","slug":"health-medical","icon":"ti-stethoscope","order":5,"subcategories":[
    {"name":"Hospital / clinic","slug":"hospital-clinic"},{"name":"Pharmacy","slug":"pharmacy"},{"name":"Dental practice","slug":"dental-practice"},{"name":"Optical / eyecare","slug":"optical-eyecare"},{"name":"Laboratory / diagnostics","slug":"laboratory-diagnostics"},{"name":"Allied health (physio, counselling, etc.)","slug":"allied-health"},]},
  {"name":"Education & training","slug":"education-training-biz","icon":"ti-school","order":6,"subcategories":[
    {"name":"Primary / secondary school","slug":"primary-secondary-school"},{"name":"TVET / vocational institution","slug":"tvet-vocational-institution"},{"name":"University / tertiary institution","slug":"university-tertiary"},{"name":"Private tutor / coaching centre","slug":"private-tutor-coaching"},{"name":"Driving school","slug":"driving-school"},{"name":"Training provider / corporate training","slug":"training-provider"},]},
  {"name":"Construction & trades","slug":"construction-trades","icon":"ti-hammer","order":7,"subcategories":[
    {"name":"General contractor / builder","slug":"general-contractor"},{"name":"Electrical contractor","slug":"electrical-contractor"},{"name":"Plumbing contractor","slug":"plumbing-contractor"},{"name":"Carpentry / joinery","slug":"carpentry-joinery"},{"name":"Welding / steel fabrication","slug":"welding-steel"},{"name":"Painting & decorating","slug":"painting-decorating"},{"name":"Civil engineering / earthworks","slug":"civil-engineering-earthworks"},]},
  {"name":"Transport & logistics","slug":"transport-logistics","icon":"ti-truck","order":8,"subcategories":[
    {"name":"PMV operator","slug":"pmv-operator"},{"name":"Taxi / hire car service","slug":"taxi-hire-car"},{"name":"Freight & cargo company","slug":"freight-cargo"},{"name":"Courier / delivery service","slug":"courier-delivery"},{"name":"Shipping agent","slug":"shipping-agent"},{"name":"Aviation / charter flights","slug":"aviation-charter"},{"name":"Vehicle rental","slug":"vehicle-rental"},]},
  {"name":"ICT & media","slug":"ict-media","icon":"ti-server","order":9,"subcategories":[
    {"name":"Software / web development","slug":"software-web-dev"},{"name":"IT support & managed services","slug":"it-support-managed"},{"name":"Telecommunications provider","slug":"telco-provider"},{"name":"Printing & signage","slug":"printing-signage"},{"name":"Media / advertising agency","slug":"media-advertising"},{"name":"CCTV / security technology","slug":"cctv-security-tech"},]},
  {"name":"Hospitality & tourism","slug":"hospitality-tourism","icon":"ti-bed","order":10,"subcategories":[
    {"name":"Hotel / resort","slug":"hotel-resort"},{"name":"Guesthouse / lodge","slug":"guesthouse-lodge"},{"name":"Tour operator","slug":"tour-operator"},{"name":"Event / conference venue","slug":"event-conference-venue"},{"name":"Travel agency","slug":"travel-agency"},]},
  {"name":"Agriculture, fishing & forestry","slug":"agriculture-fishing-forestry","icon":"ti-plant","order":11,"subcategories":[
    {"name":"Smallholder farmer","slug":"smallholder-farmer"},{"name":"Commercial farm / plantation","slug":"commercial-farm-plantation"},{"name":"Fishing / aquaculture","slug":"fishing-aquaculture"},{"name":"Agro-processing / milling","slug":"agro-processing-milling"},{"name":"Logging / timber company","slug":"logging-timber"},{"name":"Agricultural supply / input dealer","slug":"agricultural-supply"},{"name":"Export / commodity trader","slug":"export-commodity-trader"},]},
  {"name":"Mining & resources","slug":"mining-resources","icon":"ti-mountain","order":12,"subcategories":[
    {"name":"Mining company","slug":"mining-company"},{"name":"Oil & gas operator","slug":"oil-gas-operator"},{"name":"Mining services / contractor","slug":"mining-services-contractor"},{"name":"Equipment hire & supply","slug":"equipment-hire-supply"},{"name":"Industrial supply & chemicals","slug":"industrial-supply-chemicals"},]},
  {"name":"Security & facilities","slug":"security-facilities","icon":"ti-shield","order":13,"subcategories":[
    {"name":"Security / guard services","slug":"security-guard-services"},{"name":"Cleaning & janitorial","slug":"cleaning-janitorial"},{"name":"Waste management","slug":"waste-management"},{"name":"Pest control","slug":"pest-control"},{"name":"Facilities management","slug":"facilities-management"},]},
  {"name":"NGO, church & community","slug":"ngo-church-community","icon":"ti-heart","order":14,"subcategories":[
    {"name":"Non-governmental organisation (NGO)","slug":"ngo"},{"name":"Church / religious organisation","slug":"church-religious"},{"name":"Community group / association","slug":"community-group"},{"name":"Government agency / statutory body","slug":"government-agency"},{"name":"International development organisation","slug":"international-development"},]},
]


class Command(BaseCommand):
    help = "Seed consumer and business category data."

    def handle(self, *args, **options):
        consumer_count = 0
        consumer_sub_count = 0
        for category_data in CONSUMER_CATEGORIES:
            subcategories = category_data.pop('subcategories')
            category, _ = Category.objects.update_or_create(
                slug=category_data['slug'],
                defaults={**category_data, 'is_png_specific': category_data.get('is_png_specific', False)},
            )
            consumer_count += 1
            for order, subcategory_data in enumerate(subcategories, start=1):
                Subcategory.objects.update_or_create(
                    category=category,
                    slug=subcategory_data['slug'],
                    defaults={**subcategory_data, 'order': order},
                )
                consumer_sub_count += 1
            category_data['subcategories'] = subcategories

        business_count = 0
        business_sub_count = 0
        for category_data in BUSINESS_CATEGORIES:
            subcategories = category_data.pop('subcategories')
            category, _ = BusinessCategory.objects.update_or_create(
                slug=category_data['slug'],
                defaults=category_data,
            )
            business_count += 1
            for order, subcategory_data in enumerate(subcategories, start=1):
                BusinessSubcategory.objects.update_or_create(
                    category=category,
                    slug=subcategory_data['slug'],
                    defaults={**subcategory_data, 'order': order},
                )
                business_sub_count += 1
            category_data['subcategories'] = subcategories

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {consumer_count} consumer categories, {consumer_sub_count} consumer subcategories, "
            f"{business_count} business categories, and {business_sub_count} business subcategories."
        ))
