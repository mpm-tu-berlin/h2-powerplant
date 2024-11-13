import copy
import json
import os
from typing import Literal

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

import h2pp
from h2pp.optimizer import optimize_h2pp


def increase_mean_and_variance_in_netztransparenz_power_price_file(strompreis_file_path, streckungsfaktor,
                                                                   mean_steigerung, output_file):
    """
    Erhöht in einer gegebenen CSV-Datei mit Strompreisen den Mittelwert und die Varianz des 'Spotmarktpreis in ct/kWh'

    """

    # Step 1: Read the CSV file with the correct delimiter and decimal separator
    df = pd.read_csv(strompreis_file_path, delimiter=';', decimal=',')

    # Step 2: Adjust the variance of the 'Spotmarktpreis in ct/kWh' column
    column_name = 'Spotmarktpreis in ct/kWh'
    spotmarktpreis = df[column_name]

    # Center the data by subtracting the mean
    mean_value = np.mean(spotmarktpreis)
    centered_data = spotmarktpreis - mean_value

    # Scale the centered data and add the mean back
    adjusted_data = (centered_data * streckungsfaktor) + mean_value

    # Increase the overall mean
    adjusted_data += mean_steigerung

    # Update the DataFrame with the new values
    df[column_name] = adjusted_data

    # Step 3: Write the adjusted DataFrame back to a new CSV file with the correct format
    df.to_csv(output_file, sep=';', decimal=',', index=False)  # No index, same delimiters and format


def export_jahreszeiten_und_stacked_tco_plot(tco_obj, figs, exp_name, s):
    """
    Die Standard-Plots (welche bei der Optimierung/Hauptalgorithmus generiert werden), abgreifen und abspeichern
    Analog das TCO-Stacked Bar Plot aus dem TCO Objekt generieren
    @param tco_obj: Das TCO Objekt (Ergebnis der Optimierung)
    @param figs: Das figs-dictionary, welches die Plots enthält (Ergebnis der Optimierung)
    @param exp_name: Kürzel für das Experiment (für den Dateiordner beim Abspeichern)
    @param s: Kürzel für das Szenario (für den Dateinamen beim Abspeichern)
    @return:
    """
    create_export_folder(exp_name)

    for fig in figs:
        figs[fig].update_layout(
            title_font_size=15,
            legend_tracegroupgap=105,

            title={
                'x': 0.05,  # Set to 0 for left alignment
                'y': 0.96,  # Set to 1 for top alignment
                'xanchor': 'left',  # Anchor title to the left
                'yanchor': 'top',  # Anchor title to the top
            },

        )

    figs['SOMMER'].write_image(f"Plot_Results_For_MA/{exp_name}/{s}_Sommer.pdf", width=1380, height=580)
    figs['UEBERGANG'].write_image(f"Plot_Results_For_MA/{exp_name}/{s}_Uebergang.pdf", width=1380, height=580)
    figs['WINTER'].write_image(f"Plot_Results_For_MA/{exp_name}/{s}_Winter.pdf", width=1380, height=580)

    tco_norm_plot = tco_obj.plot_stacked_bar_over_period(include_title=False)
    tco_norm_plot.write_image(f"Plot_Results_For_MA/{exp_name}/{s}_TCO_Stacked.pdf", width=1200, height=600)

def create_export_folder(exp_name):
    if not os.path.exists("Plot_Results_For_MA"):
        os.makedirs("Plot_Results_For_MA")

    if not os.path.exists(f"Plot_Results_For_MA/{exp_name}"):
        os.makedirs(f"Plot_Results_For_MA/{exp_name}")

def donut_export(exp_name, list_of_tcos, labels):
    create_export_folder(exp_name)
    donut = h2pp.tco.plot_donut_tco_fractions(
        list_of_tcos,
        labels,
        labels)
    donut.write_image(f"Plot_Results_For_MA/{exp_name}/Donut_Anteile.pdf", width=1200, height=400)

def multiple_tco_costs_and_revenue_bars_export(exp_name, list_of_tcos, labels):
    create_export_folder(exp_name)
    fig1 = h2pp.tco.plot_multiple_tco_costs_and_revenue_bars(list_of_tcos, labels)
    fig1.write_image(f"Plot_Results_For_MA/{exp_name}/Kostenbestandteile_Vergleich.pdf", width=1200, height=600)

def multiple_tco_total_cost_comparison_export(exp_name, list_of_tcos, labels):
    create_export_folder(exp_name)
    fig2 = h2pp.tco.plot_multiple_tco_total_bars(list_of_tcos, labels)
    fig2.write_image(f"Plot_Results_For_MA/{exp_name}/Gesamtkosten_Vergleich.pdf")


def config_dict_ev_change(config_dict, usage_on_weekends):
    """
    Modification is done inplace.
    Exchanges the FCEV demand in an config dict with a BEV demand.
    """
    # Delete the FCEV time series:
    config_dict['consumers'] = [consumer for consumer in config_dict['consumers'] if
                                consumer.get('name') != 'timeseries_fcev']

    # Add new EV
    # Assumption here: Charging the EVs with AC
    config_dict["consumers"].append({
        "name": "BEV_CONSUMPTION",
        "energy_type": "electricity_ac",
        "calculation_type": "time_series",
        "parameters": {
            "contains": "one_day" if usage_on_weekends else "one_week",
            "file_path": "../Common_Data/ev_equiv_dummy_time_series.csv" if usage_on_weekends else "../Common_Data/bev_fcev_without_weekends/ev_equiv_dummy_time_series_only_weekdays.csv"
        }
    })
def switch_fcev_with_ev(input_file_path,
                        output_file_path,
                        usage_on_weekends):
    """
    Load the EV time series to replace the FCEV time series in the config file.
    Output file may not exist or will be overwritten otherwise!!

    usage_on_weekends: True if EVs should be used also at the weekends. False if Saturday/Sunday have no EV consumption.
    :param input_file_path:
    :param output_file_path:
    :return:
    """
    ###  ###

    with open(input_file_path) as user_file:
        config_dict = json.load(user_file)


    config_dict_ev_change(config_dict, usage_on_weekends)

    # User warnen: soll enter drücken, wenn er wirklich überschreiben will und bekommt den filename angezeigt, der überschrieben werden würde.
    if os.path.exists(output_file_path):
        print(f"WARNING: You are about to overwrite the file at {output_file_path}.")
        print("Press Enter to continue.")
        input()

    # Write the modified json back to a new temporary file
    with open(output_file_path, "w") as user_file: # may NOT exist or will be overwritten
        json.dump(config_dict, user_file, indent=4)

    ###


def change_setting_in_json(input_file_path, output_file_name, key, value):
    """
    Load the JSON file, change the value at the given key path and save the modified JSON to a new file.
    Output file may not exist or will be overwritten otherwise!!
    :param input_file_path:
    :param output_file_path:
    :param key_:
    :param value:
    :return:
    """
    with open(input_file_path) as user_file:
        config_dict = json.load(user_file)

    # Delete the FCEV time series:
    config_dict[key] = value

    file_path_out = os.path.join(output_file_name)  # may NOT exist or will be overwritten
    with open(file_path_out, "w") as user_file:
        json.dump(config_dict, user_file, indent=4)


def fuenffach_analyse(datapath, file_path, exp_name, ev_usage_on_weekends=True):
    create_export_folder(exp_name)

    # Prepare EV json
    ev_tempfile_path = os.path.join(datapath,
                                    "TEMPFILE_ONLY__config_5ers_ev.json")  # must be in this folder so that the relative path in the json file still works
    switch_fcev_with_ev(input_file_path=file_path,
                               output_file_path=ev_tempfile_path, usage_on_weekends=ev_usage_on_weekends)

    # ==== 1. Campus + H2PP + FCEV ====
    tco_normal, figs = optimize_h2pp(file_path, mode="normal")
    export_jahreszeiten_und_stacked_tco_plot(tco_normal, figs, exp_name, "H2PP_FCEV")

    # ==== 2. Campus + Battery + FCEV ====
    tco_battery_fcev, figs = optimize_h2pp(file_path, mode="battery_ref")
    export_jahreszeiten_und_stacked_tco_plot(tco_battery_fcev, figs, exp_name, "Batt_FCEV")

    # ==== 3. Campus + Battery + BEV ====
    tco_battery_bev, figs = optimize_h2pp(ev_tempfile_path, mode="battery_ref")
    export_jahreszeiten_und_stacked_tco_plot(tco_battery_bev, figs, exp_name, "Batt_BEV")

    # ==== 4. Campus + FCEV (no H2PP or Batt.)====

    tco_sq_fcev, figs = optimize_h2pp(file_path, mode="power_grid_only_ref")
    export_jahreszeiten_und_stacked_tco_plot(tco_sq_fcev, figs, exp_name, "SQ_FCEV")

    # ==== 5. Campus + EV (no H2PP or Batt.)====

    tco_sq_bev, figs = optimize_h2pp(ev_tempfile_path, mode="power_grid_only_ref")
    export_jahreszeiten_und_stacked_tco_plot(tco_sq_bev, figs, exp_name, "SQ_BEV")

    # ====

    labels = ["H2PP", "Battery + FCEV", "Battery + EV", "Only Grid + FCEV", "Only Grid + EV"]
    tcos = [tco_normal, tco_battery_fcev, tco_battery_bev, tco_sq_fcev, tco_sq_bev]

    donut_export(exp_name, tcos, labels)
    multiple_tco_costs_and_revenue_bars_export(exp_name, tcos, labels)
    multiple_tco_total_cost_comparison_export(exp_name, tcos, labels)

    # Delete our temporary EV json file
    os.remove(ev_tempfile_path)


def set_nested_value(d, key_list, value):

    # Traverse to the correct dictionary level

    if len(key_list) == 1:
        d[key_list[0]] = value
        return
    for key in key_list[:-1]:
        d = d[key]

    # Set the final key to the value
    d[key_list[-1]] = value

def calc_and_plot_sensitivity(the_parsed_config_json, original_folder_path, x_values, key_path, plot_title, plot_x_label,
                              exp_name, file_name_prefix):
    tcos = calc_tco_sensitivity(the_parsed_config_json, original_folder_path, x_values, key_path)
    list_of_tco_npvs = [tco.npv_total / 1e6 for tco in tcos]

    # Now plot in matplotlib the x_values against the list_of_tco_npvs
    # Plotting
    plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
    plt.plot(x_values, list_of_tco_npvs, marker='o', linestyle='-', color='b')  # Customize marker, line, and color

    # Adding labels and title
    plt.xlabel(plot_x_label)  # Customize your x-axis label
    plt.ylabel('NPV in Mio. EUR')  # Customize your y-axis label

    # Optionally add grid
    plt.grid(True)

    # Display the plot
    create_export_folder(exp_name)
    plt.savefig(f"Plot_Results_For_MA/{exp_name}/{file_name_prefix}_Sensitivity.pdf")
    plt.title(plot_title)  # Title will only be on the displayed plot, not in the saved PDF one.
    plt.show()

def plot_sensitivity_multipe_scenarios(the_scenario_config_dicts, original_folder_path, scenario_labels, x_values, key_path_x,
                                       plot_title, plot_x_label,
                                       exp_name, file_name_prefix,
                                       hide_grid=False):
    """
        Plot in the same figure one graph for each scenario, where the property (x_values) in key_path is altered
        Quite similar to calc_and_plot_pair_sensitivity
    """
    all_graphs = []
    for config_dict in the_scenario_config_dicts:

        c_dict = copy.deepcopy(config_dict)

        tcos = calc_tco_sensitivity(c_dict, original_folder_path, x_values, key_path_x)
        list_of_tco_npvs = [tco.npv_total / 1e6 for tco in tcos]
        all_graphs.append(list_of_tco_npvs)

    # Now plot in matplotlib the x_values against the list_of_tco_npvs
    # Plotting
    plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
    for i, list_of_tco_npvs in enumerate(all_graphs):
        z_value = scenario_labels[i]

        plt.plot(x_values, list_of_tco_npvs, label=z_value)

    # Adding labels and title
    plt.xlabel(plot_x_label)  # Customize your x-axis label
    plt.ylabel('NPV in Mio. EUR')  # Customize your y-axis label
    plt.legend()

    # Optionally add grid
    if not hide_grid:
        plt.grid(True)

    # Display the plot and save it
    create_export_folder(exp_name)
    plt.savefig(f"Plot_Results_For_MA/{exp_name}/{file_name_prefix}_Sensitivity.pdf")
    plt.title(plot_title)  # Title will only be on the displayed plot, not in the saved PDF one.
    plt.show()
def calc_and_plot_pair_sensitivity(the_parsed_config_json, original_folder_path, x_values, z_values, key_path_x, key_path_z, plot_title, plot_x_label, plot_z_label,
                                   exp_name, file_name_prefix):
    """
    Function to calculate and plot a sensitivity analysis for two parameters.
    x_values contains the values for the x-axis, for modifying the first parameter.
    z_values contains the values for all "reference scenarios" (one graph per reference scenario).

    For every fixed value in z_values, the function will calculate the NPV for every value in x_values and plot for this
    reference scenario a graph with x_values on the x-axis and the NPV on the y-axis.

    @param the_parsed_config_json:
    @param x_values:
    @param z_values:
    @param key_path_x:
    @param key_path_z:
    @param plot_title:
    @param plot_x_label:
    @param plot_z_label:
    @return:
    """

    all_graphs = []
    for z_value in z_values:
        copied_json = copy.deepcopy(the_parsed_config_json)  # Copy the dictionary to avoid changing the original
        set_nested_value(copied_json, key_path_z, z_value)

        tcos = calc_tco_sensitivity(copied_json, original_folder_path, x_values, key_path_x)
        list_of_tco_npvs = [tco.npv_total / 1e6 for tco in tcos]
        all_graphs.append(list_of_tco_npvs)


    # Now plot in matplotlib the x_values against the list_of_tco_npvs
    # Plotting
    plt.figure(figsize=(8, 6))  # Optionally set the size of the plot
    for i, list_of_tco_npvs in enumerate(all_graphs):
        z_value = z_values[i]
        plt.plot(x_values, list_of_tco_npvs, label =f'{plot_z_label} = {z_value}')  # Customize marker, line, and color

    # Adding labels and title
    plt.xlabel(plot_x_label)  # Customize your x-axis label
    plt.ylabel('NPV in Mio. EUR')  # Customize your y-axis label
    plt.legend()

    # Optionally add grid
    plt.grid(True)

    # Display the plot
    # Create dictionary if not already exists:
    create_export_folder(exp_name)
    plt.savefig(f"Plot_Results_For_MA/{exp_name}/{file_name_prefix}_Sensitivity.pdf")
    plt.title(plot_title)  # Title will only be on the displayed plot, not in the saved PDF one.
    plt.show()


def calc_tco_sensitivity(the_parsed_config_json, file_path, x_values, key_path, optimizer_mode: Literal["normal", "battery_ref", "power_grid_only_ref"]="normal"):

    """
    file path is the folder path where the original json was stored; so that the file links in the file will work
    """
    list_of_tcos = []

    for value in x_values:
        # Setting a value dynamically using a list of keys

        copied_json = copy.deepcopy(the_parsed_config_json)  # Copy the dictionary to avoid changing the original
        set_nested_value(copied_json, key_path, value)

        # write the altered file to a temporary file in the file_path:
        output_file_path = os.path.join(file_path, "__tempA_sensitivity_analysis.json")
        print(copied_json)
        with open(output_file_path, "w") as user_file:  # may NOT exist or will be overwritten
            json.dump(copied_json, user_file, indent=4)

        tco_obj = h2pp.optimizer.optimize_h2pp(output_file_path, mode=optimizer_mode)[0]

        print(value, tco_obj.npv_total)

        os.remove(output_file_path)

        list_of_tcos.append(tco_obj)

    return list_of_tcos
