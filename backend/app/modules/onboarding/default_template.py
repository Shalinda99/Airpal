"""Global default questionnaire. Super Admin can clone it into country/region templates with different defaults."""

T, Y, N, S, M, TM, L = "text", "yesno", "number", "select", "multiselect", "time", "link"


def q(key, label, type_=T, required=False, help_=None, examples=None, options=None, default=None, journey=None):
    return {"key": key, "label": label, "type": type_, "required": required, "help_text": help_,
            "examples": examples, "options": options, "default_value": default, "journey": journey}


def j(flow, scope, order, title, role="text"):
    return {"flow": flow, "scope": scope, "order": order, "title": title, "role": role}


LANGS = ["en", "si", "ta", "hi", "ar", "fr", "de", "es", "zh", "ja"]

DEFAULT_TEMPLATE = {
    "name": "Airpal Global Default",
    "sections": [
        {"key": "general", "title": "General", "questions": [
            q("terminals", "List your terminals and what each is used for", T, True,
              "One line per terminal.", ["Terminal 1: all international flights"]),
            q("opening_hours", "Airport opening hours", T, True, examples=["Open 24 hours"], default="Open 24 hours"),
            q("languages", "Languages available to passengers", M, True, options=LANGS, default=["en"]),
            q("website", "Official airport website", L, False, examples=["https://www.example-airport.com"]),
            q("general_contact", "General information contact", T, False),
        ]},
        {"key": "departure", "title": "Departure process", "questions": [
            q("checkin_hours", "When does check-in open and close for flights?", T, True,
              "Typical windows relative to departure.", ["Opens 3 hours before departure, closes 60 minutes before"],
              journey=j("departure", "both", 1, "Check-in")),
            q("bag_drop_cutoff", "Bag drop cut-off (minutes before departure)", N, True, examples=[60],
              journey=j("departure", "both", 1, "Check-in", "tip")),
            q("queue_checkin_minutes", "Typical check-in queue time (minutes)", N, False,
              journey=j("departure", "both", 1, "Check-in", "minutes")),
            q("security_rules", "Describe security screening rules", T, True, journey=j("departure", "both", 3, "Security")),
            q("liquids_rule", "Liquids rule for hand luggage", T, True, "State the exact published rule.",
              ["Containers up to 100ml in a 1 litre clear bag"], journey=j("departure", "both", 3, "Security")),
            q("electronics_rule", "Laptops and electronics at security", T, False, journey=j("departure", "both", 3, "Security")),
            q("prohibited_items", "Prohibited items (one per line)", T, False,
              journey=j("departure", "both", 3, "Security", "prohibited")),
            q("queue_security_minutes", "Typical security queue time (minutes)", N, False,
              journey=j("departure", "both", 3, "Security", "minutes")),
            q("emigration_process", "Departure passport control / emigration process", T, False,
              journey=j("departure", "international", 4, "Passport control")),
            q("boarding_close_minutes", "Gate closes (minutes before departure)", N, True, examples=[15],
              journey=j("departure", "both", 6, "Gate and boarding", "tip")),
            q("departure_documents", "Documents needed at departure (one per line)", T, False,
              journey=j("departure", "international", 1, "Check-in", "documents")),
        ]},
        {"key": "arrival", "title": "Arrival process", "questions": [
            q("immigration_process", "Immigration process for arriving passengers", T, True,
              journey=j("arrival", "international", 1, "Immigration")),
            q("egates", "Are e-gates available?", Y, False, journey=j("arrival", "international", 1, "Immigration")),
            q("visa_on_arrival", "Visa on arrival information", T, False, "Link or short summary.",
              journey=j("arrival", "international", 1, "Immigration")),
            q("immigration_minutes", "Typical immigration time (minutes)", N, False,
              journey=j("arrival", "international", 1, "Immigration", "minutes")),
            q("baggage_claim", "Baggage claim information", T, True, journey=j("arrival", "both", 2, "Baggage claim")),
            q("baggage_minutes", "Typical wait for baggage (minutes)", N, False,
              journey=j("arrival", "both", 2, "Baggage claim", "minutes")),
            q("lost_baggage", "What should passengers do if baggage is lost or delayed?", T, True,
              journey=j("arrival", "both", 2, "Baggage claim", "tip")),
            q("customs_rules", "Customs rules and declarations", T, True, journey=j("arrival", "international", 3, "Customs")),
            q("arrival_exit", "Arrivals hall and exit information", T, False, journey=j("arrival", "both", 4, "Exit")),
        ]},
        {"key": "transit", "title": "Transit and transfers", "questions": [
            q("transit_rules", "Transit / transfer rules", T, True, journey=j("transit", "both", 1, "Transfer")),
            q("min_connection_minutes", "Minimum connection time (minutes)", N, False,
              journey=j("transit", "both", 1, "Transfer", "minutes")),
            q("transit_visa", "Transit visa requirements", T, False, journey=j("transit", "both", 1, "Transfer")),
            q("transit_security", "Is there a second security check for transfers?", Y, False,
              journey=j("transit", "both", 2, "Transfer security")),
        ]},
        {"key": "facilities", "title": "Facilities", "questions": [
            q("lounges", "Lounges", T), q("prayer_rooms", "Prayer rooms", T), q("pharmacy", "Pharmacy", T),
            q("sim_currency", "SIM cards and currency exchange", T), q("charging", "Charging points", T),
            q("wifi", "Wi-Fi information", T, True), q("accessibility", "Accessibility services", T, True),
            q("family_rooms", "Family and baby rooms", T), q("smoking", "Smoking areas", T),
        ]},
        {"key": "gates", "title": "Gates and walking times", "questions": [
            q("gate_walking_times", "Typical walking time from security to gates (one line per gate zone: 'A1-A10: 8')", T, True,
              "Used by the agent and ticket countdown.", ["A1-A10: 8", "B1-B12: 12"]),
        ]},
        {"key": "ground_transport", "title": "Ground transport and ride pickup", "questions": [
            q("ground_overview", "Ground transport overview (taxi, bus, rail, ride-hailing)", T, True),
            q("taxi_info", "Official taxi desk information", T),
            q("public_transport", "Public transport (metro, bus) information", T),
            q("rideshare_notes", "Ride-hailing pickup notes", T, False, examples=["Rideshare pickup is at Car Park B, level 1"]),
        ]},
        {"key": "support", "title": "Customer care", "questions": [
            q("support_notes", "Additional customer care notes", T),
        ]},
        {"key": "emergency", "title": "Emergency contacts", "questions": [
            q("emergency_number", "Airport emergency number", T, True), q("medical_info", "Medical assistance", T),
            q("police_info", "Police / security contact", T),
        ]},
    ],
}

# Sections that additionally require structured data (not questions) before go-live.
STRUCTURAL_REQUIREMENTS = {
    "ground_transport": "pickup_points",
    "support": "support_channels",
}
