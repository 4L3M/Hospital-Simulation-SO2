import tkinter as tk
import random
import threading
import time
from queue import Queue
import sys

PACJENTÓW = 10
ODDZIALY = ["Chirurgia", "Interna", "Ortopedia"]
KOLORY = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]
BADANIA = ["RTG", "USG", "EKG", "KREW"]
P_BADANIA = 0.7

class Pacjent:
    def __init__(self, id, canvas):
        self.id = id
        self.status = "Izba"
        self.oddzial_docelowy = None
        self.badania_do_wykonania = []
        if random.random() < P_BADANIA:
            ile = random.randint(1, 2)
            self.badania_do_wykonania = random.sample(BADANIA, ile)
        else:
            self.badania_do_wykonania = []
        self.czy_ma_lozko = False
        self.index_lozka = None

        self.canvas = canvas
        self.color = KOLORY[id % len(KOLORY)]
        self.x, self.y = 0, 0
        self.czas_na_odziale = random.randint(150, 200)
        self.oval = canvas.create_oval(self.x, self.y, self.x + 15, self.y + 15, fill=self.color)
        print(f"Pacjent {self.id} ({self.status}) - badania: {self.badania_do_wykonania}, czas na oddziale: {self.czas_na_odziale}")

    def move_to(self, x, y):
        dx, dy = x - self.x, y - self.y
        self.canvas.move(self.oval, dx, dy)
        self.x, self.y = x, y


class Lekarz(threading.Thread):
    def __init__(self, nazwa_oddzialu, x, y, canvas):
        super().__init__()
        self.nazwa = nazwa_oddzialu
        self.x = x
        self.y = y
        self.canvas = canvas
        self.kolejka = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.pacjent = None
        self.gotowi = []

    def skonsultuj(self, pacjent):
        with self.lock:
            self.kolejka.append(pacjent)

    def run(self):
        while not self.stop_event.is_set():
            with self.lock:
                if self.kolejka:
                    pacjent = self.kolejka.pop(0)
                else:
                    pacjent = None
            if pacjent:
                with self.lock:
                    self.pacjent = pacjent
                    pacjent.status = f"Konsultacja {self.nazwa}"
                time.sleep(random.uniform(2, 4))
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
    def __init__(self, nazwa, ilosc_lozek, lekarz):
        self.nazwa = nazwa
        self.lozka = [None for _ in range(ilosc_lozek)]
        self.kolejka = Queue()
        self.lock = threading.Lock()
        self.lekarz = lekarz

    def przyjmij_pacjenta(self, pacjent):
        self.lekarz.skonsultuj(pacjent)

    def zakwateruj_po_konsultacji(self, pacjent):
        with self.lock:
            for i in range(len(self.lozka)):
                if self.lozka[i] is None:
                    self.lozka[i] = pacjent
                    pacjent.status = f"{self.nazwa} - łóżko {i + 1}"
                    pacjent.czy_ma_lozko = True
                    pacjent.index_lozka = i
                    return True
            self.kolejka.put(pacjent)
            pacjent.status = f"{self.nazwa} (oczekuje)"
            return False

    def zwolnij_lozko(self, pacjent):
        with self.lock:
            for i in range(len(self.lozka)):
                if self.lozka[i] == pacjent:
                    self.lozka[i] = None
                    break
            if not self.kolejka.empty():
                nowy = self.kolejka.get()
                self.lozka[i] = nowy
                nowy.status = f"{self.nazwa} - łóżko {i + 1}"

class GabinetBadania:
    def __init__(self, nazwa, x, y, canvas):
        self.nazwa = nazwa
        self.kolejka = Queue()
        self.x = x
        self.y = y
        self.canvas = canvas
        self.aktywny_pacjent = None
        self.lock = threading.Lock()

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
    def __init__(self, gabinet, oddzialy):
        super().__init__()
        self.gabinet = gabinet
        self.oddzialy = oddzialy
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                pacjent = self.gabinet.kolejka.get(timeout=1)
                self.gabinet.set_aktywny(pacjent)
                pacjent.status = f"Badanie: {self.gabinet.nazwa}"
                time.sleep(random.uniform(3, 5))  # czas badania
                pacjent.badania_do_wykonania.remove(self.gabinet.nazwa)

                if pacjent.czy_ma_lozko:
                    pacjent.status = "Powrót na łóżko"
                    oddzial = self.oddzialy[pacjent.status.split()[0]]
                    # wróci automatycznie w update_gui
                elif not pacjent.badania_do_wykonania:
                    # pacjent nie ma więcej badań i nie ma łóżka → zakwateruj
                    for oddzial in self.oddzialy.values():
                        oddzial = self.oddzialy[pacjent.oddzial_docelowy]
                        if oddzial:
                            if pacjent in oddzial.lekarz.gotowi:
                                oddzial.lekarz.gotowi.remove(pacjent)
                            if oddzial.zakwateruj_po_konsultacji(pacjent):
                                pacjent.czy_ma_lozko = True
                                pacjent.index_lozka = oddzial.lozka.index(pacjent)
                            else:
                                break  # pacjent już w kolejce oczekujących
                else:
                    # kieruj dalej na kolejne badania
                    kolejny = pacjent.badania_do_wykonania[0]
                    app.gabinety_badan[kolejny].dodaj_pacjenta(pacjent)
                self.gabinet.set_aktywny(None)
            except:
                continue

    def zatrzymaj(self):
        self.stop_event.set()


class Pielegniarka(threading.Thread):
    def __init__(self, id, x, y, canvas, oddzialy, kolejka_wejsciowa):
        super().__init__()
        self.id = id
        self.x = x
        self.y = y
        self.canvas = canvas
        self.oddzialy = oddzialy
        self.kolejka = kolejka_wejsciowa
        self.pacjent = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

    def run(self):
        while not self.stop_event.is_set():
            try:
                pacjent = self.kolejka.get(timeout=1)
                with self.lock:
                    self.pacjent = pacjent
                    pacjent.status = f"Pielęgniarka {self.id + 1}"
                time.sleep(random.uniform(2, 4))
                oddzial_obj = random.choice(list(self.oddzialy.values()))
                pacjent.status = f"Oddział {oddzial_obj.nazwa}"
                pacjent.oddzial_docelowy = oddzial_obj.nazwa
                oddzial_obj.przyjmij_pacjenta(pacjent)
                with self.lock:
                    self.pacjent = None
            except:
                continue

    def zatrzymaj(self):
        self.stop_event.set()

    def get_pacjent(self):
        with self.lock:
            return self.pacjent


class Symulacja:
    def __init__(self, root):
        self.canvas = tk.Canvas(root, width=1100, height=600, bg='white')
        self.canvas.pack()
        self.root = root
        root.protocol("WM_DELETE_WINDOW", self.zakoncz_program)

        self.pacjenci = [Pacjent(i, self.canvas) for i in range(PACJENTÓW)]
        self.kolejka_wejsciowa = Queue()
        for pacjent in self.pacjenci:
            self.kolejka_wejsciowa.put(pacjent)

        self.lekarze = {
            nazwa: Lekarz(nazwa, 100 + i * 250, 300, self.canvas)
            for i, nazwa in enumerate(ODDZIALY)
        }
        for l in self.lekarze.values():
            l.start()

        self.oddzialy = {
            nazwa: Oddzial(nazwa, ilosc_lozek=3, lekarz=self.lekarze[nazwa])
            for nazwa in ODDZIALY
        }

        self.gabinety_badan = {
            nazwa: GabinetBadania(nazwa, 600 + i * 120, 100, self.canvas)
            for i, nazwa in enumerate(BADANIA)
        }

        self.diagności = []
        for gabinet in self.gabinety_badan.values():
            diagnosta = LekarzDiagnosta(gabinet, self.oddzialy)
            diagnosta.start()
            self.diagności.append(diagnosta)


        self.wypisani = []

        self.pielegniarki = [
            Pielegniarka(0, 150, 100, self.canvas, self.oddzialy, self.kolejka_wejsciowa),
            Pielegniarka(1, 300, 100, self.canvas, self.oddzialy, self.kolejka_wejsciowa)
        ]
        for p in self.pielegniarki:
            p.start()

        self.draw_labels()
        self.lozka_graficzne = {}
        self.lozka_rects = {}
        self.rysuj_lozka()
        self.update_gui()

    def draw_labels(self):
        self.canvas.create_text(100, 30, text="Izba Przyjęć", font=("Arial", 10))
        for i, nazwa in enumerate(ODDZIALY):
            self.canvas.create_text(100 + i * 250, 200, text=f"Oddział {nazwa}", font=("Arial", 10))
            self.canvas.create_text(100 + i * 250, 280, text=f"Lekarz {nazwa}", font=("Arial", 9))
        self.canvas.create_text(950, 50, text="Wypisani", font=("Arial", 10))
        self.canvas.create_text(150, 80, text="Pielęgniarka 1", font=("Arial", 10))
        self.canvas.create_text(300, 80, text="Pielęgniarka 2", font=("Arial", 10))
        for i, nazwa in enumerate(BADANIA):
            self.canvas.create_text(600 + i * 120, 80, text=f"GABINET {nazwa}", font=("Arial", 9))


    def rysuj_lozka(self):
        for idx, (nazwa, oddzial) in enumerate(self.oddzialy.items()):
            for i in range(len(oddzial.lozka)):
                lx = 100 + idx * 250 + i * 40
                ly = 210
                rect = self.canvas.create_rectangle(lx, ly, lx + 30, ly + 20, outline="black")
                label = self.canvas.create_text(lx + 15, ly + 10, text=f"L{i + 1}", font=("Arial", 7))
                self.lozka_graficzne[(nazwa, i)] = (lx + 7, ly + 2)
                self.lozka_rects[(nazwa, i)] = rect

    def update_gui(self):
        for i, pacjent in enumerate(list(self.kolejka_wejsciowa.queue)):
            pacjent.move_to(50 + i * 20, 50)

        for pielegniarka in self.pielegniarki:
            pacjent = pielegniarka.get_pacjent()
            if pacjent:
                pacjent.move_to(pielegniarka.x, pielegniarka.y)

        for gabinet in self.gabinety_badan.values():
            pacjent = gabinet.get_aktywny()
            if pacjent:
                pacjent.move_to(gabinet.x, gabinet.y)

            for j, p in enumerate(gabinet.get_kolejka()):
                p.move_to(gabinet.x + j * 15, gabinet.y + 30)


        for idx, oddzial in enumerate(self.oddzialy.values()):
            nazwa = oddzial.nazwa

            # łóżka i zajętość
            for i, pacjent in enumerate(oddzial.lozka):
                rect_id = self.lozka_rects[(nazwa, i)]
                color = pacjent.color if pacjent else "green"
                self.canvas.itemconfig(rect_id, fill=color)
                if pacjent:
                    lx, ly = self.lozka_graficzne[(nazwa, i)]
                    pacjent.move_to(lx, ly)
                    pacjent.czas_na_odziale -= 1
                    if pacjent.czas_na_odziale <= 0:
                        pacjent.status = "Wypisany"
                        self.wypisani.append(pacjent)
                        oddzial.zwolnij_lozko(pacjent)

            # pacjenci gotowi po konsultacji -> łóżka
            while oddzial.lekarz.gotowi:
                pacjent = oddzial.lekarz.gotowi.pop(0)
                if pacjent.badania_do_wykonania:
                    pierwsze = pacjent.badania_do_wykonania[0]
                    self.gabinety_badan[pierwsze].dodaj_pacjenta(pacjent)
                else:
                    oddzial.zakwateruj_po_konsultacji(pacjent)

            # pacjenci w gabinecie
            pacjent = oddzial.lekarz.get_pacjent()
            if pacjent:
                pacjent.move_to(oddzial.lekarz.x, oddzial.lekarz.y)

            # kolejka do gabinetu (pod gabinetem)
            for j, pacjent in enumerate(oddzial.lekarz.get_kolejka()):
                pacjent.move_to(oddzial.lekarz.x + j * 20, oddzial.lekarz.y + 25)

            # kolejka do łóżek (nad łóżkami)
            for j, pacjent in enumerate(list(oddzial.kolejka.queue)):
                pacjent.move_to(100 + idx * 250 + j * 20, 240)

                # pacjenci wracający na łóżko po badaniu
        for pacjent in self.pacjenci:
            if pacjent.status == "Powrót na łóżko" and pacjent.czy_ma_lozko and pacjent.index_lozka is not None:
                for oddzial in self.oddzialy.values():
                    if pacjent in oddzial.lozka:
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


        for i, pacjent in enumerate(self.wypisani):
            x = 950 + (i % 5) * 20
            y = 70 + (i // 5) * 20
            pacjent.move_to(x, y)

        if len(self.wypisani) < PACJENTÓW:
            self.canvas.after(100, self.update_gui)
        else:
            self.zakoncz_program()

    def zakoncz_program(self):
        for p in self.pielegniarki:
            p.zatrzymaj()
        for l in self.lekarze.values():
            l.zatrzymaj()
        for d in self.diagności:
            d.zatrzymaj()
        self.root.destroy()
        sys.exit()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Symulacja pacjentów w szpitalu – kolejki do lekarza i łóżek")
    app = Symulacja(root)
    root.mainloop()           