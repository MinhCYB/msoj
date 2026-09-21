FEATURE_AI_BRAINSTORM = 'ai_brainstorm'
FEATURE_AI_REVIEW = 'ai_review'
FEATURE_PERSONALIZED_ROADMAP = 'personalized_roadmap'

FEATURE_CHOICES = (
    (FEATURE_AI_BRAINSTORM, 'AI brainstorm ý tưởng'),
    (FEATURE_AI_REVIEW, 'AI review sau nộp bài'),
    (FEATURE_PERSONALIZED_ROADMAP, 'Roadmap cá nhân hoá'),
)

ALL_FEATURES = {choice[0] for choice in FEATURE_CHOICES}
