WMO_TO_YANDEX_CONDITION = {
    0: "clear",
    1: "partly-cloudy",
    2: "partly-cloudy",
    3: "cloudy",
    45: "fog",
    48: "fog",
    51: "light-rain",
    53: "rain",
    55: "heavy-rain",
    56: "sleet",
    57: "sleet",
    61: "light-rain",
    63: "rain",
    65: "heavy-rain",
    66: "sleet",
    67: "sleet",
    71: "light-snow",
    73: "snow",
    75: "snowfall",
    77: "hail",
    80: "showers",
    81: "showers",
    82: "showers",
    85: "snow",
    86: "snowfall",
    95: "thunderstorm",
    96: "thunderstorm-with-hail",
    99: "thunderstorm-with-hail",
}

CONDITION_TO_ICON = {
    "clear": "skc_d",
    "partly-cloudy": "bkn_d",
    "cloudy": "bkn_d",
    "overcast": "ovc",
    "fog": "fg_d",
    "light-rain": "ovc_-ra",
    "rain": "ovc_ra",
    "heavy-rain": "ovc_+ra",
    "showers": "ovc_ra",
    "sleet": "ovc_ra_sn",
    "light-snow": "ovc_-sn",
    "snow": "ovc_sn",
    "snowfall": "ovc_+sn",
    "heavy-snow": "ovc_+sn",
    "hail": "ovc_ha",
    "thunderstorm": "ovc_ts",
    "thunderstorm-with-rain": "ovc_ts_ra",
    "thunderstorm-with-hail": "ovc_ts_ha",
    "light-blizzard": "-bl",
    "blizzard": "bl",
    "dust": "dst",
    "dust-storm": "du_st",
    "smog": "smog",
    "storm": "strm",
    "volcano": "vlka",
}

YANDEX_CONDITION_NAMES = {
    "clear": "Ясно",
    "partly-cloudy": "Малооблачно",
    "cloudy": "Облачно с прояснениями",
    "overcast": "Пасмурно",
    "fog": "Туман",
    "light-rain": "Небольшой дождь",
    "rain": "Дождь",
    "heavy-rain": "Сильный дождь",
    "showers": "Ливень",
    "sleet": "Дождь со снегом",
    "light-snow": "Небольшой снег",
    "snow": "Снег",
    "snowfall": "Снегопад",
    "heavy-snow": "Сильный снегопад",
    "hail": "Град",
    "thunderstorm": "Гроза",
    "thunderstorm-with-rain": "Гроза с дождём",
    "thunderstorm-with-hail": "Гроза с градом",
    "light-blizzard": "Метель",
    "blizzard": "Сильная метель",
    "dust": "Пыль",
    "dust-storm": "Пыльная буря",
    "smog": "Смог",
    "storm": "Шторм",
    "volcano": "Извержение вулкана",
}

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def degree_to_wind_direction(degree):
    if degree is None:
        return "—"
    deg = (float(degree) + 360) % 360
    if deg >= 337.5 or deg < 22.5:
        return "С"
    if deg >= 22.5 and deg < 67.5:
        return "СВ"
    if deg >= 67.5 and deg < 112.5:
        return "В"
    if deg >= 112.5 and deg < 157.5:
        return "ЮВ"
    if deg >= 157.5 and deg < 202.5:
        return "Ю"
    if deg >= 202.5 and deg < 247.5:
        return "ЮЗ"
    if deg >= 247.5 and deg < 292.5:
        return "З"
    if deg >= 292.5 and deg < 337.5:
        return "СЗ"
    return "Штиль"
