VIDEO_INTRO_TEMPLATES = [
    {"text": "Best Moments", "overlay": "fire", "duration": 3, "style": "bold_center"},
    {"text": "You Won't Believe This!", "duration": 2, "style": "simple_center"},
]

VIDEO_OUTRO_TEMPLATES = [
    {"text": "Subscribe for more!", "duration": 2, "style": "simple_center"},
    {"text": "Thanks for watching!", "duration": 2, "style": "simple_center"},
]

SOCIAL_CAPTIONS = {
    "tiktok": [
        "Check this out! 🔥 #Trending",
        "This is absolutely INSANE 🤯",
        "Wait for it... 💥",
    ],
    "youtube_shorts": [
        "Best moments you need to see #shorts",
        "Wait till the end! 🤯 #shorts",
        "This is too good 🔥 #shorts",
    ],
    "instagram": [
        "This energy is unmatched 🔥",
        "You need to see this 👀",
        "Absolutely incredible 💯",
    ],
    "facebook": [
        "Check out these amazing moments!",
        "You won't believe this!",
        "Share with someone who needs to see this!",
    ],
}

HASHTAGS = {
    "tiktok": ["#Trending", "#Viral", "#FYP", "#MustWatch", "#BestMoments"],
    "youtube": ["#Shorts", "#Trending", "#BestMoments", "#MustWatch"],
    "instagram": ["#Trending", "#Viral", "#BestMoments", "#MustWatch"],
    "facebook": ["#Trending", "#MustWatch", "#BestMoments"],
}

OVERLAY_ASSETS = {
    "fire": "fire_overlay.gif",
}

THUMBNAIL_TEMPLATES = [
    {
        "name": "action_shot",
        "elements": [
            {"type": "background", "source": "frame_from_video"},
            {"type": "text", "content": "BEST MOMENTS", "font_size": 48, "position": "bottom_center", "color": "white", "stroke": "black"},
        ]
    },
]
