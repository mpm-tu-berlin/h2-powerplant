# Loads both the FCEV and EV consumption files, turns them into "whole year" files (only one week per season)
# and sets the weekends to zero.
import pandas as pd

df_ev_1day = pd.read_csv("../fcev_dummy_time_series.csv",
                         parse_dates=True, index_col='datetime').loc['2020-01-01']
df_fcev_1day = pd.read_csv("../ev_equiv_dummy_time_series.csv",
                           parse_dates=True, index_col='datetime').loc['2020-01-01']

# Winterwoche: 1.1. - 7.1.24 (Mo-So)
# Übergang: 1.4. - 7.4.24 (Mo-So)
# Sommer: 1.7. - 7.7.24 (Mo-So)

neue_dfs = []

for mod_df in [df_ev_1day, df_fcev_1day]:

    tage_dfs = []
    for monat in [1,4,7]:
        for tag in range(1,9):
            day = f"2024-{monat:02d}-{tag:02d}"
            # alle werte vom 2020-01-01 selektieren
            df = mod_df.copy(deep=True)
            # 2020-01-01 im index wird ersetzt durch den day
            new_date = pd.Timestamp(day)
            df['datetime'] = pd.to_datetime(df.index)
            df['datetime'] = df['datetime'].apply(lambda x: x.replace(year=2024, month=monat, day=tag))

            # für den 8. tag brauchen wir NUR den 1. Eintrag! (nur wegen geschlossenem intervall)
            if tag == 8:
                df = df.head(1)

            if tag in [6,7]: # Samstag und Sonntag
                df['value'] = 0
            tage_dfs.append(df)


    # concat all the days
    df_concat = pd.concat(tage_dfs)

    neue_dfs.append(df_concat)

# save the columns ('datetime', 'value') to a csv
neue_dfs[0].to_csv("fcev_dummy_time_series_only_weekdays.csv", columns=['datetime', 'value'], index=False)
neue_dfs[1].to_csv("ev_equiv_dummy_time_series_only_weekdays.csv", columns=['datetime', 'value'], index=False)

# Noch DFs für variation der Last auf den FCEV verstellen (Sensitivitätsanalyse)
fcev_mod = neue_dfs[0].copy(deep=True)
fcev_mod["value_orig"] = fcev_mod["value"]

fcev_mod["value"] = fcev_mod["value_orig"] / 3
fcev_mod.to_csv("fcev_equiv_dummy_ts_drittel_bedarf_only_weekdays.csv", columns=['datetime', 'value'], index=False)

fcev_mod["value"] = fcev_mod["value_orig"] / 6
fcev_mod.to_csv("fcev_equiv_dummy_ts_sechstel_bedarf_only_weekdays.csv", columns=['datetime', 'value'], index=False)

fcev_mod["value"] = fcev_mod["value_orig"] / 2
fcev_mod.to_csv("fcev_equiv_dummy_ts_halber_bedarf_only_weekdays.csv", columns=['datetime', 'value'], index=False)

print("alfons")
