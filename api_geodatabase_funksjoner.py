import os

import arcpy
import pandas as pd
import requests
import numpy as np


# Funksjon for å hente data fra norge i bilder og lage 'stedinfo'-kolonnen
def hent_data_fra_norge_i_bilder(search_term, max_sider):
    base_url = 'https://api.nb.no/catalog/v1/items'
    params = {
        'q': search_term,
        'filter': 'mediatype:bilder',
        'page': 1,
        'size': 100
    }

    data = []
    while True:
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            break  # Avbryt hvis det er en feil med forespørselen

        items = response.json()['_embedded']['items']
        for item in items:
            # Hent ut thumbnail_medium og title
            thumbnail_medium = item['_links'].get('thumbnail_medium', {}).get('href')
            title = item['metadata'].get('title')

            # Hent ut geographic placeString og subject geographics
            place_string = item.get('metadata', {}).get('geographic', {}).get('placeString', '')
            subject_geographics = item.get('metadata', {}).get('subject', {}).get('geographics', [])
            subject_geographics_str = ';'.join(subject_geographics) if subject_geographics else ''

            # Kombiner placeString og subject geographics til stedinfo
            stedinfo = f"{place_string};{subject_geographics_str}".replace(';', ',')

            # Legg til raden i data-listen
            data.append({
                'thumbnail_medium': thumbnail_medium,
                'title': title,
                'stedinfo': stedinfo
            })
        # Sjekk om det er flere sider å hente
        total_pages = response.json()['page']['totalPages']
        if params['page'] >= total_pages or params['page'] >= max_sider:
            break  # Avslutt hvis vi har nådd siste side eller maks antall sider

        # Gå til neste side
        params['page'] += 1

    return pd.DataFrame(data)

# def tilpass_dataframe(df):
#     for col in df.columns:
#         if col.startswith('geo_'):  # Sjekk om kolonnen er en geografisk kolonne
#             # Splitt kolonnen ved ';,' og lag nye kolonner
#             split_data = df[col].str.split(';,', expand=True)
#             for i in range(split_data.shape[1]):
#                 new_col_name = f'{col}_Sted{i + 1}'
#                 df[new_col_name] = split_data[i]
#             df.drop(columns=[col], inplace=True)  # Fjern den opprinnelige geografiske kolonnen
#     return df

def hent_stedsinformasjon(df):
    # Legg til kolonner for hver unik navneobjekttype
    for index, row in df.iterrows():
        # Rens 'stedinfo' for tomme strenger og 'null', og splitt på komma
        stedinfo = row['stedinfo'].replace('null', '').replace('\'', '').split(',')
        stedinfo = [sted.strip() for sted in stedinfo if sted.strip()]  # Fjern tomme strenger og whitespace
        unike_steder = list(set(stedinfo))  # Fjern duplikater

        for sted in unike_steder:
            if sted:  # Sjekk at stedet ikke er en tom streng
                # Definer parametre for API-kallet
                params = {
                    'sok': sted,
                    'fuzzy': 'true',
                    'utkoordsys': '25833',
                    'treffPerSide': '1',
                    'side': '1'
                }
                # Utfør API-kall for hvert sted
                response = requests.get('https://ws.geonorge.no/stedsnavn/v1/sted', params=params)
                if response.status_code == 200:
                    navneobjekter = response.json().get('navn', [])
                    for navneobjekt in navneobjekter:
                        navneobjekttype = navneobjekt.get('navneobjekttype')
                        representasjonspunkt = navneobjekt.get('representasjonspunkt')
                        koordinater = (representasjonspunkt['øst'], representasjonspunkt['nord'])
                        # Opprett en ny kolonne for navneobjekttypen hvis den ikke allerede eksisterer
                        if navneobjekttype not in df:
                            df[navneobjekttype] = None
                        # Lagre representasjonspunktet i den tilsvarende kolonnen
                        df.at[index, navneobjekttype] = koordinater

    return df

def sanitize_name(name):
    # Fjern eller erstatt ugyldige tegn
    name = name.replace(' ', '_')  # Erstatt mellomrom med understrek
    name = ''.join(e for e in name if e.isalnum() or e == '_')  # Fjern spesialtegn bortsett fra understrek
    if name[0].isdigit():
        name = 'fc_' + name  # Legg til prefix hvis navnet starter med et tall
    return name

def opprett_geodatabase(df, gdb_path, hovedtabell_navn, punkt_tabell_prefiks):
    # Definer standardkoordinatene for Norge (eksempelkoordinater, endre til faktiske verdier)
    standard_koordinater_norge = (368304, 7098745)  # Steinkjer kommune, Trøndelag, om lag midt mellom Vakkerlifjellet og Skjækervatnet

    # Sjekk om geodatabasen eksisterer, hvis ikke, opprett den
    if not arcpy.Exists(gdb_path):
        arcpy.CreateFileGDB_management(*os.path.split(gdb_path))

    # Opprett hovedtabellen med tabell_id, tittel og thumbnail
    hovedtabell = os.path.join(gdb_path, sanitize_name(hovedtabell_navn))
    if not arcpy.Exists(hovedtabell):
        arcpy.management.CreateTable(gdb_path, hovedtabell_navn)
        arcpy.management.AddField(hovedtabell, 'tabell_id', 'LONG')
        arcpy.management.AddField(hovedtabell, 'tittel', 'TEXT')
        arcpy.management.AddField(hovedtabell, 'thumbnail', 'TEXT')

    # Legg til data i hovedtabellen
    with arcpy.da.InsertCursor(hovedtabell, ['tabell_id', 'tittel', 'thumbnail']) as cursor:
        for index, row in df.iterrows():
            cursor.insertRow((index, row['title'], row['thumbnail_medium']))

    # Opprett punktfeatures for hver unik navneobjekttype-kolonne
    for navneobjekttype in df.columns:
        if navneobjekttype not in ['title', 'thumbnail_medium', 'stedinfo', 'koordinater']:  # Unngå ikke-geografiske kolonner
            punkt_tabell_navn = sanitize_name(f"{punkt_tabell_prefiks}_{navneobjekttype}")
            punkt_tabell = os.path.join(gdb_path, punkt_tabell_navn)
            if not arcpy.Exists(punkt_tabell):
                arcpy.management.CreateFeatureclass(gdb_path, punkt_tabell_navn, 'POINT', spatial_reference=25833)
                arcpy.management.AddField(punkt_tabell, 'tabell_id', 'LONG')

            # Legg til punktdata i punktfeature-tabellen
            with arcpy.da.InsertCursor(punkt_tabell, ['tabell_id', 'SHAPE@XY']) as cursor:
                for index, row in df.iterrows():
                    koordinater = row.get(navneobjekttype)
                    if koordinater is None and navneobjekttype == 'Nasjon':
                        koordinater = standard_koordinater_norge
                    if koordinater:
                        cursor.insertRow((index, koordinater))
