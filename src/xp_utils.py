def format_integer(value):
    return f"{int(value):,}".replace(",", " ")


def format_duration(seconds):
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if seconds or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)


def xp_for_next_level(level, base):
    return max(1, int(level * base))


def apply_role_xp(progress, amount, max_level, base):
    progress["xp"] = max(0, int(progress.get("xp", 0)) + int(amount))
    progress["level"] = max(1, min(max_level, int(progress.get("level", 1))))
    levels_gained = 0

    while progress["level"] < max_level:
        needed = xp_for_next_level(progress["level"], base)
        if progress["xp"] < needed:
            break
        progress["xp"] -= needed
        progress["level"] += 1
        levels_gained += 1

    if progress["level"] >= max_level:
        progress["level"] = max_level
        progress["xp"] = min(progress["xp"], xp_for_next_level(max_level, base))

    return levels_gained
