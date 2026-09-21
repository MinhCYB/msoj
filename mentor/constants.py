# Ngưỡng thời gian active (giây) để tăng cấp độ gợi ý trong brainstorm session.
# Cấp 1: dưới 10 phút. Cấp 2: 10-25 phút. Cấp 3: trên 25 phút.
HINT_LEVEL_1_THRESHOLD_SECONDS = 0
HINT_LEVEL_2_THRESHOLD_SECONDS = 10 * 60
HINT_LEVEL_3_THRESHOLD_SECONDS = 25 * 60

# Sau bao lâu không hoạt động thì coi là idle, không cộng vào total_active_seconds.
IDLE_TIMEOUT_SECONDS = 5 * 60


def compute_hint_level(total_active_seconds):
    """Trả về 1, 2, hoặc 3 dựa trên tổng thời gian active."""
    if total_active_seconds >= HINT_LEVEL_3_THRESHOLD_SECONDS:
        return 3
    if total_active_seconds >= HINT_LEVEL_2_THRESHOLD_SECONDS:
        return 2
    return 1
