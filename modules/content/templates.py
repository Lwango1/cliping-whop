VIDEO_INTRO_TEMPLATES = [
    {
        "text": "WORLD CUP 2026",
        "overlay": "fire",
        "duration": 3,
        "style": "bold_center"
    },
    {
        "text": "BETWAY CANADA",
        "overlay": "betway_logo",
        "duration": 2,
        "style": "branded"
    },
]

VIDEO_OUTRO_TEMPLATES = [
    {
        "text": "Bet Canada, Bet Betway",
        "overlay": "betway_logo",
        "duration": 3,
        "style": "branded"
    },
    {
        "text": "Subscribe for more!",
        "duration": 2,
        "style": "simple_center"
    },
]

SOCIAL_CAPTIONS = {
    "tiktok": [
        "World Cup 2026 is here! Who's winning it all? ⚽ #WorldCup #Betway #Canada",
        "This moment was INSANE 🔥 Full coverage on Betway #WorldCup #Football",
        "CANADA at the World Cup - let's go! 🇨🇦⚽ #Betway #WorldCup2026",
    ],
    "youtube_shorts": [
        "World Cup 2026 - Best moments #shorts",
        "He did WHAT?! 🤯 World Cup 2026 highlights",
        "Canada's journey - World Cup 2026 🇨🇦",
    ],
    "instagram": [
        "This energy is unmatched ⚽🔥 World Cup 2026. Who's your pick? #WorldCup #Betway",
        "The beautiful game. The biggest stage. #WorldCup2026 #Betway",
        "Every moment counts. #WorldCup #BetwayCanada",
    ],
    "facebook": [
        "World Cup 2026 highlights! What a match! Who are you supporting?",
        "The World Cup is heating up! Don't miss a moment with Betway Canada 🇨🇦⚽",
        "Incredible plays from today's match. Canada making us proud!",
    ],
}

HASHTAGS = {
    "tiktok": ["#WorldCup", "#Betway", "#Canada", "#Football", "#Soccer", "#WorldCup2026", "#FIFA"],
    "youtube": ["#WorldCup", "#Betway", "#Shorts", "#Canada", "#Football"],
    "instagram": ["#WorldCup", "#Betway", "#Canada", "#Football", "#Soccer", "#WorldCup2026"],
    "facebook": ["#WorldCup", "#Betway", "#Canada", "#Football"],
}

OVERLAY_ASSETS = {
    "betway_logo": "betway_logo.png",
    "fire": "fire_overlay.gif",
    "canada_flag": "canada_flag.png",
}

THUMBNAIL_TEMPLATES = [
    {
        "name": "action_shot",
        "elements": [
            {"type": "background", "source": "frame_from_video"},
            {"type": "overlay", "asset": "betway_logo", "position": "top_left"},
            {"type": "text", "content": "WORLD CUP 2026", "font_size": 48, "position": "bottom_center", "color": "white", "stroke": "black"},
        ]
    },
    {
        "name": "score_display",
        "elements": [
            {"type": "background", "source": "gradient_dark"},
            {"type": "text", "content": "{home_team} vs {away_team}", "font_size": 36, "position": "top_center"},
            {"type": "text", "content": "{home_score} - {away_score}", "font_size": 64, "position": "center", "color": "yellow"},
            {"type": "overlay", "asset": "betway_logo", "position": "bottom_right"},
        ]
    },
]
