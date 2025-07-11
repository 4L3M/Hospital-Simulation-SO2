import csv
import os


import traceback
from cProfile import label
import tkinter as tk
import random
import threading
import time
from collections import defaultdict
from queue import Queue
import sys
from queue import Empty



"""

 
OK - pacjenci ktorzy sa od razu do lekarza kierowani
 za dlugo sie wyswietlaja pod pielegniarka mimo ze juz go tam nie ma!!!

OK - zmienic proporcje spadku i wzrostu krytyczności pacjenta

Dodać:
OK - zmienna liczba pacjentów!,pielęgniarek, lekarzy
OK - zmienny czas pracy lekarza (bo kilku na oddziale)
OK - zmienna liczba łóżek na oddziale
0K - zmienna liczba badań, ale ma być dosyć dużo możliwych
OK - dodać leki - zmienne zasoby które się kończą, trzeba domówić i one się odnawiają
OK - dodać możliwość śmierci pacjenta

- STATYSTYKI
- ile czasu ktoś spędził w szpitalu, ile badań miał, ile czekał na przyjęcie (łóżko)

OK - dodać kilku lekarzy na oddziale, którzy się zmieniają - mają czas pracy i po pewnym czasie mają przerwę
OK - pielęgniarki - mają czas pracy i po pewnym czasie mają przerwę

- WIĘCEJ WSZYSTKIEGO!!!

"""

MUTEX = threading.Lock()

PACJENTÓW = random.randint(3, 5)  # liczba pacjentów na start
PIELEGNIARKI = random.randint(3,9)
LEKARZE_NA_ODDZIAL = (1, 5)  # liczba lekarzy na oddziale

ODDZIALY = ["Chirurgia", "Interna", "Ortopedia", "Neurologia", "Kardiologia", "Pediatria", "Onkologia"]
KOLORY = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
BADANIA = ["RTG", "USG", "EKG", "KREW", "Konsultacja", "Kolonoskopia", "Gastroskopia", "CT", "MR", "Biopsja"]
P_BADANIA = 0.7

def średnia(lista):
    return round(sum(lista) / len(lista), 2) if lista else 0

class Pacjent:
    def __init__(self, id, canvas, app):
        self.id = id
        self.krytycznosc = random.randint(50, 200)  # 0 - śmierć, im mniej tym większa szansa na śmierć
        self.status = "Izba"
        self.oddzial_docelowy = None
        self.badania_do_wykonania = []
        if random.random() < P_BADANIA:
            ile = random.randint(1, 4)
            self.badania_do_wykonania = random.sample(BADANIA, ile)
        else:
            self.badania_do_wykonania = []

        self.w_trakcie_badania = False
        self.lock = threading.Lock()  # mutex dla pacjenta

        self.liczba_badan = 0
        self.czy_ma_lozko = False
        self.index_lozka = None

        self.czas_u_pielegniarki = 0  # czas w sekundach
        self.start_pielegniarki = None

        self.canvas = canvas
        self.color = KOLORY[id % len(KOLORY)]
        self.x, self.y = 0, 0
        self.czas_na_odziale = 0
        self.oval = canvas.create_oval(self.x, self.y, self.x + 15, self.y + 15, fill=self.color)
        self.leki = {}
        self.label = canvas.create_text(
            self.x, self.y + 25,
            text=f"{self.krytycznosc}%", font=("Arial", 8),
            fill="black",
            tags=f"label_pacjent_{self.id}"
        )

        self.historia = {
            "czas_w_szpitalu": 0,
            "czas_oczekiwania_na_lozko": 0,
            "czas_w_izbie": 0,
            "czas_u_pielegniarki": 0,
            "czas_przyjecia_na_oddzial": 0,
            "leki_przyjete": {},
            "badania": [],
            "czas_przybycia": app.symulowany_czas if hasattr(app, "symulowany_czas") else 0 # czas przybycia do szpitala
        }

        print(f"Pacjent {self.id} ({self.status}) - badania: {self.badania_do_wykonania}, czas na oddziale: {self.czas_na_odziale}")


    def move_to(self, x, y):
        dx, dy = x - self.x, y - self.y
        self.x, self.y = x, y

        def update_gui():
            try:
                self.canvas.move(self.oval, dx, dy)
                self.canvas.move(self.label, dx, dy)

                # Aktualizacja tekstu labela
                oddzial = self.status.split()[-1]  # wyciągamy nazwę oddziału z końca statusu
                self.canvas.itemconfig(self.label, text=f" {self.id} || {int(self.krytycznosc)} | {oddzial}")

                # Kolor obramowania w zależności od stanu
                if self.krytycznosc > 120:
                    outline = "yellow"
                elif self.krytycznosc > 60:
                    outline = "orange"
                elif self.krytycznosc > 0:
                    outline = "red"
                else:
                    outline = "black"

                self.canvas.itemconfig(self.oval, outline=outline, width=3)

            except Exception as e:
                print(f"[move_to] Błąd aktualizacji GUI pacjenta {self.id}: {e}")

        self.canvas.after(0, update_gui)


class Lekarz(threading.Thread):
    def __init__(self, nazwa_oddzialu, x, y, canvas, numer, app_ref):
        super().__init__()
        self.app = app_ref
        self.nazwa = nazwa_oddzialu
        self.numer  = numer

        self.dlugosc_dyzuru = random.choice( [6*60, 8*60, 12*60, 24*60])  # godziny pracy lekarza

        offset = random.randint(0, 6 * 60)
        self.start_dyzuru = self.app.symulowany_czas - offset  # rozpoczęcie dyżuru w losowym momencie
        self.w_pracy = True

        self.x = x
        self.y = y
        self.canvas = canvas
        self.kolejka = []
        self.pacjent = None
        self.gotowi = []

        self.w_gabinecie = True
        self.czas_poza_gabinetem = 0
        self.czas_rozpoczecia_obchodu = None
        self.czas_pracy = 0
        self.lock = MUTEX
        self.stop_event = threading.Event()
        self.rect_id = None
        self.label_id = None

        self.rect_id = canvas.create_rectangle(
            self.x - 20, self.y + 25, self.x + 35, self.y + 45,
            outline="black", fill="lightgray"
        )
        self.label_id = canvas.create_text(
            self.x + 7, self.y + 35, text=f"Lekarz {self.numer}", font=("Arial", 7)
        )




    def skonsultuj(self, pacjent):
        with self.lock:
            self.kolejka.append(pacjent)

    def run(self):
        while not self.stop_event.is_set():
            # Czy czas pracy minął?
            if self.w_pracy and (self.app.symulowany_czas - self.start_dyzuru >= self.dlugosc_dyzuru) and self.pacjent is None:
                print(f"🛌 Lekarz {self.nazwa} #{self.numer} kończy dyżur i idzie na 12h przerwy.")
                self.w_pracy = False
                self.start_dyzuru = self.app.symulowany_czas
                self.canvas.itemconfig(self.rect_id, fill="gray")
                continue

            # Czy czas przerwy minął?
            if not self.w_pracy:
                if self.app.symulowany_czas - self.start_dyzuru >= 12 * 60:
                    print(f"👨‍⚕️ Lekarz {self.nazwa} #{self.numer} wraca do pracy.")
                    self.w_pracy = True
                    self.dlugosc_dyzuru = random.choice([12 * 60, 24 * 60])
                    self.start_dyzuru = app.symulowany_czas
                    self.canvas.itemconfig(self.rect_id, fill="lightgreen")
                else:
                    time.sleep(0.1)
                    continue

            # Co jakiś czas wychodzi z gabinetu na obchód
            if self.w_gabinecie and random.random() < 0.01:
                self.w_gabinecie = False
                self.czas_rozpoczecia_obchodu = time.monotonic()
                print(f"Lekarz {self.nazwa} #{self.numer} wyszedł na oddział.")

            if not self.w_gabinecie and self.czas_rozpoczecia_obchodu is not None:
                if time.monotonic() - self.czas_rozpoczecia_obchodu > 5:
                    self.w_gabinecie = True
                    print(f"Lekarz {self.nazwa} #{self.numer} wrócił do gabinetu.")
                time.sleep(0.1)
                continue

            # Obsługa pacjentów tylko jeśli w gabinecie
            with self.lock:
                pacjent = self.kolejka.pop(0) if self.kolejka else None

            if pacjent is None or pacjent.status == "Zmarł":
                time.sleep(0.1)
                continue

            if pacjent:
                with self.lock:
                    self.pacjent = pacjent
                    pacjent.status = f"Konsultacja {self.nazwa}"
                time.sleep(random.uniform(2, 4))

                # zmiana = random.randint(-40, 40)
                # procent = 1 + zmiana / 100
                # stary_czas = pacjent.czas_na_odziale
                # nowy_czas = max(30, int(stary_czas * procent))
                # pacjent.czas_na_odziale = nowy_czas

                # print(
                #     f"[{self.nazwa}] Pacjent {pacjent.id} – czas pobytu zmieniony z {stary_czas} do {nowy_czas} min ({zmiana:+}%)")

                pacjent.status = f"{self.nazwa} - gotowy"
                self.gotowi.append(pacjent)
                with self.lock:
                    self.pacjent = None
            else:
                time.sleep(0.1)

    def zatrzymaj(self):
        self.stop_event.set()

    def get_pacjent(self):
        with self.lock:
            return self.pacjent

    def get_kolejka(self):
        with self.lock:
            return list(self.kolejka)


class Oddzial:
    def __init__(self, nazwa, liczba_lozek, lekarze, app):
        self.nazwa = nazwa
        self.lozka = [None for _ in range(liczba_lozek)]
        self.kolejka = Queue()
        self.lock = MUTEX
        self.lekarze = lekarze # lista lekarzy na oddziale
        self.app = app

    def przyjmij_pacjenta(self, pacjent):
        losowy_lekarz = random.choice(self.lekarze)
        losowy_lekarz.skonsultuj(pacjent)

    def zakwateruj_po_konsultacji(self, pacjent):
        with self.lock:
            if pacjent in self.lozka:
                return True

            if pacjent in list(self.kolejka.queue):
                return False

            for i in range(len(self.lozka)):
                if self.lozka[i] is None:
                    self.lozka[i] = pacjent
                    pacjent.status = f"{self.nazwa}|łóżko {i + 1}"

                    pacjent.historia["czas_przyjecia_na_oddzial"] = self.app.symulowany_czas

                    pacjent.czy_ma_lozko = True
                    pacjent.historia["czas_oczekiwania_na_lozko"] = self.app.symulowany_czas - pacjent.historia[
                        "czas_przybycia"]

                    pacjent.index_lozka = i

                    pacjent.leki = {}
                    for lek_nazwa in random.sample(list(app.leki.keys()), random.randint(1, 4)):
                        czestotliwosc = random.choice([8, 12, 24])  # w godzinach
                        pacjent.leki[lek_nazwa] = {
                            "czestotliwosc": czestotliwosc,
                            "ostatnio": app.symulowany_czas  # czas zakwaterowania
                        }

                    return True

            # Jeśli nie ma wolnego łóżka, dodaj do kolejki oczekujących
            self.kolejka.put(pacjent)
            pacjent.status = f"{self.nazwa}|czeka"
            return False

    def zwolnij_lozko(self, pacjent):
        with self.lock:
            idx = None
            for i in range(len(self.lozka)):
                if self.lozka[i] == pacjent:
                    self.lozka[i] = None
                    idx = i
                    break
            if idx is not None and not self.kolejka.empty():
                nowy = self.kolejka.get()
                self.lozka[idx] = nowy
                nowy.status = f"{self.nazwa} - łóżko {idx + 1}"
                nowy.czy_ma_lozko = True
                nowy.index_lozka = idx

class GabinetBadania:
    def __init__(self, nazwa, x, y, canvas):
        self.nazwa = nazwa
        self.kolejka = Queue()
        self.x = x
        self.y = y
        self.canvas = canvas
        self.aktywny_pacjent = None
        self.lock = MUTEX
        self.rect_id = None
        self.label_id = None

    def dodaj_pacjenta(self, pacjent):
        self.kolejka.put(pacjent)

    def get_kolejka(self):
        with self.lock:
            return list(self.kolejka.queue)

    def set_aktywny(self, pacjent):
        with self.lock:
            self.aktywny_pacjent = pacjent

    def get_aktywny(self):
        with self.lock:
            return self.aktywny_pacjent

class LekarzDiagnosta(threading.Thread):
    def __init__(self, gabinet, oddzialy, app_ref):
        super().__init__()
        self.app = app_ref
        self.gabinet = gabinet
        self.oddzialy = oddzialy
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                pacjent = self.gabinet.kolejka.get(timeout=1)
            except Empty:
                continue  # normalne – brak pacjenta w kolejce

            try:
                if pacjent.status == "Zmarł":
                    continue

                self.gabinet.set_aktywny(pacjent)
                pacjent.status = f"Badanie: {self.gabinet.nazwa}"
                pacjent.w_trakcie_badania = True
                pacjent.historia["badania"].append(self.gabinet.nazwa)
                pacjent.move_to(self.gabinet.x, self.gabinet.y)
                time.sleep(random.uniform(3, 5))

                self.app.popraw_krytycznosc(pacjent, random.randint(10, 50))

                oddzial = self.oddzialy.get(pacjent.oddzial_docelowy)
                if oddzial and self.app.sprawdz_zgon(pacjent, oddzial):
                    self.gabinet.set_aktywny(None)
                    pacjent.w_trakcie_badania = False
                    continue

                if self.gabinet.nazwa in pacjent.badania_do_wykonania:
                    pacjent.badania_do_wykonania.remove(self.gabinet.nazwa)

                pacjent.historia["badania"].append(self.gabinet.nazwa)
                self.app.statystyki["badania"][self.gabinet.nazwa] += 1

                pacjent.move_to(self.gabinet.x, self.gabinet.y + 30)
                self.gabinet.set_aktywny(None)
                with pacjent.lock:
                    pacjent.w_trakcie_badania = False
                if pacjent.krytycznosc <= 0:
                    if oddzial:
                        self.app.sprawdz_zgon(pacjent, oddzial)
                    continue

                if pacjent.czy_ma_lozko:
                    pacjent.status = "Powrót na łóżko"

                elif pacjent.badania_do_wykonania:
                    kolejny = pacjent.badania_do_wykonania[0]
                    with pacjent.lock:
                        if not pacjent.w_trakcie_badania:
                            self.app.gabinety_badan[kolejny].dodaj_pacjenta(pacjent)
                            pacjent.w_trakcie_badania = True

                elif oddzial:
                    # Najpierw spróbuj zakwaterować
                    if oddzial.zakwateruj_po_konsultacji(pacjent):
                        pacjent.status = f"{oddzial.nazwa} - łóżko {pacjent.index_lozka + 1}"
                    else:
                        pacjent.status = f"{oddzial.nazwa} (oczekuje)"
                        with oddzial.lock:
                            if pacjent not in list(oddzial.kolejka.queue):
                                oddzial.kolejka.put(pacjent)

            except Exception as e:
                print(f"[Diagnosta] Błąd podczas przetwarzania pacjenta: {e}")
                traceback.print_exc()

    def zatrzymaj(self):
        self.stop_event.set()


class Pielegniarka(threading.Thread):
    def __init__(self, id, x, y, canvas, oddzialy, kolejka_wejsciowa, app_ref):
        super().__init__()
        self.app = app_ref
        self.id = id
        self.x = x
        self.y = y

        self.dlugosc_dyzuru = random.choice([12 * 60, 24 * 60])  # 12h lub 24h
        offset = random.randint(0, 6 * 60)  # max 6h przesunięcia
        self.start_dyzuru = self.app.symulowany_czas - offset
        self.w_pracy = True
        self.start_przerwy = None

        self.niedostepna = random.random() < 0.2  # czy pielęgniarka jest niedostępna

        self.canvas = canvas
        self.oddzialy = oddzialy
        self.kolejka = kolejka_wejsciowa
        self.pacjent = None
        self.stop_event = threading.Event()
        self.lock = MUTEX

    def run(self):
        while not self.stop_event.is_set():
            try:
                # Czy dyżur się skończył?
                # opóźnij przerwę jeśli trwa obsługa
                if self.w_pracy and (self.app.symulowany_czas - self.start_dyzuru >= self.dlugosc_dyzuru):
                    with self.lock:
                        if self.pacjent is not None:
                            # Poczekaj, aż skończy obsługę
                            time.sleep(0.1)
                            continue
                        print(f"🛌 Pielęgniarka {self.id + 1} kończy dyżur i idzie na przerwę.")
                        self.w_pracy = False
                        self.start_przerwy = self.app.symulowany_czas

                    # 🛌 Sprawdzenie końca dyżuru DOPIERO PO obsłudze pacjenta
                    if self.w_pracy and (self.app.symulowany_czas - self.start_dyzuru >= self.dlugosc_dyzuru):
                        print(f"🛌 Pielęgniarka {self.id + 1} kończy dyżur i idzie na przerwę.")
                        self.w_pracy = False
                        self.start_przerwy = self.app.symulowany_czas

                    else:
                        # opóźnij przerwę – wróć do pętli, aż pacjent zostanie obsłużony
                        time.sleep(0.1)
                        continue

                # Czy przerwa się skończyła?
                if not self.w_pracy:
                    if self.app.symulowany_czas - self.start_przerwy >= 12 * 60:
                        print(f"👩‍⚕️ Pielęgniarka {self.id + 1} wraca po przerwie.")
                        self.w_pracy = True
                        self.dlugosc_dyzuru = random.choice([12 * 60, 24 * 60])
                        self.start_dyzuru = self.app.symulowany_czas
                    else:
                        time.sleep(1)
                        continue

                # Losowa chwilowa niedostępność (np. dokumentacja)
                if self.w_pracy and not self.niedostepna and random.random() < 0.02:
                    self.niedostepna = True
                    print(f"📋 Pielęgniarka {self.id + 1} chwilowo niedostępna (dokumentacja)")
                    threading.Thread(target=self.symuluj_niedostepnosc).start()

                # Próba pobrania pacjenta z kolejki (nie blokująco)
                if self.niedostepna:
                    time.sleep(1)
                    continue

                # Pobranie najbardziej krytycznego pacjenta
                with self.kolejka.mutex:
                    if not self.kolejka.queue:
                        time.sleep(0.1)
                        continue

                    # Odfiltruj zmarłych i None
                    kolejka_lista = [p for p in self.kolejka.queue if p is not None and p.status != "Zmarł"]
                    if not kolejka_lista:
                        time.sleep(0.1)
                        continue

                    kolejka_lista.sort(key=lambda p: p.krytycznosc)
                    pacjent = kolejka_lista.pop(0)

                    self.kolejka.queue.clear()
                    self.kolejka.queue.extend(kolejka_lista)

                # Dodaj zabezpieczenie na wszelki wypadek:
                if pacjent is None:
                    time.sleep(0.1)
                    continue

                    kolejka_lista.sort(key=lambda p: p.krytycznosc)
                    pacjent = kolejka_lista.pop(0)
                    self.kolejka.queue.clear()
                    self.kolejka.queue.extend(kolejka_lista)

                with self.lock:
                    self.pacjent = pacjent
                    pacjent.status = f"Pielęgniarka {self.id + 1}"

                pacjent.start_pielegniarki = self.app.symulowany_czas

                czas = self.app.symulowany_czas - pacjent.historia["czas_przybycia"]
                self.app.statystyki["średni_czas_w_izbie"].append(czas / 60)  # czas w izbie w minutach


                # Symulacja czasu obsługi (bez zablokowania całego wątku)
                time_start = time.time()
                time_to_work = random.uniform(2, 4)
                while time.time() - time_start < time_to_work:
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.1)



                # Przydziel pacjenta do oddziału
                oddzial_obj = random.choice(list(self.oddzialy.values()))
                pacjent.status = f"Oddział {oddzial_obj.nazwa}"
                pacjent.oddzial_docelowy = oddzial_obj.nazwa



                # Po zakończeniu obsługi pacjenta
                with self.lock:
                    self.pacjent = None
                    pacjent.czas_u_pielegniarki = self.app.symulowany_czas - pacjent.start_pielegniarki
                    if "Pielęgniarka" in pacjent.status:
                        pacjent.status = f"Oczekuje: {oddzial_obj.nazwa}"

                # # 50% szans na pójście do lekarza, 50% na próbę zakwaterowania od razu
                if random.random() < 0.5:
                    # idzie do lekarza (konsultacja)
                    pacjent.status = f"Oczekuje: {oddzial_obj.nazwa}"
                    oddzial_obj.przyjmij_pacjenta(pacjent)
                else:
                    # próba natychmiastowego zakwaterowania
                    if oddzial_obj.zakwateruj_po_konsultacji(pacjent):
                        pacjent.status = f"{oddzial_obj.nazwa} - łóżko {pacjent.index_lozka + 1}"
                    else:
                        pacjent.status = f"{oddzial_obj.nazwa} (oczekuje)"

                # DEBUG
                # Zawsze próba natychmiastowego zakwaterowania
                # if oddzial_obj.zakwateruj_po_konsultacji(pacjent):
                #     pacjent.status = f"{oddzial_obj.nazwa} - łóżko {pacjent.index_lozka + 1}"
                # else:
                #     pacjent.status = f"{oddzial_obj.nazwa} (oczekuje)"




            except Exception as e:
                print(f"Błąd wątku pielęgniarki {self.id + 1}: {e}")
                time.sleep(0.1)

    def symuluj_niedostepnosc(self):
        time.sleep(random.randint(1, 5))  # np. 10-20 sekund
        self.niedostepna = False
        print(f"✅ Pielęgniarka {self.id + 1} wróciła do przyjmowania pacjentów")

    def zatrzymaj(self):
        self.stop_event.set()

    def get_pacjent(self):
        with self.lock:
            return self.pacjent


class Lek:
    def __init__(self, nazwa):
        self.nazwa = nazwa
        self.ilosc = random.randint(3, 10)
        self.prog_minimalny = random.randint(2, 5)
        self.sztuki_dozamowienia = random.randint(5, 10)
        self.lock = threading.Lock() # każdy lek ma swój mutex
        self.czy_zamowiony = False

    def zuzyj(self):
        with self.lock:
            if self.ilosc < 0:
                print(f"⛔ Lek {self.nazwa} niedostępny – podanie wstrzymane!")
                return False
            self.ilosc -= 1

            print(f"✅ Podano lek {self.nazwa}, pozostało {self.ilosc} szt.")
            if self.ilosc <= self.prog_minimalny:
                self.zamow()
            return True

    def zamow(self):
        print(f"Zamówienie leku {self.nazwa}: {self.sztuki_dozamowienia} sztuk")
        self.ilosc += self.sztuki_dozamowienia
        print(f"Stan leku {self.nazwa}: {self.ilosc} sztuk")


class Symulacja:
    def __init__(self, root):
        self.canvas = tk.Canvas(root, width=1900, height=1000, bg='white')
        self.canvas.pack()
        self.root = root
        root.protocol("WM_DELETE_WINDOW", self.zakoncz_program)
        self.symulowany_czas = 8 * 60
        self.symulacja_tick = 0

        self.statystyki = {
            "pacjenci_na_oddziale": defaultdict(int),
            "pacjenci_w_szpitalu": [],
            "zgonów": 0,
            "wypisani": 0,
            "leki": defaultdict(int),
            "badania": defaultdict(int),
            "średni_czas_ocz_na_lozko": [],
            "średni_czas_w_szpitalu": [],
            "średni_czas_w_izbie": [],
            "nowi_pacjenci_dzienni": []  # lista krotek: (ciezki, sredni, lekki)

        }



        # STATYSTYKI OGOLNE ----------------------------------------------------------------------------------
        self.csv_folder = "statystyki"
        os.makedirs(self.csv_folder, exist_ok=True)
        self.csv_file = os.path.join(self.csv_folder, f"statystyki_{int(time.time())}.csv")

        with open(self.csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "dzien",
                "nowi pacjenci - stan ciezki",
                "nowi pacjenci - stan sredni",
                "nowi pacjenci - stan lekki",
                "zgony",
                "wypisani",
                "sredni czas w izbie (min)",
                "sredni czas ocz. na łozko (min)",
                "średni czas w szpitalu (min)",
                "leki",
                "badania"
            ])

            # STATYSTYKI ODDZIAŁÓW ----------------------------------------------------------------------------------

            self.csv_oddzialy_file = os.path.join(self.csv_folder, f"oddzialy_{int(time.time())}.csv")
            with open(self.csv_oddzialy_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "dzien", "oddzial", "pacjenci_przyjeci", "zgony", "wypisy",
                    "badania_przeprowadzone", "%_zapełnienia_łóżek", "pacjenci_na_lekarza"
                ])

        self.pacjenci = [Pacjent(i, self.canvas, self) for i in range(PACJENTÓW)]
        self.kolejka_wejsciowa = Queue()
        for pacjent in self.pacjenci:
            self.kolejka_wejsciowa.put(pacjent)

        self.lekarze = {}
        for i, nazwa in enumerate(ODDZIALY):
            ilu = random.randint(*LEKARZE_NA_ODDZIAL)
            lekarze_list = []
            for j in range(ilu):
                x = 100 + i * 250  # rozstaw
                y = 450 + j * 60
                lekarz = Lekarz(f"{nazwa}", x, y, self.canvas, j + 1, self)
                lekarz.start()
                lekarze_list.append(lekarz)
            self.lekarze[nazwa] = lekarze_list

        # Rysowanie gabinetów lekarzy
        # Stałe rysowanie lekarzy obok siebie nad gabinetami
        for lekarze_list in self.lekarze.values():
            for lekarz in lekarze_list:
                # ustal pozycję lekarza i jego gabinetu statycznie
                rect_x1 = lekarz.x - 40
                rect_y1 = lekarz.y - 20
                rect_x2 = lekarz.x + 40
                rect_y2 = lekarz.y + 20

                self.canvas.coords(lekarz.rect_id, rect_x1, rect_y1, rect_x2, rect_y2)
                self.canvas.coords(lekarz.label_id, lekarz.x, lekarz.y)

        self.oddzialy = {
            nazwa: Oddzial(nazwa, liczba_lozek=random.randint(3, 15), lekarze=self.lekarze[nazwa], app=self)
            for nazwa in ODDZIALY
        }

        self.gabinety_badan = {
            nazwa: GabinetBadania(nazwa, 100 + i * 150, 850, self.canvas)
            for i, nazwa in enumerate(BADANIA)
        }

        self.leki = {
            "Aspiryna": Lek("Aspiryna"),
            "Ibuprofen": Lek("Ibuprofen"),
            "Paracetamol": Lek("Paracetamol"),
            "Antybiotyk": Lek("Antybiotyk"),
            "Leki przeciwbólowe": Lek("Leki przeciwbólowe")
        }

        for i, (nazwa, gabinet) in enumerate(self.gabinety_badan.items()):
            gabinet_x = gabinet.x
            gabinet_y = gabinet.y
            width, height = 80, 40
            rect = self.canvas.create_rectangle(
                gabinet_x - width // 2,
                gabinet_y - height // 2,
                gabinet_x + width // 2,
                gabinet_y + height // 2,
                outline="black"
            )
            label = self.canvas.create_text(
                gabinet_x, gabinet_y, text=nazwa, font=("Arial", 9, "bold")
            )
            gabinet.rect_id = rect
            gabinet.label_id = label
        self.diagności = []
        for gabinet in self.gabinety_badan.values():
            diagnosta = LekarzDiagnosta(gabinet, self.oddzialy, self)
            diagnosta.start()
            self.diagności.append(diagnosta)


        self.wypisani = []
        self.zmarli = []

        self.pielegniarki = []
        for i in range(PIELEGNIARKI):
            x_pos = 150 + i * 150
            pielegniarka = Pielegniarka(i, x_pos, 100, self.canvas, self.oddzialy, self.kolejka_wejsciowa, self)
            pielegniarka.start()
            self.pielegniarki.append(pielegniarka)

        self.draw_labels()
        self.lozka_graficzne = {}
        self.lozka_rects = {}
        self.rysuj_lozka()
        self.update_gui()

        self.nastepny_id = PACJENTÓW
        self.generuj_pacjentow_thread = threading.Thread(target=self.generuj_nowych_pacjentow)
        self.generuj_pacjentow_thread.daemon = True
        self.generuj_pacjentow_thread.start()

    def generuj_nowych_pacjentow(self):
        while True:
            czas = random.uniform(1, 2)
            time.sleep(czas)

            nowy = Pacjent(self.nastepny_id, self.canvas, self)
            self.nastepny_id += 1
            self.pacjenci.append(nowy)
            self.kolejka_wejsciowa.put(nowy)
            print(f"➕ Nowy pacjent {nowy.id} dodany do kolejki (co {czas:.2f}s)")


# STATYSTYKI ---------------------------------------------------------

            dzien = self.symulowany_czas // (24 * 60) + 1  # dzień w symulacji

            # Rozszerz listę, jeśli trzeba
            while len(self.statystyki["nowi_pacjenci_dzienni"]) <= dzien:
                self.statystyki["nowi_pacjenci_dzienni"].append((0, 0, 0))

            # Załóżmy, że `nowy.krytycznosc` decyduje o stanie
            if nowy.krytycznosc < 70:
                typ = "krytyczny"
            elif nowy.krytycznosc < 130:
                typ = "średni"
            else:
                typ = "lekki"

            k, s, l = self.statystyki["nowi_pacjenci_dzienni"][dzien]
            if typ == "krytyczny":
                k += 1
            elif typ == "średni":
                s += 1
            else:
                l += 1

            self.statystyki["nowi_pacjenci_dzienni"][dzien] = (k, s, l)

    def draw_labels(self):
        for i, nazwa in enumerate(ODDZIALY):
           self.canvas.create_text(
                100 + i * 250, 400,
                text=f"Lekarz {nazwa}",
                font=("Arial", 9),
                tags="oddzial_pacjenci"
            )

        # 📦 Inne etykiety GUI
           self.canvas.create_text(1650, 50, text="Stan magazynu leków", font=("Arial", 10, "bold"),
                                tags="oddzial_pacjenci")

        for i, nazwa in enumerate(BADANIA):
            self.canvas.create_text(
                100 + i * 150, 780,
                text=f"GABINET {nazwa}",
                font=("Arial", 9),
                tags="oddzial_pacjenci"
            )

    def rysuj_lozka(self):
        for idx, (nazwa, oddzial) in enumerate(self.oddzialy.items()):
            for i in range(len(oddzial.lozka)):
                rzad = i // 3  # co 3 łóżka nowy rząd
                kol = i % 3  # kolumna w rzędzie

                base_x = 50 + idx * 250
                lx = base_x + kol * 50
                ly = 180 + rzad * 40

                rect = self.canvas.create_rectangle(lx, ly, lx + 30, ly + 20, outline="black")
                label = self.canvas.create_text(lx + 15, ly + 10, text=f"L{i + 1}", font=("Arial", 7))
                self.lozka_graficzne[(nazwa, i)] = (lx + 7, ly + 2)
                self.lozka_rects[(nazwa, i)] = rect

    def obniz_krytycznosc(self, pacjent, ile):
        pacjent.krytycznosc -= ile
        if pacjent.krytycznosc < 0:
            pacjent.krytycznosc = 0

    def popraw_krytycznosc(self, pacjent, ile):
        pacjent.krytycznosc = min(pacjent.krytycznosc + ile, 250)  # max 200

    def sprawdz_zgon(self, pacjent, oddzial):
        if pacjent and pacjent.krytycznosc <= 0 and pacjent.status != "Zmarł":
            pacjent.status = "Zmarł"

# STATYSTYKI ---------------------------------------------------------
            czas_w_szpitalu = self.symulowany_czas - pacjent.historia["czas_przybycia"]
            self.statystyki["średni_czas_w_szpitalu"].append(czas_w_szpitalu)
            self.statystyki["zgonów"] += 1
# --------------------------------------------------------------------

            self.zmarli.append(pacjent)


            if oddzial:
                oddzial.zwolnij_lozko(pacjent)
            else:
                print(f"⚠️ Pacjent {pacjent.id} zmarł, ale nie był przypisany do żadnego oddziału.")

            print(f"💀 Pacjent {pacjent.id} zmarł.")

            # Oznacz graficznie jako zmarły
            # Oznacz graficznie jako zmarły – tylko obramowanie na czarno
            self.canvas.itemconfig(pacjent.oval, outline="black", width=3)
            self.canvas.itemconfig(pacjent.label, text="")

            # Usuń z kolejki wejściowej
            with self.kolejka_wejsciowa.mutex:
                try:
                    self.kolejka_wejsciowa.queue.remove(pacjent)
                except ValueError:
                    pass

            # Usuń z kolejek lekarzy
            for lekarze in self.lekarze.values():
                for lekarz in lekarze:
                    with lekarz.lock:
                        if pacjent in lekarz.kolejka:
                            lekarz.kolejka.remove(pacjent)
                        if lekarz.pacjent == pacjent:
                            lekarz.pacjent = None

            # Usuń z kolejek oddziałów
            for oddzial in self.oddzialy.values():
                with oddzial.lock:
                    try:
                        oddzial.kolejka.queue.remove(pacjent)
                    except ValueError:
                        pass

            # Usuń z gabinetów badań
            for gabinet in self.gabinety_badan.values():
                with gabinet.lock:
                    if gabinet.aktywny_pacjent == pacjent:
                        gabinet.aktywny_pacjent = None
                    try:
                        gabinet.kolejka.queue.remove(pacjent)
                    except ValueError:
                        pass

            return True
        return False

    def sprawdz_wypis(self, pacjent, oddzial):
        if pacjent is None:
            return False
        if pacjent.krytycznosc >= 250 and pacjent.status != "Wypisany":
            if pacjent in self.wypisani:
                return False

            self.statystyki["wypisani"] += 1
            czas = pacjent.historia.get("czas_w_szpitalu", 0)
            self.statystyki["średni_czas_w_szpitalu"].append(czas)
            ocz = pacjent.historia.get("czas_oczekiwania_na_lozko", 0)
            self.statystyki["średni_czas_ocz_na_lozko"].append(ocz)

            for lek, liczba in pacjent.historia["leki_przyjete"].items():
                self.statystyki["leki"][lek] = self.statystyki["leki"].get(lek, 0) + liczba
            for bad in pacjent.historia["badania"]:
                self.statystyki["badania"][bad] = self.statystyki["badania"].get(bad, 0) + 1

            pacjent.status = "Wypisany"
            pacjent.historia["czas_w_szpitalu"] = self.symulowany_czas - pacjent.historia["czas_przybycia"]
            self.wypisani.append(pacjent)
            oddzial.zwolnij_lozko(pacjent)
            print(f"🏁 Pacjent {pacjent.id} został wypisany.")
            return True
        return False

    def update_gui(self):
        try:
            if self.symulowany_czas % (60 * 24) == 0 and self.symulacja_tick == 9:
                self.zapisz_statystyki_csv()

            for i, pacjent in enumerate(list(self.kolejka_wejsciowa.queue)):
                pacjent.move_to(50 + i * 30, 50)
                self.obniz_krytycznosc(pacjent, 0.2)  # zmniejszenie krytyczności co tick // gorszy stan

            self.canvas.delete("zegar_info")

            # 🕒 Zegar – dzień i godzina w prawym górnym rogu
            dzien = self.symulowany_czas // (24 * 60) + 1
            godzina = (self.symulowany_czas // 60) % 24
            minuta = self.symulowany_czas % 60
            czas_tekst = f"Dzień {dzien}, {godzina:02d}:{minuta:02d}"

            # Wymiary prostokąta
            x1, y1 = 1750, 10
            x2, y2 = 1890, 50

            # Ramka zegara
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="black", width=2,
                tags="zegar_info"
            )

            # Tekst zegara
            self.canvas.create_text(
                (x1 + x2) // 2, (y1 + y2) // 2,
                text=czas_tekst,
                font=("Arial", 10, "bold"),
                fill="black",
                tags="zegar_info"
            )
            self.canvas.delete("pacjenci")

            # 🔢 Zlicz pacjentów przypisanych do oddziałów (niezmarłych)
            przypisani = defaultdict(int)
            for pacjent in self.pacjenci:
                if pacjent.status != "Zmarł" and pacjent.oddzial_docelowy:
                    przypisani[pacjent.oddzial_docelowy] += 1

            # 🏥 Liczba wszystkich pacjentów w szpitalu
            wszyscy = sum(przypisani.values())
            self.canvas.create_text(
                1650, 30,
                text=f"Pacjenci w szpitalu: {wszyscy}",
                font=("Arial", 10, "bold"),
                fill="darkblue",
                tags="pacjenci"
            )

            # 🏥 Nazwy oddziałów + liczba pacjentów
            self.canvas.create_text(100, 30, text="Izba Przyjęć", font=("Arial", 10), tags="oddzial_pacjenci")
            for i, nazwa in enumerate(ODDZIALY):
                self.canvas.create_text(
                    100 + i * 250, 160,
                    text=f"Oddział {nazwa} ({przypisani.get(nazwa)} pac.)",
                    font=("Arial", 10),
                    tags="pacjenci"
                )

                # 🟦 Wypisani z liczbą
                self.canvas.create_text(
                    1550, 750,
                    text=f"Wypisani ({len(self.wypisani)})",
                    font=("Arial", 10),
                    tags="pacjenci"
                )

                # ⚫ Kostnica z liczbą
                self.canvas.create_text(
                    1750, 750,
                    text=f"Kostnica ({len(self.zmarli)})",
                    font=("Arial", 10),
                    tags="pacjenci"
                )

            # Licznik pacjentów u pielęgniarek
            liczniki_pacjentow = [0 for _ in self.pielegniarki]
            for i, pielegniarka in enumerate(self.pielegniarki):
                if pielegniarka.get_pacjent():
                    liczniki_pacjentow[i] += 1

            # 🧹 Usuń etykiety i pacjentów przy pielęgniarkach
            self.canvas.delete("pielegniarka_label")
            self.canvas.delete("pacjent_przy_pielegniarce")

            # 🧮 Zlicz ilu pacjentów jest przypisanych do każdego oddziału (oddzial_docelowy)
            przypisani = defaultdict(int)
            for pacjent in self.pacjenci:
                if pacjent.status != "Zmarł" and pacjent.oddzial_docelowy:
                    przypisani[pacjent.oddzial_docelowy] += 1



            for i, pielegniarka in enumerate(self.pielegniarki):
                x_pos = pielegniarka.x

                if not pielegniarka.w_pracy and pielegniarka.get_pacjent() is None:
                    kolor = "red"
                elif pielegniarka.niedostepna:
                    kolor = "orange"
                else:
                    kolor = "black"

                # Licznik nad etykietą
                self.canvas.create_text(
                    x_pos, 65,
                    text=f"{liczniki_pacjentow[i]} pac.",
                    font=("Arial", 8),
                    fill="black",
                    tags="pielegniarka_label"
                )

                self.canvas.create_text(
                    x_pos, 80,
                    text=f"Pielęgniarka {i + 1}",
                    font=("Arial", 10, "bold"),
                    fill=kolor,
                    tags="pielegniarka_label"
                )

                obslugiwany_pacjent = pielegniarka.get_pacjent()

                if obslugiwany_pacjent is not None:
                    obslugiwany_pacjent.move_to(pielegniarka.x, pielegniarka.y + 10)

            self.canvas.delete("gabinet_info")

            for gabinet in self.gabinety_badan.values():
                pacjent = gabinet.get_aktywny()
                if pacjent and pacjent.status != "Zmarł":
                    if pacjent is None or pacjent.status == "Zmarł":
                        continue
                    self.canvas.itemconfig(gabinet.rect_id, fill=pacjent.color)
                    pacjent.move_to(gabinet.x, gabinet.y)
                else:
                    self.canvas.itemconfig(gabinet.rect_id, fill="white")

                for j, p in enumerate(gabinet.get_kolejka()):
                    p.move_to(gabinet.x + j * 18, gabinet.y + 65)
                    self.obniz_krytycznosc(p, 0.2)  # zmniejszenie krytyczności co tick

                    # 🔼 liczba oczekujących (nad gabinetem)
                self.canvas.create_text(
                    gabinet.x, gabinet.y + 100,
                    text=f"{len(gabinet.get_kolejka())} w kolejce",
                    font=("Arial", 8),
                    fill="black",
                    tags="gabinet_info"
                )

                # 🔽 status aktywnego pacjenta (pod kolejką)
                aktywny = f"1 w gabinecie: {pacjent.id}" if gabinet.get_aktywny() else "pusto"
                self.canvas.create_text(
                    gabinet.x, gabinet.y - 35,
                    text=aktywny,
                    font=("Arial", 8),
                    fill="gray",
                    tags="gabinet_info"
                )

            for idx, oddzial in enumerate(self.oddzialy.values()):
                nazwa = oddzial.nazwa

                # łóżka i zajętość
                for i, pacjent in enumerate(oddzial.lozka):
                    rect_id = self.lozka_rects[(nazwa, i)]
                    color = pacjent.color if pacjent else "green"
                    self.canvas.itemconfig(rect_id, fill=color)

                    # sprawdzenie zgonu przed dalszym przetwarzaniem
                    if self.sprawdz_zgon(pacjent, oddzial):
                        continue

                    if pacjent:
                        # 2. Sprawdź zgon jako pierwszy (po zmianach!)
                        if self.sprawdz_zgon(pacjent, oddzial):
                            continue

                        # 3. Sprawdź wypis
                        # if pacjent.krytycznosc >= 250: # stan sie polepszyl
                        #     pacjent.status = "Wypisany"
                        #     self.wypisani.append(pacjent)
                        #     oddzial.zwolnij_lozko(pacjent)
                        #     continue

                        # Sprawdź, czy pacjent nie zmarł
                        if pacjent.krytycznosc <= 0:
                            pacjent.status = "Zmarł"
                            self.zmarli.append(pacjent)
                            oddzial.zwolnij_lozko(pacjent)
                            continue

                        # Polepsz stan pacjenta kiedy jest na łóżku
                        if pacjent:
                            self.popraw_krytycznosc(pacjent,0.1)  # poprawa krytyczności co tick

                        # Nagle pogorszenie stanu pacjenta
                        if random.random() < 0.01:
                            pacjent.krytycznosc -= 50
                            if pacjent.krytycznosc < 0:
                                pacjent.krytycznosc = 0
                            print(f"⚠️ NAGŁE POGORSZENIE: Pacjent {pacjent.id} pogorszył się o 50 punktów!")

                        # 4. Podawanie leków
                        for lek_nazwa, info in pacjent.leki.items():
                            czest = info["czestotliwosc"]
                            ostatni = info["ostatnio"]

                            if self.symulowany_czas - ostatni >= czest * 60:
                                pacjent.historia["leki_przyjete"][lek_nazwa] = pacjent.historia["leki_przyjete"].get(
                                    lek_nazwa, 0) + 1
                                if lek_nazwa in self.leki:
                                    if self.leki[lek_nazwa].zuzyj():
                                        pacjent.leki[lek_nazwa]["ostatnio"] = self.symulowany_czas
                                        self.popraw_krytycznosc(pacjent, random.randint(10,50))  # poprawa krytyczności po podaniu leku
                                        print(f"💊 Pacjent {pacjent.id} poprawił stan po {lek_nazwa}")

# Statystyki ---------------------------------------------------------------------------------------
                                        self.statystyki["leki"][lek_nazwa] += 1

                                    else:
                                        pacjent.krytycznosc -= 10  # zmniejszenie krytyczności przy braku leku
                                        if random.random() < 0.1:
                                            # losowe podanie leku
                                            if random.random() < 0.1:
                                                losowy_lek = random.choice(list(self.leki.keys()))
                                                print(
                                                    f"⚠️ Błędne podanie: Pacjent {pacjent.id} dostał {losowy_lek} poza harmonogramem")
                                                self.leki[losowy_lek].zuzyj()
                                            # Skrócenie czasu pobytu o 10% po podaniu leku
                                            # if random.random() < 0.2:
                                            #     zmiana = int(pacjent.czas_na_odziale * 0.1)
                                            #     pacjent.czas_na_odziale -= zmiana
                                            #     print(f"⏱️ Pacjent {pacjent.id} skrócił czas pobytu o {zmiana} minut")

                        # # Losowe dodanie badania
                        if random.random() < 0.02:  # niska szansa co tick
                            dostepne = list(set(BADANIA) - set(pacjent.badania_do_wykonania))
                            if dostepne:
                                nowe_badanie = random.choice(dostepne)
                                pacjent.badania_do_wykonania.append(nowe_badanie)
                                with pacjent.lock:
                                    if not pacjent.w_trakcie_badania:
                                        self.gabinety_badan[nowe_badanie].dodaj_pacjenta(pacjent)
                                        pacjent.w_trakcie_badania= True
                                        print(f"🧪 Pacjent {pacjent.id} (łóżko) dostał nowe badanie: {nowe_badanie}")

                        # 5. Rysowanie
                        lx, ly = self.lozka_graficzne[(nazwa, i)]
                        pacjent.move_to(lx, ly)

                # Rysuj pacjentów oczekujących na łóżko pod łóżkami
                for j, pacjent in enumerate(list(oddzial.kolejka.queue)):
                    if pacjent is None or pacjent.status == "Zmarł":
                        continue
                    x = 100 + idx * 250 + (j % 3) * 40  # 3 pacjentów w rzędzie, odstęp 40
                    y = 235 + (j // 3) * 20  # każdy rząd niżej o 20px
                    pacjent.move_to(x, y)
                    self.obniz_krytycznosc(pacjent, 0.2)  # zmniejszenie stabilnosci co tick

                # pacjenci gotowi po konsultacji -> łóżka
                for lekarz in oddzial.lekarze:
                    while lekarz.gotowi:
                        pacjent = lekarz.gotowi.pop(0)
                        if pacjent.badania_do_wykonania:
                            pierwsze = pacjent.badania_do_wykonania[0]
                            self.gabinety_badan[pierwsze].dodaj_pacjenta(pacjent)
                        else:
                            oddzial.zakwateruj_po_konsultacji(pacjent)

                for lekarz in oddzial.lekarze:
                    pacjent = lekarz.get_pacjent()
                    if pacjent:
                        pacjent.move_to(lekarz.x + 7, lekarz.y + 15)  # pacjent w gabinecie

                    for j, p in enumerate(lekarz.get_kolejka()):
                        if pacjent is None or pacjent.status == "Zmarł":
                            continue
                        p.move_to(lekarz.x + 45 + j * 20, lekarz.y - 10)  # kolejka z prawej strony gabinetu
                        self.obniz_krytycznosc(p, 0.2)  # zmniejszenie krytyczności co tick

                    # pacjenci wracający na łóżko po badaniu
                for pacjent in self.pacjenci:
                    if self.sprawdz_zgon(pacjent, self.oddzialy.get(pacjent.oddzial_docelowy)):
                        continue
                    if self.sprawdz_wypis(pacjent, self.oddzialy.get(pacjent.oddzial_docelowy)):
                        continue

                    if pacjent.status == "Powrót na łóżko" and pacjent.czy_ma_lozko and pacjent.index_lozka is not None:
                        for oddzial in self.oddzialy.values():
                            if any(pacjent == p for p in oddzial.lozka if p is not None):
                                break
                        else:
                            # pacjent nie leży (np. po badaniu) – przywróć na swoje łóżko
                            for oddzial in self.oddzialy.values():
                                for i, lozko in enumerate(oddzial.lozka):
                                    if lozko is None and i == pacjent.index_lozka:
                                        oddzial.lozka[i] = pacjent
                                        pacjent.status = f"{oddzial.nazwa} - łóżko {i + 1}"
                                        break
                    elif pacjent.status == "Powrót na łóżko" and not pacjent.czy_ma_lozko:
                        # pacjent nie miał łóżka – zakwateruj po badaniach
                        for oddzial in self.oddzialy.values():
                            if pacjent not in oddzial.kolejka.queue and pacjent not in oddzial.lozka:
                                oddzial.zakwateruj_po_konsultacji(pacjent)
                                break

            # Zakwateruj pacjentów z kolejki, jeśli są wolne łóżka
            with oddzial.lock:
                for i in range(len(oddzial.lozka)):
                    if oddzial.lozka[i] is None and not oddzial.kolejka.empty():
                        nowy = oddzial.kolejka.get()
                        oddzial.lozka[i] = nowy
                        nowy.status = f"{oddzial.nazwa} - łóżko {i + 1}"
                        nowy.czy_ma_lozko = True
                        nowy.index_lozka = i
                        nowy.leki = {}

                        # przypisz leki jak przy pierwszym zakwaterowaniu
                        for lek_nazwa in random.sample(list(self.leki.keys()), random.randint(1, 4)):
                            czestotliwosc = random.choice([8, 12, 24])
                            nowy.leki[lek_nazwa] = {
                                "czestotliwosc": czestotliwosc,
                                "ostatnio": self.symulowany_czas
                            }

            for lekarze_list in self.lekarze.values():
                for lekarz in lekarze_list:
                    if not lekarz.w_pracy:
                        kolor_gabinetu = "gray"
                    elif lekarz.w_gabinecie:
                        kolor_gabinetu = "lightgreen"
                    else:
                        kolor_gabinetu = "lightcoral"

                    self.canvas.itemconfig(lekarz.rect_id, fill=kolor_gabinetu)

            # Rysowanie wypisanych pacjentów
            for i, pacjent in enumerate(self.wypisani):
                x = 1550 + (i % 7) * 20
                y = 770 + (i // 7) * 35

                # ❌ Ukryj kółko i etykietę pacjenta
                self.canvas.itemconfig(pacjent.oval, state="hidden")
                self.canvas.itemconfig(pacjent.label, state="hidden")

                # ✅ Zamiast tego narysuj tylko tekst "id |"
                self.canvas.create_text(
                    x, y,
                    text=f"{pacjent.id} |",
                    font=("Arial", 10),
                    anchor="nw",
                    fill="black",
                    tags="wypisani_info"
                )

            # Rysowanie zmarłych pacjentów
            # Rysowanie zmarłych pacjentów
            for i, pacjent in enumerate(self.zmarli):
                x = 1750 + (i % 7) * 20
                y = 770 + (i // 7) * 35

                self.canvas.itemconfig(pacjent.oval, state="hidden")
                self.canvas.itemconfig(pacjent.label, state="hidden")

                self.canvas.create_text(
                    x, y,
                    text=f"{pacjent.id} |",
                    font=("Arial", 10),
                    anchor="nw",
                    fill="black",
                    tags="zmarli_info"
                )

            # AKTUALIZACJA CZASU
            self.symulacja_tick += 1
            if self.symulacja_tick >= 10:
                self.symulowany_czas += 60
                self.symulacja_tick = 0

            # 🧪 Stan leków – GUI
            self.canvas.delete("leki_info")  # 👈 USUŃ stare etykiety przed rysowaniem nowych

            for i, (nazwa, lek) in enumerate(self.leki.items()):
                kolor = "orange" if lek.ilosc < lek.prog_minimalny else "black"
                kolor = "red" if lek.ilosc <= 0 else kolor
                self.canvas.create_text(
                    1600, 60 + i * 15,
                    text=f"{nazwa}: {lek.ilosc} szt.",
                    font=("Arial", 8),
                    anchor="nw",
                    fill=kolor,
                    tags="leki_info"
                )

            # ⏱️ NIE KOŃCZ SYMULACJI AUTOMATYCZNIE!
            self.canvas.after(100, self.update_gui)
        except Exception as e:
            print(f"Błąd aktualizacji GUI: {e}")
            traceback.print_exc()
            self.canvas.after(100, self.update_gui)

    def zapisz_statystyki_csv(self):
        dzien = self.symulowany_czas // 1440
        nowi = self.statystyki["nowi_pacjenci_dzienni"][dzien] if dzien < len(
            self.statystyki["nowi_pacjenci_dzienni"]) else [0, 0, 0]
        krytyczni, sredni, leccy = nowi

        sr_izba = średnia(self.statystyki["średni_czas_w_izbie"])
        sr_ocz = średnia(self.statystyki["średni_czas_ocz_na_lozko"])
        sr_szpital = średnia(self.statystyki["średni_czas_w_szpitalu"])
        suma_lekow = sum(self.statystyki["leki"].values())
        badania_str = "; ".join(f"{nazwa}: {liczba}" for nazwa, liczba in self.statystyki["badania"].items())
        with open(self.csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)  # ← tutaj tworzysz writer

            writer.writerow([
                dzien,
                krytyczni, sredni, leccy,
                self.statystyki["zgonów"],
                self.statystyki["wypisani"],
                sr_izba,
                sr_ocz,
                sr_szpital,
                suma_lekow,
                badania_str
            ])

        with open(self.csv_oddzialy_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            for nazwa, oddzial in self.oddzialy.items():
                liczba_lozek = len(oddzial.lozka)
                zajete_lozka = sum(1 for p in oddzial.lozka if p is not None)
                procent_zapelnienia = round((zajete_lozka / liczba_lozek) * 100, 2) if liczba_lozek else 0

                przyjeci = sum(1 for p in self.pacjenci
                               if p.oddzial_docelowy == nazwa and
                               p.historia["czas_przyjecia_na_oddzial"] // 1440 == dzien-1)

                zgony = sum(1 for p in self.zmarli
                            if p.oddzial_docelowy == nazwa and
                            p.historia["czas_przyjecia_na_oddzial"] // 1440 == dzien-1)

                # Statystyki dla "Izba Przyjęć" – pacjenci bez oddziału
                zgony_izba = sum(1 for p in self.zmarli
                                 if p.oddzial_docelowy is None and
                                 p.historia.get("czas_przyjecia_na_oddzial", 0) == 0 and
                                 p.historia["czas_przybycia"] // 1440 == dzien - 1)

                badania_izba = sum(1 for p in self.pacjenci
                                   if p.oddzial_docelowy is None and
                                   any(p.historia["badania"]) and
                                   p.historia["czas_przybycia"] // 1440 == dzien - 1)

                writer.writerow([
                    dzien, "Izba Przyjęć",  # oddział
                    0,  # pacjenci_przyjeci
                    zgony_izba,  # zgony
                    0,  # wypisy
                    0,  # badania
                    0,  # % zapełnienia łóżek
                    0  # pacjenci_na_lekarza
                ])
                print("XXXXXXXXXXXXXXXXXXX")
                for p in self.zmarli:
                    print(f"Pacjent {p.id} zmarł na oddziale {p.oddzial_docelowy} w dniu {p.historia['czas_przyjecia_na_oddzial'] // 1440 + 1}")

                wypisy = sum(1 for p in self.wypisani
                             if p.oddzial_docelowy == nazwa and
                             p.historia["czas_przyjecia_na_oddzial"] // 1440 == dzien-1)


                badania = sum(1 for p in self.pacjenci
                              if p.oddzial_docelowy == nazwa and
                              any(b for b in p.historia["badania"])
                              and p.historia["czas_przyjecia_na_oddzial"] // 1440 == dzien-1)

                liczba_pacjentow = sum(1 for p in self.pacjenci
                                       if p.oddzial_docelowy == nazwa)
                liczba_lekarzy = len(self.lekarze[nazwa]) if nazwa in self.lekarze else 1
                pacjenci_na_lekarza = round(liczba_pacjentow / liczba_lekarzy, 2) if liczba_lekarzy else 0

                writer.writerow([
                    dzien, nazwa, przyjeci, zgony, wypisy, badania,
                    procent_zapelnienia, pacjenci_na_lekarza
                ])

    def zakoncz_program(self):
        for p in self.pielegniarki:
            p.zatrzymaj()
        for lekarze_list in self.lekarze.values():
            for l in lekarze_list:
                l.zatrzymaj()
        for d in self.diagności:
            d.zatrzymaj()
        self.root.destroy()
        sys.exit()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Szpital – symulacja")
    app = Symulacja(root)
    root.mainloop()