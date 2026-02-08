"""Example activities for LLM few-shot prompting. Derived from seed_activity_templates ideas."""

# Structure matches what the LLM must return: title, description, recommendation_rationale,
# estimated_minutes, recommended_location, recommended_invitee_name.
# "Partner" in recommended_invitee_name is a placeholder: the service substitutes it with
# the first relationship member's actual name when building the LLM prompt; the route uses
# the first member as recommended_invitee when mapping the seed fallback.
SEED_EXAMPLE_ACTIVITIES = [
    {
        "title": "The $5 Art Challenge",
        "description": "Give everyone the same tiny budget at a dollar store (or a pile of random craft supplies). Create an artwork or invention in 20 minutes, then present it like an infomercial. Finish with award certificates and a group photo with creations.",
        "recommendation_rationale": "Constraints boost creativity and the presentation element makes it memorable and confidence-building.",
        "estimated_minutes": 80,
        "recommended_location": "home",
        "recommended_invitee_name": "Family",
        "vibe_tags": ["creative", "arts-and-crafts", "silly", "keepsake"]
    },
    {
        "title": "Recreate first date",
        "description": "Agree on which first date to recreate. Match the vibe: same type of place, similar food, or same activity. Share one thing you each remember most from that day.",
        "recommendation_rationale": "Great for quality time and reconnecting.",
        "estimated_minutes": 60,
        "recommended_location": "cafe or favorite restaurant",
        "recommended_invitee_name": "Partner",
        "vibe_tags": ["nostalgic", "intimate"],
    },
    {
        "title": "Invent-a-Board-Game Night",
        "description": "Using paper, markers, coins, and dice, invent a board game in 20 minutes. Rules: include one wild-card space and one teamwork mechanic. Playtest once, then revise the rules like real designers.",
        "recommendation_rationale": "Builds collaboration and creativity, and you end up with a repeatable game.",
        "estimated_minutes": 90,
        "recommended_location": "dining table",
        "recommended_invitee_name": "Family",
        "vibe_tags": ["creative", "teamwork", "puzzle", "keepsake"]
    },
    {
        "title": "Blanket fort night",
        "description": "Build a blanket fort together. Bring pillows, string lights or a lamp, and snacks. Watch a movie, read aloud, or play a simple card game inside. No phones in the fort.",
        "recommendation_rationale": "Cozy way to connect and unwind together.",
        "estimated_minutes": 60,
        "recommended_location": "living room",
        "recommended_invitee_name": "Partner",
        "vibe_tags": ["silly", "calm", "family"],
    },
    {
        "title": "Compliment Scavenger Hunt",
        "description": "Write 12 specific compliments on sticky notes (must include evidence like \"when you…\"). Hide them around the home. The final note includes one small request for next week (e.g., \"device-free dinner\"). Read them aloud together.",
        "recommendation_rationale": "Builds connection through appreciation while sneaking in gentle, actionable relationship improvements.",
        "estimated_minutes": 40,
        "recommended_location": "home",
        "recommended_invitee_name": "Partner",
        "vibe_tags": ["sweet", "affirming", "cozy", "bonding"]
    },
    {
        "title": "Foreign Film Dubbing Challenge",
        "description": "Put on a random foreign-language clip with the sound off and dub the dialogue live with dramatic voices. Switch genres halfway (rom-com → thriller). Record a 30-second highlight reel as your \"trailer.\"",
        "recommendation_rationale": "Instant laughs, low effort, and it breaks the ice even if you’re tired or not feeling talkative.",
        "estimated_minutes": 60,
        "recommended_location": "living room",
        "recommended_invitee_name": "Partner",
        "vibe_tags": ["silly", "low-effort", "creative", "indoors"]
    },
]
