# nb_api_functions.py

import requests
import pandas as pd


def search_nb_images(search_term, page_size=100, max_results=None):
    api_url = 'https://api.nb.no/catalog/v1/items'
    all_data = []
    current_page = 0
    total_results_fetched = 0

    while True:
        if max_results is not None and total_results_fetched >= max_results:
            break

        params = {
            'q': search_term,
            'filter': 'mediatype:bilder',
            'size': page_size if not max_results else min(page_size, max_results - total_results_fetched),
            'page': current_page
        }
        response = requests.get(api_url, params=params)
        if response.status_code == 200:
            results = response.json()
            for item in results['_embedded']['items']:
                if max_results is not None and total_results_fetched >= max_results:
                    break
                geographics = item['metadata'].get('subject', {}).get('geographics')
                if geographics:
                    thumbnail_custom = item['_links'].get('thumbnail_custom', {}).get('href')
                    if thumbnail_custom:  # Sjekk om thumbnail_custom er None
                        thumbnail_custom = thumbnail_custom.replace('{width},{height}', 'full')
                    title = item['metadata'].get('title')
                    all_data.append({
                        'thumbnail_custom': thumbnail_custom,
                        'title': title,
                        'geographics': geographics[0] if geographics else None
                    })
                    total_results_fetched += 1
            if current_page >= results['page']['totalPages'] - 1:
                break
            else:
                current_page += 1
        else:
            print(f'Error: {response.status_code}')
            break

    df = pd.DataFrame(all_data)

    # Splitte geographics-kolonnen
    geo_df = df['geographics'].str.split('[;:,? &]+', expand=True)
    df['Land'] = geo_df[0]
    df['Fylke'] = geo_df[1]
    df['Kommune'] = geo_df[2]

    # Splitte Kommune-kolonnen videre
    kommune_df = df['Kommune'].str.split('[;:,? &]', expand=True)
    for i in range(kommune_df.shape[1]):
        df[f'Sted_{i + 1}'] = kommune_df[i]


    # Fjerne den opprinnelige geographics-kolonnen
    df.drop('geographics', axis=1, inplace=True)

    return df


def save_to_excel(df, filename):
    if not filename.endswith('.xlsx'):
        filename += '.xlsx'
    df.to_excel(filename, index=False)
    #print(f'Data lagret til {filename}')


# Funksjon for å bygge API-parametere basert på tilgjengelige kolonner
def build_api_params(row):
    # Søk etter kommunenavn først, deretter fylkesnavn, til slutt land
    search_term = None
    if pd.notnull(row['Kommune']) and row['Kommune'].strip():
        search_term = row['Kommune'].strip()
    elif pd.notnull(row['Fylke']) and row['Fylke'].strip():
        search_term = row['Fylke'].strip()
    elif pd.notnull(row['Land']) and row['Land'].strip():
        search_term = row['Land'].strip()

    if search_term and 1 <= len(search_term) <= 100:  # Sjekk at søkeordet er innenfor gyldig lengde
        return {
            'sok': search_term,
            'fuzzy': 'true',  # Hvis du ønsker fuzzy-søk
            'utkoordsys': '25833',# Angi ønsket koordinatsystem
            'treffPerSide': '1',
            'side': '1'
        }
    else:
        return None  # Ingen gyldig søkestreng å sende


def get_coordinates(params):
    if not params:
        return None, None  # Ingen søkeparametere tilgjengelig
    base_url = "https://ws.geonorge.no/stedsnavn/v1/sted"
    try:
        # Forbered forespørselen for å få den fullstendige URL-en
        prepared_request = requests.Request('GET', base_url, params=params).prepare()
        # Skriv ut den fullstendige URL-en
        #print(f"Full URL: {prepared_request.url}")

        # Send forespørselen
        response = requests.Session().send(prepared_request)
        response.raise_for_status()  # Vil kaste en HTTPError hvis statusen er 4xx eller 5xx
        data = response.json()

        # Sjekk om det er treff i responsen og hent ut koordinatene
        if data['metadata']['totaltAntallTreff'] > 0:
            sted = data['navn'][0]  # Anta at vi tar det første treffet
            if 'representasjonspunkt' in sted:
                nord = sted['representasjonspunkt']['nord']
                øst = sted['representasjonspunkt']['øst']
                return nord, øst
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  # HTTP-feil
    except Exception as err:
        print(f"An error occurred: {err}")  # Andre feil
    return None, None


# Funksjon for å legge til koordinater i tabellen
def add_coordinates_to_table(df):
    # Legg til nye kolonner for nord og øst koordinater
    df['Nord'] = None
    df['Øst'] = None

    for index, row in df.iterrows():
        params = build_api_params(row)
        if params:  # Sørg for at det er søkeparametere
            nord, øst = get_coordinates(params)
            df.at[index, 'Nord'] = nord
            df.at[index, 'Øst'] = øst

    return df