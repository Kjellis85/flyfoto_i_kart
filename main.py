from api_geodatabase_funksjoner import hent_data_fra_norge_i_bilder, hent_stedsinformasjon, opprett_geodatabase

def main():
    search_term = input("Skriv inn søkeord: ")
    max_sider = int(input("Maks antall sider å søke gjennom: "))
    gdb_path = input("Angi filplassering for geodatabasen: ")
    gdb_name = input("Angi navn på geodatabase: ")
    hovedtabell_navn = input("Hva skal hovedtabellen hete? ")
    punkt_tabell_prefiks = input("Hva skal prefikset for punkttabellene hete? ")

    # Første funksjon
    df_bilde = hent_data_fra_norge_i_bilder(search_term, max_sider)
    # print(df_bilde)

    # Andre funksjon (tidligere tredje funksjon)
    df = hent_stedsinformasjon(df_bilde)
    # print(df.iloc[0])

    # Tredje funksjon (tidligere fjerde funksjon)
    # Bygg den fullstendige stien til geodatabasen
    full_gdb_path = f"{gdb_path}\\{gdb_name}.gdb"
    opprett_geodatabase(df, full_gdb_path, hovedtabell_navn, punkt_tabell_prefiks)

    print("Prosessering fullført.")

if __name__ == "__main__":
    main()