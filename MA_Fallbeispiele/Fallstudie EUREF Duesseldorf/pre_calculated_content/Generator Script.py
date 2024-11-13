# Für schnellere Evaluation exportieren wir hier die PV Daten für EUREF als Zeitreihen Files
import json
import os

import pandas as pd

import h2pp.generators
from h2pp.generators import Jahreszeit

# Basic Simulation
# Achtung, geänderte Annahmen, siehe MA.. Vor allem jetzt auch am WE keine Fahrzeugbetankungen mehr..
datapath = os.path.join(os.path.dirname(__file__))
file_path = os.path.join(datapath, "input_dus.json")

with open(file_path) as user_file:
    config_dict = json.load(user_file)

# get from the config_dict in the generators list the generator with the name "Floating PV"
generator_floating_pv = [gen for gen in config_dict['generators'] if gen['name'] == "Floating PV"][0]
generator_autobahn_pv = [gen for gen in config_dict['generators'] if gen['name'] == "Autobahn PV"][0]

consumer_bdew = [consumer for consumer in config_dict['consumers'] if consumer['name'] == "BDEW Consumption EUREF DUS"][0]

for gen_key in ["BDEW_DUS", "FLOATING", "AUTOBAHN"]:
    print("Pre-calculating CSV for", gen_key, "...")
    if gen_key == "FLOATING":
        generator = generator_floating_pv
    elif gen_key == "AUTOBAHN":
        generator = generator_autobahn_pv

    elif gen_key == "BDEW_DUS":
        kundengruppe = consumer_bdew['parameters']['profile']
        annual_consumption = consumer_bdew['parameters']['yearly_consumption']


    if gen_key in ["FLOATING", "AUTOBAHN"]:
        lat = generator['parameters']['latitude']
        lon = generator['parameters']['longitude']
        peakpower = generator['parameters']['peakpower']
        surface_tilt = generator['parameters']['surface_tilt']
        surface_azimuth = generator['parameters']['surface_azimuth']
        pvtechchoice = generator['parameters']['pvtechchoice']

    sim_interval = 15 # Bei PV eigentlich egal aber BDEW hat 15 Min auflösung, deshalb nehmen wir es

    timeserieses = {}
    for jz in ["SOMMER", "UEBERGANG", "WINTER"]:
        jahreszeit = Jahreszeit[jz]

        if gen_key in ["FLOATING", "AUTOBAHN"]:

            generator_ts = h2pp.generators.create_pv_plant_time_series(latitude=lat, longitude=lon,
                                                                       jahreszeit=jahreszeit,
                                                                       peakpower_in_kW=peakpower,
                                                                       # 1.4 MWp, in Anlehnung an zu installierende Leistung EUREF Campus Düsseldorf
                                                                       base_sim_interval_in_min=config_dict['base_sim_interval'],
                                                                       sim_sow=config_dict['sim_start_of_week'],
                                                                       surface_tilt=surface_tilt,
                                                                       surface_azimuth=surface_azimuth,
                                                                       pvtechchoice=pvtechchoice
                                                                       )

            timeserieses[jz] = generator_ts

        elif gen_key == "BDEW_DUS":
            consumer_ts = h2pp.generators.create_bdew_consumption_time_series(kundengruppe=
                                                                                    h2pp.generators.BDEW_Kundengruppe[kundengruppe],
                                                                              jahreszeit=jahreszeit,
                                                                              annual_consumption=annual_consumption,
                                                                              start_of_week=0,  # MÜSSEN files so speichern dass der Weekday zu den values passt; da ich unten Mo->So mache, mach ichs auch hier
                                                                              base_sim_interval_in_min=config_dict['base_sim_interval'])
            timeserieses[jz] = consumer_ts

    # Export to CSV. Every element of the generator_ts is a row with a timestamp starting 2020-01-01 00:00:00. next row 15 minutes later and so on.
    # The first column is the timestamp (name "datetime", the second column is the power in kW ("value").
    # Also, we need to add the first element for each jahreszeit again as the last (8th day at 0:00
    # Need to do it for all the Jahreszeiten: choose year 2024-01-01 to 2024-01-08 for Winter, 2024-04-01 to 2024-04-08 for Uebergang, 2024-07-01 to 2024-07-08 for Sommer.
    # these mentioned weeks are tactically selected so that we have the right weekdays (Mo-So) for each jahreszeit! :)
    # All Jahreszeiten combined in the same CSV!

    all_dfs = []
    for jz in ["SOMMER", "UEBERGANG", "WINTER"]:
        jahreszeit = Jahreszeit[jz]
        ts = timeserieses[jz]

        # Create subfolder "pre_calculated_content_for_euref_duesseldorf"
        export_dir = os.path.join(datapath, "output")
        if not os.path.exists(export_dir):
            os.makedirs(export_dir)

        # create a series containing 2024-01-01 0:00 to 2024-01-08 0:00 (15min intervals)

        # Create a DataFrame with the index as a DatetimeIndex
        if jz == "SOMMER":
            mth = "07"
        elif jz == "UEBERGANG":
            mth = "04"
        elif jz == "WINTER":
            mth = "01"
        df = pd.DataFrame(index=pd.date_range(start=f"2024-{mth}-01 00:00:00", end=f"2024-{mth}-08 00:00:00", freq="15min"))

        # Add the power values from the generator_ts
        df["value"] = ts

        all_dfs.append(df)

    # Concatenate all the DataFrames
    combined_df = pd.concat(all_dfs)

    # Store the combined DataFrame to a CSV file. Index row gets the "datetime" row and value is value.
    combined_df.to_csv(os.path.join(export_dir, f"PV_{gen_key}_combined.csv"), index_label="datetime")


    # Replace it in the Dict: set the new values..
    if gen_key == "FLOATING":
        thename = "Floating PV"
    elif gen_key == "AUTOBAHN":
        thename = "Autobahn PV"
    elif gen_key == "BDEW_DUS":
        thename = "BDEW Consumption EUREF DUS"

    gen_neu = {
        "name": thename,
        "energy_type": "electricity_dc" if gen_key in ["FLOATING", "AUTOBAHN"] else "electricity_ac",
        "calculation_type": "time_series",
        "parameters": {
            "contains": "one_week",
            "file_path": "pre_calculated_content/output/PV_" + gen_key + "_combined.csv",
        }
    }

    if gen_key in ["FLOATING", "AUTOBAHN"]:

        # remove the old generator and add the new one
        config_dict['generators'] = [generator for generator in config_dict['generators'] if
                                    generator.get('name') != thename]

        config_dict['generators'].append(gen_neu)

    elif gen_key == "BDEW_DUS":
        # Remove the old BDEW consumer and add the new one
        config_dict['consumers'] = [consumer for consumer in config_dict['consumers'] if
                                    consumer.get('name') != 'BDEW Consumption EUREF DUS']

        config_dict['consumers'].append(gen_neu)


# Save the new config_dict to a new file
new_file_path = os.path.join(datapath, "__output_precalculated_pv_and_bdew_config_euref_dus.json")
with open(new_file_path, "w") as new_file:
    json.dump(config_dict, new_file, indent=4)


