import re

input_file = "Simulation.py"
output_file = "wyjscie_bez_polskich_znakow.txt"

def usun_polskie_litery_emoji_i_komentarze(tekst):
    # Usuwanie docstringów """ lub '''
    tekst = re.sub(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', '', tekst)

    # Usuwanie komentarzy (linia od # do końca, z pominięciem # w stringach)
    tekst = re.sub(r'(?m)^([^"\']*?)#.*$', r'\1', tekst)  # usuwa tylko jeśli # nie jest w stringu

    # Zamiana polskich znaków
    zamiany = {
        '–': '-',
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l',
        'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L',
        'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    tekst = ''.join(zamiany.get(znak, znak) for znak in tekst)

    # Usuwanie emoji
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u200d"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\u3030"
        u"\ufe0f"
        "]+", flags=re.UNICODE)
    tekst = emoji_pattern.sub('', tekst)

    return tekst

# Wczytaj i przetwórz
with open(input_file, 'r', encoding='utf-8') as f:
    kod = f.read()

oczyszczony = usun_polskie_litery_emoji_i_komentarze(kod)

# Zapisz do pliku
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(oczyszczony)

print(f"✅ Zapisano do: {output_file}")
