# Nazwa pliku wejściowego (plik .py z kodem Pythona)
input_file = "Simulation.py"

# Nazwa pliku wyjściowego (plik .txt)
output_file = "kod_z_cudzyslowiami.txt"

with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
    for line in infile:
        line = line.rstrip('\n')                # usuń znak nowej linii z końca
        escaped_line = line.replace('"', '\\"') # zamień " na \"
        outfile.write(f'"{escaped_line}\"\n') # dodaj cudzysłowy + \n i zapisz
