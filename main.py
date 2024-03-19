# main.py

from nb_api_functions import search_nb_images, save_to_excel, add_coordinates_to_table

def main():
    search_term = input('Skriv inn søkeord: ')
    max_treff_input = input('Hvor mange treff ønsker du? (Skriv et tall eller "alle" for alle treff): ')
    max_treff = None if max_treff_input.lower() == 'alle' else int(max_treff_input)

    df = search_nb_images(search_term, max_results=max_treff)

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