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

OWM_TO_CONDITION = {
    200: "thunderstorm-with-rain",
    201: "thunderstorm-with-rain",
    202: "thunderstorm-with-rain",
    210: "thunderstorm",
    211: "thunderstorm",
    212: "thunderstorm",
    221: "thunderstorm",
    230: "thunderstorm-with-rain",
    231: "thunderstorm-with-rain",
    232: "thunderstorm-with-rain",
    300: "light-rain",
    301: "light-rain",
    302: "rain",
    310: "light-rain",
    311: "light-rain",
    312: "rain",
    313: "showers",
    314: "showers",
    321: "showers",
    500: "light-rain",
    501: "rain",
    502: "heavy-rain",
    503: "heavy-rain",
    504: "heavy-rain",
    511: "sleet",
    520: "showers",
    521: "showers",
    522: "showers",
    531: "showers",
    600: "light-snow",
    601: "snow",
    602: "snowfall",
    611: "sleet",
    612: "sleet",
    613: "sleet",
    615: "sleet",
    616: "sleet",
    620: "light-snow",
    621: "snow",
    622: "snowfall",
    701: "fog",
    711: "smog",
    721: "fog",
    731: "dust",
    741: "fog",
    751: "dust",
    761: "dust",
    762: "volcano",
    771: "storm",
    781: "storm",
    800: "clear",
    801: "partly-cloudy",
    802: "partly-cloudy",
    803: "cloudy",
    804: "overcast",
}


def owm_code_to_condition(code: int) -> str:
    if code in OWM_TO_CONDITION:
        return OWM_TO_CONDITION[code]
    if 200 <= code < 300:
        return "thunderstorm"
    if 300 <= code < 400:
        return "light-rain"
    if 500 <= code < 600:
        return "rain"
    if 600 <= code < 700:
        return "snow"
    if 700 <= code < 800:
        return "fog"
    if code == 800:
        return "clear"
    if code > 800:
        return "cloudy"
    return "clear"

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


def degree_to_wind_arrow(degree):
    if degree is None:
        return ""
    deg = (float(degree) + 360) % 360
    if deg >= 337.5 or deg < 22.5:
        return "↓"
    if deg >= 22.5 and deg < 67.5:
        return "↙"
    if deg >= 67.5 and deg < 112.5:
        return "←"
    if deg >= 112.5 and deg < 157.5:
        return "↖"
    if deg >= 157.5 and deg < 202.5:
        return "↑"
    if deg >= 202.5 and deg < 247.5:
        return "↗"
    if deg >= 247.5 and deg < 292.5:
        return "→"
    if deg >= 292.5 and deg < 337.5:
        return "↘"
    return ""
