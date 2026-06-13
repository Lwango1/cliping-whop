VIDEO_INTRO_TEMPLATES = [
    {
        "text": "WORLD CUP 2026",
        "overlay": "fire",
        "duration": 3,
        "style": "bold_center"
    },
    {
        "text": "CANADA VS THE WORLD",
        "duration": 2,
        "style": "simple_center"
    },
]

VIDEO_OUTRO_TEMPLATES = [
    {
        "text": "Subscribe for more!",
        "duration": 2,
        "style": "simple_center"
    },
    {
        "text": "See you next match!",
        "duration": 2,
        "style": "simple_center"
    },
]

SOCIAL_CAPTIONS = {
    "tiktok": [
        "World Cup 2026 is here! Who's winning it all? ⚽ #WorldCup #Canada",
        "This moment was INSANE 🔥 #WorldCup #Football",
        "CANADA at the World Cup - let's go! 🇨🇦⚽ #WorldCup2026",
    ],
    "youtube_shorts": [
        "World Cup 2026 - Best moments #shorts",
        "He did WHAT?! 🤯 World Cup 2026 highlights",
        "Canada's journey - World Cup 2026 🇨🇦",
    ],
    "instagram": [
        "This energy is unmatched ⚽🔥 World Cup 2026. Who's your pick? #WorldCup",
        "The beautiful game. The biggest stage. #WorldCup2026",
        "Every moment counts. #WorldCup",
    ],
    "facebook": [
        "World Cup 2026 highlights! What a match! Who are you supporting?",
        "The World Cup is heating up!",
        "Incredible plays from today's match. Canada making us proud!",
    ],
}

HASHTAGS = {
    "tiktok": ["#WorldCup", "#Canada", "#Football", "#Soccer", "#WorldCup2026", "#FIFA"],
    "youtube": ["#WorldCup", "#Shorts", "#Canada", "#Football"],
    "instagram": ["#WorldCup", "#Canada", "#Football", "#Soccer", "#WorldCup2026"],
    "facebook": ["#WorldCup", "#Canada", "#Football"],
}

OVERLAY_ASSETS = {
    "fire": "fire_overlay.gif",
    "canada_flag": "canada_flag.png",
}

THUMBNAIL_TEMPLATES = [
    {
        "name": "action_shot",
        "elements": [
            {"type": "background", "source": "frame_from_video"},
            {"type": "text", "content": "WORLD CUP 2026", "font_size": 48, "position": "bottom_center", "color": "white", "stroke": "black"},
        ]
    },
    {
        "name": "score_display",
        "elements": [
            {"type": "background", "source": "gradient_dark"},
            {"type": "text", "content": "{home_team} vs {away_team}", "font_size": 36, "position": "top_center"},
            {"type": "text", "content": "{home_score} - {away_score}", "font_size": 64, "position": "center", "color": "yellow"},
        ]
    },
]
