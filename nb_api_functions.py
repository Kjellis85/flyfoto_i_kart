# nb_api_functions.py

import requests
import pandas as pd
import urllib.parse



def search_nb_images(search_term, page_size=100, max_pages=None):
    api_url = 'https://api.nb.no/catalog/v1/items'
    all_data = []
    current_page = 0

    while True:
        if max_pages is not None and current_page >= max_pages:
            break

        params = {
            'q': search_term,
            'filter': 'mediatype:bilder',
            'size': page_size,
            'page': current_page
        }
        response = requests.get(api_url, params=params)
        if response.status_code == 200:
            results = response.json()
            for item in results['_embedded']['items']:
                geographics = item['metadata'].get('subject', {}).get('geographics')
                if geographics:
                    geographic_parts = geographics[0].split(';')
                    # Filtrer ut "Norge" eller "null" fra geografisk informasjon
                    geographic_parts = [part for part in geographic_parts if part.lower() not in ('norge', 'null')]
                    if len(geographic_parts) >= 3:
                        # Fjern "Land" og behandle resten av geografisk informasjon
                        fylke = geographic_parts[1]
                        kommune = geographic_parts[2]
                        steder = geographic_parts[3:]
                        thumbnail_custom = item['_links'].get('thumbnail_custom', {}).get('href')
                        if thumbnail_custom:  # Sjekk om thumbnail_custom er None
                            thumbnail_custom = thumbnail_custom.replace('{width},{height}', 'full')
                        title = item['metadata'].get('title')
                        all_data.append({
                            'thumbnail_custom': thumbnail_custom,
                            'title': title,
                            'Fylke': fylke,
                            'Kommune': kommune,
                            'Steder': ', '.join(steder), # Konverter liste til streng
                            'geographics': geographics[0] if geographics else None
                        })
            if current_page >= results['page']['totalPages'] - 1:
                break
            current_page += 1
        else:
            print(f'Error: {response.status_code}')
            break

    df = pd.DataFrame(all_data)

    geo_df = df['geographics'].str.split('[;:,?&]', expand=True)
    df['Fylke'] = geo_df[1].str.strip() if geo_df.shape[1] > 1 else None
    df['Kommune'] = geo_df[2].str.strip() if geo_df.shape[1] > 2 else None

    # Resten av strengen etter 'Kommune' vil være de individuelle stedene
    # Vi samler disse i en egen kolonne for videre splitting
    df['Steder'] = geo_df.loc[:, 3:].apply(lambda x: ','.join(x.dropna().astype(str)), axis=1)

    # Splitte 'Steder'-kolonnen ved komma for å få de individuelle 'Sted_'-kolonnene
    steder_df = df['Steder'].str.split('[;:,?&]', expand=True)
    for i in range(steder_df.shape[1]):
        df[f'Sted_{i + 1}'] = steder_df[i].str.strip()

    # Fjerne midlertidige kolonner som ikke lenger er nødvendige
    df.drop(['geographics', 'Steder'], axis=1, inplace=True)

    return df


def save_to_excel(df, filename):
    if not filename.endswith('.xlsx'):
        filename += '.xlsx'
    df.to_excel(filename, index=False)
    #print(f'Data lagret til {filename}')


# Funksjon for å bygge API-parametere basert på tilgjengelige kolonner
def build_api_params(row):
    # Start fra den siste utfylte kolonnen og jobb deg bakover
    search_columns = ['Sted_5', 'Sted_4', 'Sted_3', 'Sted_2','Sted_1', 'Kommune', 'Fylke']
    for col in search_columns:
        if col in row and pd.notnull(row[col]) and row[col].strip():
            search_term = row[col].strip()
            if 1 <= len(search_term) <= 100:  # Sjekk at søkeordet er innenfor gyldig lengde
                return {
                    'sok': search_term,
                    'fuzzy': 'true',  # Hvis du ønsker fuzzy-søk
                    'utkoordsys': '25833',  # Angi ønsket koordinatsystem
                    'treffPerSide': '1',
                    'side': '1'
                }
    return None  # Ingen gyldig søkestreng å sende


def get_coordinates(sok, fuzzy='true', utkoordsys='25833', treffPerSide='1', side='1'):
    base_url = "https://ws.geonorge.no/stedsnavn/v1/sted"
    # Konstruer URL-en manuelt
    full_url = f"{base_url}?sok={sok}&fuzzy={fuzzy}&utkoordsys={utkoordsys}&treffPerSide={treffPerSide}&side={side}"
    try:
        # Send forespørselen direkte med den fullstendige URL-en
        response = requests.get(full_url)
        response.raise_for_status()  # Vil kaste en HTTPError hvis statusen er 4xx eller 5xx
        data = response.json()

        # Sjekk om det er treff i responsen og hent ut koordinatene
        if data['metadata']['totaltAntallTreff'] > 0:
            for sted in data['navn']:  # Iterer gjennom alle treffene
                if 'representasjonspunkt' in sted and sted['representasjonspunkt']:
                    nord = sted['representasjonspunkt']['nord']
                    øst = sted['representasjonspunkt']['øst']
                    return nord, øst  # Returner koordinatene for det første gyldige treffet
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  # HTTP-feil
    except Exception as err:
        print(f"An error occurred: {err}")  # Andre feil
    return None, None  # Returner None hvis det ikke finnes koordinater eller en feil oppstår


# Funksjon for å legge til koordinater i tabellen
def add_coordinates_to_table(df):
    # Legg til nye kolonner for nord og øst koordinater
    df['Nord'] = None
    df['Øst'] = None

    for index, row in df.iterrows():
        params = build_api_params(row)
        if params:  # Sørg for at det er søkeparametere
            nord, øst = get_coordinates(params['sok'])
            df.at[index, 'Nord'] = nord
            df.at[index, 'Øst'] = øst

    return df