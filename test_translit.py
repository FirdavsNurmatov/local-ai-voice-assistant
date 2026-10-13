pairs = [
    ("салом, бугун қандайсиз?", "salom, bugun qanday siz?"),
    ("робот китобхонада одамларга ёрдам бера олади.", "robot kutubxonada odamlarga yordam bera oladi."),
    ("ёрдамингиз учун раҳмат.", "yordamingiz uchun rahmat."),
    ("тошкент қаерда жойлашган?", "toshkent qayerda joylashgan?"),
]

mapping = {
    "а":"a", "б":"b", "в":"v", "г":"g", "д":"d", "е":"e",
    "ё":"yo", "ж":"j", "з":"z", "и":"i", "й":"y", "к":"k",
    "л":"l", "м":"m", "н":"n", "о":"o", "п":"p", "р":"r",
    "с":"s", "т":"t", "у":"u", "ф":"f", "х":"x", "ц":"ts",
    "ч":"ch", "ш":"sh", "щ":"shch", "ъ":"'", "ы":"i", "ь":"",
    "э":"e", "ю":"yu", "я":"ya", "қ":"q", "ғ":"g'", "ҳ":"h",
    "ў":"o'",
}

def transliterate(text):
    result = []
    for char in text:
        lower = char.lower()
        if lower in mapping:
            value = mapping[lower]
            result.append(value.capitalize() if char.isupper() else value)
        else:
            result.append(char)
    return "".join(result)

for source, expected in pairs:
    print("Kirill:   ", source)
    print("Lotin:    ", transliterate(source))
    print("Kutilgan: ", expected)
    print()
