from dataclasses import dataclass

import numpy as np
import pandas as pd
import rainflow
from matplotlib import pyplot as plt
from oemof import solph
from oemof.solph import views

from plotly.subplots import make_subplots
import plotly.graph_objects as go
from scipy.signal import find_peaks

from h2pp import tco


@dataclass
class EvaluationResult:
    tco: tco.TCO
    aufschlaege_strom_total_eur_per_kwh: float
    leistungspreis_summe: float
    total_consumption_year_kwh: float
    peak_power_year_kW: float


def get_max_depth(x: np.array, **kwargs) -> float:
    '''
    This function is used for the 'tank requirement' calculation in the feasibility analysis.

    Find the maximum depth between a peak (local max) and the consecutive lowest point in a signal.
    :param x: an array holding the signal (in our case should be the current "state of charge" of the hydrogen tank)
    :param kwargs: set plot_peaks to True for visualization purposes (only for testing)
    :return: the absolute value difference between the peak and the following lowest point
    '''
    peaks, _ = find_peaks(x)
    lowzz, _ = find_peaks(-1 * x)

    # as the edges are not considered, we need to manually check if they might be peaks

    # left side
    i = 0
    while x[i] == x[i + 1]:
        if i == x.size - 2:
            # penultimate entry = last entry, that means the
            # function completely constant... nothin happens, just break.
            # print("allconst")
            return 0
        i += 1
    if x[i] > x[i + 1]:
        peaks = np.insert(peaks, 0, i)
    elif x[i] < x[i + 1]:
        lowzz = np.insert(lowzz, 0, i)

    # right side - func CAN NOT be const (otherwise would have been returned 0 before)
    i = x.size - 1
    while x[i] == x[i - 1]:
        i -= 1

    if x[i] > x[i - 1]:
        peaks = np.append(peaks, i)
    elif x[i] < x[i - 1]:
        lowzz = np.append(lowzz, i)

    max_depth = 0  # Initialize max_depth with 0 - if we will find any peak (e.g. if the tank is only filling up), we need to return 0
    for peak_x_idx in peaks:
        following_lows_idx = lowzz[lowzz > peak_x_idx]
        if len(following_lows_idx) == 0:
            continue
        for low_x_idx in following_lows_idx:
            if x[peak_x_idx] - x[low_x_idx] > max_depth:
                # New max depth found
                max_depth = x[peak_x_idx] - x[low_x_idx]
                # print(
                #    f"Peak at {peak_x_idx} with value {x[peak_x_idx]} and following low at {low_x_idx} with value {x[low_x_idx]}")

    #print("max_depth: ", max_depth)

    if "plot_peaks" in kwargs:
        if kwargs["plot_peaks"]:
            # plotting only runs if our x is NOT constant.
            plt.plot(x)
            plt.plot(peaks, x[peaks], "x")
            plt.plot(lowzz, x[lowzz], "o")
            plt.plot(np.zeros_like(x), "--", color="gray")
            plt.show()

    return max_depth


def get_lfp_battery_percent_degradation(verlauf_soc_battery: np.ndarray):
    """
    From the results, extract the cycles and half cycles in order to get the percent degradation of the battery in the
    given scenario (usually, a week).
    Calculation assumes LFP Battery with 7000 full equivalent cycles lifetime regardless of DOD.

    :param verlauf_soc_battery: The state of charge of the battery over time
    :return: Degatation as a float, e.g. 0.57 for 57% degradation

    """

    fec = 7000  # full equivalent cycles

    batterie_kwhs = verlauf_soc_battery

    #cycle_count: The number of equivalent cycles from rainflow counting
    #dod: the depth of discharge (float in range 0..1)

    percent_degradation = 0
    for dod, _, cycle_count, _, _ in rainflow.extract_cycles(batterie_kwhs):
        percent_degradation += (cycle_count * dod) / fec

    return percent_degradation


def number_to_day_hour(number, simulation_interval, start_of_week):
    """
    Convert an int number to a day and hour in the format "Mon 00:00".

    Example: if start_of_week = 1 (Tuesday) and simulation_interval = 30 min, then e.g. 0 is Tue 0:00; 1 is Tue 0:30; 48 is Wed 0:00 and so on
    @param number: The number to convert
    @param simulation_interval: The simulation interval in minutes
    @param start_of_week: Day of week when the simulation week starts: 0 for monday, 1 for tuesday, 6 for sunday.
    @return: the converted string in the form "Mon 0:00"
    """
    # Chatgpt helped me a bit with this func
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    # Calculate the number of intervals per day
    intervals_per_day = 24 * (60 // simulation_interval)

    # Adjust the number with the start_of_week shift
    adjusted_number = number + start_of_week * intervals_per_day

    # Calculate the corresponding day and hour
    day_index = (adjusted_number // intervals_per_day) % 7
    hour = (adjusted_number % intervals_per_day) * simulation_interval // 60
    minute = (adjusted_number % intervals_per_day) * simulation_interval % 60

    return f"{days[day_index]} {hour:02d}:{minute:02d}"


def process_results_and_return_plot(results, simulation_interval, start_of_week, electricity_prices,
                                    evalResult: EvaluationResult, titlestring=""):
    '''
    :param results:
        After doing
            om.solve(..)
        on the model and doing
            my_energysystem.results["main"] = solph.processing.results(om),
        the value
            results = my_energysystem.results["main"]
        can be passed to this function to plot some interesting info.
    :@param start_of_week: Day where the simulation week starts: 0 for monday, 1 for tuesday, 6 for sunday.
    :return:
    '''

    # to address objects by their label, we convert the results dictionary so that the keys are changed to strings representing the labels
    # this is especially needed for the fuel cell to differentiate between the thermal and electrical output
    results = views.convert_keys_to_strings(results)

    # The last entry in the simulation result is always a weird "nan" entry; and the penultimate is 0 but as, for
    # some mathematical reason would get plotted at t=0 resulting in a weird horizontal line, we need to get rid of
    # this one as well.
    buy_power = solph.views.node(results, 's_el_grid_buy')["sequences"].values[:-2, 0]
    sell_power = -1 * solph.views.node(results, 's_el_grid_sell')["sequences"].values[:-2, 0]
    industriepark_and_ac_consumption = -1 * solph.views.node(results, 'Electricity_Consumption_AC_Ges')[
                                                "sequences"].values[
                                            :-2, 0]

    dc_consumption = -1 * solph.views.node(results, 'Electricity_Consumption_DC_Ges')["sequences"].values[:-2, 0]

    pv_power_ges = solph.views.node(results, 'Electricity_DC_Generation_Ges')["sequences"].values[:-2, 0]

    fcev_consumption_350 = solph.views.node(results, 'H2_Consumption_Ges_350')["sequences"].values[:-2, 0] / 33.3
    fcev_consumption_700 = solph.views.node(results, 'H2_Consumption_Ges_700')["sequences"].values[:-2, 0] / 33.3

    buy_h2_power_350 = solph.views.node(results, 's_h2_grid_buy_350')["sequences"].values[:-2, 0]
    buy_h2_power_700 = solph.views.node(results, 's_h2_grid_buy_700')["sequences"].values[:-2, 0]
    buy_h2_power = (buy_h2_power_350 + buy_h2_power_700) / 33.3

    # Titles and colors for the first plot
    titles_and_colors_1 = [
        (buy_power, "Eingekaufte AC-Leistung", 'orange'),
        (sell_power, "Verkaufte AC-Leistung", 'green'),
        (industriepark_and_ac_consumption, "Verbrauch AC gesamt", 'magenta'),
        (dc_consumption, "Verbrauch DC gesamt", 'cyan'),
        (pv_power_ges, "Generierte Leistung DC", 'red'),
        (electricity_prices, "Spotmarktpreis", 'grey')
    ]

    # Titles and colors for the second plot
    # todo: Hier ggf später EV Flotte separat abbilden (derzeit über die AC/DC Verbräuche.)
    titles_and_colors_2 = [
        (fcev_consumption_350, "FCEV Lokal (350 bar)", 'grey'),
        (fcev_consumption_700, "FCEV Lokal (700 bar)", 'orange'),
        (buy_h2_power, "FCEV Extern (gesamter <br>Zukauf 350 und 700 bar)", 'cyan')
    ]

    # todo besseres "error handling" hier um herauszufinden ob tatsächlich ein error, oder die Komponente tatsächlich deaktiviert war!
    # todo die try Blöcke sind hier nur um zu verhindern dass das Programm abbricht, wenn eine Komponente nicht existiert

    # Elektrolysezelle
    try:
        elektrolyseur_out = solph.views.node(results, 'Elektrolysezelle')["sequences"].values[:-2, 0]
        titles_and_colors_2.append((elektrolyseur_out, "Elektrolyse (Ausgang)", 'green'))
    except KeyError:
        pass  #todo

    #Brennstoffzelle
    try:
        bz_th = results[('Brennstoffzelle', 'thermal')]['sequences'].values[:-2, 0]
        bz_el = results[('Brennstoffzelle', 'electricity_dc')]['sequences'].values[:-2, 0]
        bz_in = results[('h2_30bar', 'Brennstoffzelle')]['sequences'].values[:-2, 0]

        bzarr = [
            (bz_el, "Fuel Cell (elektr. Ausgang)", 'brown'),
            (bz_th, "Fuel Cell (therm. Ausgang)", 'black'),
            (bz_in, "Fuel Cell (Eingang)", 'magenta')
        ]
        titles_and_colors_2.extend(bzarr)
    except KeyError:
        pass  #todo

    # Storage vom H2 Tank
    # siehe hier bei GenericStorage: https://oemof-solph.readthedocs.io/en/latest/usage.html
    column_name = (('H2Tank', 'None'), 'storage_content')
    tank_fuellstand_kg = None  # Need to initialize it here as I do a "if var is tank_fuellstand_kg" check later
    try:
        SC = views.node(results, 'H2Tank')['sequences'][column_name]
        tank_fuellstand_kg = SC.values[
                             :-2] / 33.3  # 33.3 kWh pro kg H2 # TODO dynamische eingabe (wie mit der CONV_RATE_kWh_to_kg_H2 in der generators.py), auch oben
        titles_and_colors_2.append((tank_fuellstand_kg, "Füllstand H2-Tank", 'blue'))
    except KeyError:
        pass  #todo

    # analog fuer den Batteriespeicher
    column_name = (('BatteryStorage', 'None'), 'storage_content')
    try:
        SC = views.node(results, 'BatteryStorage')['sequences'][column_name]
        batterie_kwhs = SC.values[:-2]
        titles_and_colors_2.append((batterie_kwhs, "Ladezustand Batterie", 'red'))
    except KeyError:
        batterie_kwhs = None

    # Create subplots with shared x-axis
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                        specs=[[{"secondary_y": True}], [{"secondary_y": True}]])

    # Plotting
    # x-achse für alle gleich: alles hat selbe länge.. -> nimm einfach irgendeins
    x_values_number = list(range(len(buy_power)))
    x_values_formatted = [number_to_day_hour(number, simulation_interval, start_of_week) for number in x_values_number]

    # First plot
    for var, title, color in titles_and_colors_1:
        if var is electricity_prices:
            fig.add_trace(
                go.Scatter(x=x_values_formatted, y=var, mode='lines', name=title, line=dict(color=color, dash='dash'),
                           legendgroup='1'),
                row=1, col=1, secondary_y=True)
        else:
            fig.add_trace(go.Scatter(x=x_values_formatted, y=var, mode='lines', name=title, line=dict(color=color),
                                     legendgroup='1'),
                          row=1, col=1, secondary_y=False)

    # Second plot
    for var, title, color in titles_and_colors_2:
        fig.add_trace(go.Scatter(x=x_values_formatted, y=var, mode='lines', name=title, line=dict(color=color),
                                 legendgroup='2'),
                      row=2, col=1, secondary_y=False if (var is buy_h2_power or
                                                          var is fcev_consumption_350 or
                                                          var is fcev_consumption_700 or
                                                          var is tank_fuellstand_kg) else True)

    # Update layout for first plot
    fig.update_yaxes(title_text="Leistung [kW]", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Preis Strom EUR / kWh", row=1, col=1, secondary_y=True)
    fig.update_xaxes(title_text="Zeit", row=1, col=1)

    # Update layout for second plot
    fig.update_yaxes(title_text="Leistung [kW] / Ladezustand [kWh]", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Masse [kg] / Tankrate [kg/h]", row=2, col=1, secondary_y=False)
    fig.update_xaxes(title_text="Zeit", row=2, col=1)

    # Update overall layout
    jahresbenutzungsdauer = evalResult.total_consumption_year_kwh / evalResult.peak_power_year_kW
    fig.update_layout(
        title_text=titlestring + "<br>" + f"Strompreis (ohne Spotmarktpreis): {evalResult.aufschlaege_strom_total_eur_per_kwh * 100:.2f} ct/kWh, Leistungspreis: {evalResult.leistungspreis_summe / 1000:.2f} Tsd. EUR<br>Gesamtverbrauch (Netzstrom): {evalResult.total_consumption_year_kwh / 1000:.0f} MWh/a, Spitzenlast: {evalResult.peak_power_year_kW:.0f} kW, Jahresbenutzungsdauer: {jahresbenutzungsdauer:.0f} h",
        height=800,
        template='plotly_white',
        xaxis=dict(
            nticks=10,
            tickformat='%a %H:%M',  # Keep the format as Day Hour:Minute
            dtick=6 * 3600000  # Alle 6 hours (in milliseconds)
        ),

        legend_tracegroupgap=300,
        # Abstand zwischen den Gruppen im Legend (Trennung Legende 1 (oberer Plot) und Legende 2 (unterer Plot))
        # TODO in den Output Plots aus den Fallbeispielen und beim direkten Anzeigen passen die 300 gut, in der GUI
        #  jedoch ist der Abstand zwischen den Gruppen zu gross, sodass man scrollen ist (Figur nicht hoch genug)! Ich
        #  habe hier noch keine Flexibilisierung gefunden, um beides gut darzustellen. Evtl. Figures auf der GUI höher
        #   machen oder ähnlich.

    )
    fig.update_xaxes(tickangle=-45, nticks=29)  # rotate x-axis labels

    return fig


def netztransparenz_importer(file_path):
    '''

    :param file_path: Dateipfad zu einer File im Format wie aus https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/EEG/Transparenzanforderungen/Marktprämie/Spotmarktpreis-nach-3-Nr-42a-EEG exportiert
    :return: ein Dataframe mit 2 Columns: date (datetime) und price_in_EUR_per_kWh (float, in EUR), hier noch ohne Resampling oder Mittelwertbildung sondern wie die Input File, nur mit den relevanten Infos als Dataframe aufbereitet
    '''

    # Load the CSV file
    df = pd.read_csv(file_path, delimiter=';')

    # Combine the "Datum" and "von" columns into a single datetime column
    df['Datum_von'] = pd.to_datetime(df['Datum'] + ' ' + df['von'], format='%d.%m.%Y %H:%M')

    # Replace comma with dot in the "Strompreis_in_ct_per_kWh" column and convert to float; then cent to euro
    df['price_in_EUR_per_kWh'] = df['Spotmarktpreis in ct/kWh'].str.replace(',', '.').astype(float) / 100

    # Rename Date column
    df.rename(columns={'Datum_von': 'date', 'price_in_EUR_per_kWh': 'value'}, inplace=True)

    # Select only the required columns
    df_final = df[['date', 'value']]

    # Set 'date' as the index of the dataframe
    df_final.set_index('date', inplace=True)

    return df_final


def typical_week(df, months: list[int], start_of_week: int, base_sim_interval_in_min: int,
                 method='standard') -> pd.Series:
    '''

    Calculates a typical week by averaging the values of the specified months for each hour of the day, for each day of
    the week (e.g. Monday 0:00, Monday 1:00, ..., Sunday 23:00, but shifted according to the start_of_week).

    :param df: Dataframe with 2 Columns: date [Index!] (datetime) and value (float, e.g. the price per kWh in EUR)
    :param months: List of months to filter for (as a list of integers, e.g. [1, 2, 12] for January, February, December)
    :param start_of_week: Day where the simulation week starts: 0 for monday, 1 for tuesday, 6 for sunday.
    :param base_sim_interval_in_min: the base simulation interval, e.g. 15 for 15-min-intervals
    :return: timeseries in the format required for oemof (pandas series with datetime index and float values) with the
    typical day in the base simulation interval
    '''

    if start_of_week not in [0, 1, 2, 3, 4, 5, 6]:
        raise ValueError("start_of_week must be an integer between 0 and 6, where 0 is Monday, 6 is Sunday")

    reihenfolge_woche = list(range(start_of_week, 7)) + list(
        range(0, start_of_week))  # e.g. wenn start_of_week = 3, dann [3,4,5,6,0,1,2]

    week_series = []

    if method == 'standard':

        for weekday in reihenfolge_woche:
            # Filter DataFrame for the months specified in the list
            df_filtered = df[df.index.month.isin(months) & df.index.weekday.isin([weekday])]

            # Group by hour and calculate the mean
            typical_day = df_filtered.groupby(df_filtered.index.hour).mean()
            typical_day = typical_day.sort_index()  # might not be necessary but just to be sure, sort by hour
            td_values = typical_day['value'].values

            week_series.extend(td_values)

    elif method == 'weather_avg':
        # Hier unterscheiden wir nicht nach den Wochentagen, sondern mitteln einfach über das gesamte Monatsintervall.
        df_filtered = df[df.index.month.isin(months)]
        # Group by hour and calculate the mean
        typical_day = df_filtered.groupby(df_filtered.index.hour).mean()
        typical_day = typical_day.sort_index()  # might not be necessary but just to be sure, sort by hour
        td_values = typical_day['value'].values
        for _ in range(0, 7):
            week_series.extend(td_values)

    else:
        raise ValueError(f"Unknown value {method} for argument 'method'.")

    # Copy the first value to also be the last value as Resampling needs the last value as a closed interval
    week_series.append(week_series[0])

    # Now, week_series is a Series with the mean value for each hour of the 7 days in the week, sorted by the hour (entries 0..23 -> hourly averages for 1st day, 24..47 -> hourly averages for 2nd day, etc.)
    # Finally, turn the typical week into a timeseries for the simulation.

    # For resampling to the right interval, we need a time index. We create a time index with 1h intervals as we did
    # averaging for each hour above. Weekday of the index is generally irrelevant here as long as the values
    # are in the right order as normalized_ts_values will in the end only contain the values without any time index

    my_index = pd.date_range(start='2020-01-01',
                             end='2020-01-08',
                             inclusive='both',
                             freq="1h")

    ts_typical_day = pd.Series(week_series, index=my_index)
    ts_resampled_values = resample_time_series_and_extract_values_for_oemof(ts_typical_day,
                                                                            base_sim_interval_in_min)

    return ts_resampled_values


def sum_days_in_months(months: list[int]):
    """
    Berechnet die Gesamt-Anzahl der Tage in einer gegebenen Liste von Monaten in einem Nicht-Schaltjahr.


    Args:
        months (int): Liste der Monate, für die die Summe der Tage berechnet werden soll (als Einträge der Form 1 = Januar, 12 = Dezember).
        Bpsw. [1,2,12] für Januar, Februar und Dezember.

    Returns:
        int: Die Anzahl der Tage im angegebenen Intervall.


    Beispiele:
        >>> sum_days_in_months([1,2,12])
        90
        >>> sum_days_in_months([6,7,8,9])
        122
        >>> sum_days_in_months([3,4,5])
        92
    """

    # Tage pro Monat in einem Nicht-Schaltjahr
    days_in_month = {
        1: 31,  # Januar
        2: 28,  # Februar
        3: 31,  # März
        4: 30,  # April
        5: 31,  # Mai
        6: 30,  # Juni
        7: 31,  # Juli
        8: 31,  # August
        9: 30,  # September
        10: 31,  # Oktober
        11: 30,  # November
        12: 31  # Dezember
    }

    # Berechne die Anzahl der Tage
    total_days = 0

    for month in months:
        total_days += days_in_month[month]

    return total_days


def resample_time_series_and_extract_values_for_oemof(series: pd.Series, freq_in_min: int,
                                                      one_day_input=False) -> pd.Series:
    # Resamples the given series to the desired frequency in minutes.
    # Only resampling. Changing the start of week, if required, needs to be done beforehand.

    # Linear Interpolation for the resampler
    # Using the pandas resampler, more info under
    #       https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.core.resample.Resampler.interpolate.html
    #       and https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Series.resample.html
    resampler = series.resample(f"{freq_in_min}min")
    resampled_series = resampler.interpolate(method='linear')

    # Check that the resampled series has the expected length
    if one_day_input:
        expected_length = (24 * 60 / freq_in_min) + 1
    else:
        expected_length = (
                                  24 * 60 * 7 / freq_in_min) + 1  # +1 because we are everywhere including both ends of the full week (intentionally so that we actually can do the resampling)

    if len(resampled_series) != expected_length:
        raise ValueError(
            f"Expected {expected_length} values, but got {len(resampled_series)}. This most certainly means that the input series did not contain a full week (WITHOUT 0:00 as the last element) or the intervals were not equally distributed.")

    # If we only have a one-day input scope, we need to repeat the values for the whole week, but without the
    # closing 0:00 value, which needs to be added only to the last day.
    if one_day_input:
        cutout = pd.Series(resampled_series.values[:-1])
        values = cutout
        for _ in range(1, 7):
            values = pd.concat([values, cutout], ignore_index=True)
        values = pd.concat([values, pd.Series([resampled_series.values[0]])], ignore_index=True)

    else:
        # extract the values from the resampled series (we only need the values without time index for oemof)
        values = resampled_series.values

    return values
