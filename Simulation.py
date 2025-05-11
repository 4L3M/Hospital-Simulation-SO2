# Pełna symulacja z pokojami badań, pielęgniarkami, lekarzami i łóżkami

import tkinter as tk
import random
import threading
import time
from queue import Queue
import sys

PACJENTÓW = 10
ODDZIALY = ["Chirurgia", "Interna", "Ortopedia"]
BADANIA = ["USG", "CT", "MRI", "POBRANIE KRWI", "RTG"]
KOLORY = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan"]

class Pacjent:
    def __init__(self, id, canvas):
        self.id = id
        self.status = "Izba"
        self.canvas = canvas
        self.color = KOLORY[id % len(KOLORY)]
        self.x, self.y = 0, 0
        self.czas_na_odziale = random.randint(150, 200)
        self.oval = canvas.create_oval(self.x, self.y, self.x + 15, self.y + 15, fill=self.color)

    def move_to(self, x, y):
        dx, dy = x - self.x, y - self.y
        self.canvas.move(self.oval, dx, dy)
        self.x, self.y = x, y

class PokojBadania(threading.Thread):
    def __init__(self, nazwa, x, y, canvas):
        super().__init__()
        self.nazwa = nazwa
        self.x = x
        self.y = y
        self.canvas = canvas
        self.kolejka = []
        self.lock = threading.Lock()
        self.pacjent = None
        self.stop_event = threading.Event()

    def skieruj_na_badanie(self, pacjent):
        with self.lock:
            self.kolejka.append(pacjent)

    def run(self):
        while not self.stop_event.is_set():
            pacjent = None
            with self.lock:
                if self.kolejka:
                    pacjent = self.kolejka.pop(0)
            if pacjent:
                self.pacjent = pacjent
                pacjent.status = f"Badanie {self.nazwa}"
                time.sleep(random.uniform(2, 4))
                pacjent.status = f"Po badaniu {self.nazwa}"
                self.pacjent = None
            else:
                time.sleep(0.1)

    def zatrzymaj(self):
        self.stop_event.set()

    def get_pacjent(self):
        return self.pacjent

    def get_kolejka(self):
        with self.lock:
            return list(self.kolejka)

class Lekarz(threading.Thread):
    def __init__(self, nazwa_oddzialu, x, y, canvas, symulacja):
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
        self.symulacja = symulacja

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
                if random.random() < 0.3:
                    pokoj = random.choice(list(self.symulacja.pokoje_badan.values()))
                    pokoj.skieruj_na_badanie(pacjent)
                else:
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
        self.canvas = tk.Canvas(root, width=1300, height=650, bg='white')
        self.canvas.pack()
        self.root = root
        root.protocol("WM_DELETE_WINDOW", self.zakoncz_program)

        self.pacjenci = [Pacjent(i, self.canvas) for i in range(PACJENTÓW)]
        self.kolejka_wejsciowa = Queue()
        for pacjent in self.pacjenci:
            self.kolejka_wejsciowa.put(pacjent)

        self.pokoje_badan = {
            nazwa: PokojBadania(nazwa, 80 + i * 240, 580, self.canvas)
            for i, nazwa in enumerate(BADANIA)
        }
        for pokoj in self.pokoje_badan.values():
            pokoj.start()

        self.lekarze = {
            nazwa: Lekarz(nazwa, 100 + i * 250, 300, self.canvas, self)
            for i, nazwa in enumerate(ODDZIALY)
        }
        for l in self.lekarze.values():
            l.start()

        self.oddzialy = {
            nazwa: Oddzial(nazwa, ilosc_lozek=3, lekarz=self.lekarze[nazwa])
            for nazwa in ODDZIALY
        }
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
        self.canvas.create_text(1150, 50, text="Wypisani", font=("Arial", 10))
        for i, nazwa in enumerate(BADANIA):
            self.canvas.create_text(80 + i * 240, 560, text=nazwa, font=("Arial", 9))

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

        for idx, oddzial in enumerate(self.oddzialy.values()):
            nazwa = oddzial.nazwa

            for i, pacjent in enumerate(oddzial.lozka):
                rect_id = self.lozka_rects[(nazwa, i)]
                color = pacjent.color if pacjent else "green"
                self.canvas.itemconfig(rect_id, fill=color)
                if pacjent:
                    lx, ly = self.lozka_graficzne[(nazwa, i)]
                    pacjent.move_to(lx, ly)
                    pacjent.czas_na_odziale -= 1
                    if pacjent.czas_na_odziale == 100 and random.random() < 0.2:
                        pokoj = random.choice(list(self.pokoje_badan.values()))
                        pokoj.skieruj_na_badanie(pacjent)
                    if pacjent.czas_na_odziale <= 0:
                        pacjent.status = "Wypisany"
                        self.wypisani.append(pacjent)
                        oddzial.zwolnij_lozko(pacjent)

            while oddzial.lekarz.gotowi:
                pacjent = oddzial.lekarz.gotowi.pop(0)
                oddzial.zakwateruj_po_konsultacji(pacjent)

            pacjent = oddzial.lekarz.get_pacjent()
            if pacjent:
                pacjent.move_to(oddzial.lekarz.x, oddzial.lekarz.y)

            for j, pacjent in enumerate(oddzial.lekarz.get_kolejka()):
                pacjent.move_to(oddzial.lekarz.x + j * 20, oddzial.lekarz.y + 25)

            for j, pacjent in enumerate(list(oddzial.kolejka.queue)):
                pacjent.move_to(100 + idx * 250 + j * 20, 240)

        for pokoj in self.pokoje_badan.values():
            pacjent = pokoj.get_pacjent()
            if pacjent:
                pacjent.move_to(pokoj.x, pokoj.y)
            for j, p in enumerate(pokoj.get_kolejka()):
                p.move_to(pokoj.x + j * 20, pokoj.y + 25)

        for i, pacjent in enumerate(self.wypisani):
            x = 1150 + (i % 5) * 20
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
        for b in self.pokoje_badan.values():
            b.zatrzymaj()
        self.root.destroy()
        sys.exit()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Symulacja pacjentów z pokojami badań")
    app = Symulacja(root)
    root.mainloop()
