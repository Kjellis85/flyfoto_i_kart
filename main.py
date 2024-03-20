# main.py

import math
from nb_api_functions import search_nb_images, save_to_excel, add_coordinates_to_table


def main():
    search_term = input('Skriv inn søkeord: ')
    total_treff_input = input('Hvor mange treff ønsker du totalt? (Skriv et tall): ')
    total_treff = int(total_treff_input)

    # Beregn antall sider basert på antall treff, avrundet opp til nærmeste hundre
    max_sider = math.ceil(total_treff / 100)

    df = search_nb_images(search_term, max_pages=max_sider)

    if df is not None and not df.empty:
        # Kjør funksjonen for å legge til koordinater
        df = add_coordinates_to_table(df)
        # print(df.iloc[0])  # Skriv ut den første raden i DataFrame
        excel_filename = input('Skriv inn ønsket navn på Excel-filen (uten filendelse): ')
        save_to_excel(df, excel_filename)
    else:
        print("Ingen resultater med geografisk informasjon funnet.")


if __name__ == '__main__':
    main()