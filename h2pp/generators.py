"""
Enthält u.a.
- Funktionen, um die Hauptkomponenten für das Energiesystem (Elektrolyseur, Brennstoffzelle, PV-Anlage, Konverter etc.
mittels Parametern (als Solph-Objekte) zu erstellen.
- Enums für Jahreszeiten (an mehreren Stellen relevant), Kundengruppen und Tagesarten (BDEW)
- Hilfsfunktionen für Wandlung von kWh in kg H2 und umgekehrt, Bestimmung der typischen Monate je Jahreszeit
- Erstellung von konstanten Zeitreihen und Import + Mittelwertbildung + Normalisierung von Zeitreihen aus CSV
- Erstellung von Verläufen für Wetter (PVGIS)
- Arealbedarf (BDEW) """

import enum
import os

import numpy as np
import pandas as pd
import pvlib
import requests.exceptions
from oemof import solph

from h2pp import helperFunctions
from h2pp.helperFunctions import resample_time_series_and_extract_values_for_oemof
from timezonefinder import TimezoneFinder


# Allgemeine Anmerkung: Wirkungsgrade müssen offenkundig i.A. auf die Outputs: Siehe
# https://oemof-solph.readthedocs.io/en/latest/reference/oemof.solph.components.html

def create_electrolyzer(input_bus_el: solph.Bus, output_bus_h2: solph.Bus, electrical_efficiency: float,
                        nominal_power: float) -> solph.components.Converter:
    """

    :param input_bus_el:
    :param output_bus_h2:
    :param electrical_efficiency: Wirkungsgrad der Elektrolyse, bezogen auf den unteren Heizwert
    :param nominal_power: Ausgangsleistung des Elektrolyseurs in kW
    :return:
    """
    conv = solph.components.Converter(label="Elektrolysezelle",
                                      inputs={input_bus_el: solph.Flow()},
                                      outputs={output_bus_h2: solph.Flow(nominal_value=nominal_power)},
                                      conversion_factors={output_bus_h2: electrical_efficiency})

    return conv


class Jahreszeit(enum.Enum):
    """
    An enum for the seasons in Simulation and BDEW """

    WINTER = "Winter"
    SOMMER = "Sommer"
    UEBERGANG = "Uebergang"


class BDEW_Kundengruppe(enum.Enum):
    H0 = "H0"
    G0 = "G0"
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"


class BDEW_Tagesart(enum.Enum):
    """
    An enum for the different types of days in BDEW """

    WERKTAG = "Werktag"
    SAMSTAG = "Samstag"
    SONNTAG = "Sonntag"


# Konversionsfaktor kWh zu kg H2 - Unterer Heizwert (LHV) von H2: 33.33 kWh/kg H2
CONV_RATE_kWh_to_kg_H2 = 33.33


def convert_kWh_to_kg_H2(kWh: float) -> float:
    """
    Converts kWh to kg of H2. The conversion rate is CONV_RATE_kWh_to_kg_H2 = 33.33 kWh/kg H2

    Parameters
    ----------
    kWh: float
        The amount of energy in kWh

    Returns
    -------
    float
        The amount of H2 in kg
    """

    return kWh / CONV_RATE_kWh_to_kg_H2


def convert_kg_H2_to_kWh(kg_H2: float) -> float:
    """
    Converts kg of H2 to kWh.

    Parameters
    ----------
    kg_H2: float
        The amount of H2 in kg

    Returns
    -------
    float
        The amount of energy in kWh
    """
    return kg_H2 * CONV_RATE_kWh_to_kg_H2


def typical_months(jahreszeit: Jahreszeit) -> list[int]:
    if jahreszeit == Jahreszeit.SOMMER:
        months = [6, 7, 8, 9]

    elif jahreszeit == Jahreszeit.WINTER:
        months = [12, 1, 2]

    else:
        months = [3, 4, 5, 10, 11]

    return months


def create_const_time_series(power_value_kW: float, base_sim_interval_in_min: int) -> pd.Series:
    """
    Creates a constant time series with the given power value in kW.

    Parameters
    ----------
    power_value_kW: float
        The constant power value in kW
    base_sim_interval_in_min: int
        The base simulation interval in minutes

    Returns
    -------
    pd.Series
        The time series
    """

    # Create a time series with the constant power value
    ts = pd.Series([power_value_kW] * (
            24 * 60 * 7 // base_sim_interval_in_min + 1))  # +1 because we are including 0:00 as the last value
    return ts


def create_bdew_consumption_time_series(kundengruppe: BDEW_Kundengruppe,
                                        jahreszeit: Jahreszeit,
                                        annual_consumption: float,
                                        start_of_week: int,
                                        base_sim_interval_in_min: int) -> pd.Series:
    # :param start_of_week: Day when the simulation week starts: 0 for monday, 1 for tuesday, 6 for sunday.

    if start_of_week not in [0, 1, 2, 3, 4, 5, 6]:
        raise ValueError("start_of_week must be an integer between 0 and 6, where 0 is Monday, 6 is Sunday")

    reihenfolge_woche = list(range(start_of_week, 7)) + list(
        range(0, start_of_week))  # e.g. wenn start_of_week = 3, dann [3,4,5,6,0,1,2]

    week_series = []

    for weekday in reihenfolge_woche:
        if weekday in [0, 1, 2, 3, 4]:
            # Werktag
            tagesart = BDEW_Tagesart.WERKTAG
        elif weekday == 5:
            # Samstag
            tagesart = BDEW_Tagesart.SAMSTAG
        else:
            # Sonntag
            tagesart = BDEW_Tagesart.SONNTAG

        power_values = __import_bdew_values__(kundengruppe, tagesart, jahreszeit, annual_consumption)
        week_series.extend(power_values)

    # Copy the first value to also be the last value as Resampling needs the last value as a closed interval
    week_series.append(week_series[0])

    # For resampling to the right interval, we need a time index. We create a time index with 15 minute intervals
    # as BDEW data has 15 minute resolution. Weekday of the index is generally irrelevant here as long as the values
    # are in the right order as normalized_ts_values will in the end only contain the values without any time index

    my_index = pd.date_range(start='2020-01-01',
                             end='2020-01-08',
                             inclusive='both',
                             freq="15min")

    ts = pd.Series(week_series, index=my_index)
    normalized_ts_values = resample_time_series_and_extract_values_for_oemof(ts, base_sim_interval_in_min)

    return normalized_ts_values


def import_and_normalize_one_day_time_series_csv(csv_path: str, base_sim_interval_in_min: int) -> pd.Series:
    """
    Creates a sink from a time series CSV file that contains values for one day only (irrespective of the season).

    Parameters
    ----------
    input_bus_el
    csv_path: str
        Path to the CSV file containing the time series (currently only supporting one day: 0:00 to the last interval, e.g 23:45 if simulation interval = 15min). The CSV file must have a column 'datetime' and a column 'value'. [ABSOULUTE PATH ZUR FILE]
    base_sim_interval_in_min: int
        The base simulation interval in minutes

    Returns
    -------
    solph.components.Sink
    """

    ts = pd.read_csv(csv_path, parse_dates=True, index_col='datetime')
    normalized_ts_values = resample_time_series_and_extract_values_for_oemof(ts['value'],
                                                                             base_sim_interval_in_min,
                                                                             one_day_input=True)

    return normalized_ts_values


def import_and_normalize_one_week_time_series_csv(csv_path: str, base_sim_interval_in_min: int,
                                                  start_of_week: int, jahreszeit: Jahreszeit) -> pd.Series:
    # TODO error checks ergänzen, dass tatsächlich alles so lang ist, wie es sein soll.

    # Für jede der drei Jahreszeiten MUSS eine Woche in der CSV enthalten sein.
    # Diese Woche MUSS an einem Montag beginnen um 0:00 und das letzte Intervall (geschlossen - Montag 0:00 Folgewoche) enthalten.
    # Vorschlag:
    #   WINTER: -> Januar.
    #   SOMMER: -> Juli.
    #   ÜBERGANG: -> April.
    #   Für den Januar kann die Woche auf den 2024-01-01 0:00 bis 2024-01-08 0:00 eingetragen werden (Mo-So)
    #   für den April  kann die Woche auf den 2024-04-01 0:00 bis 2024-04-08 0:00 eingetragen werden (Mo-So)
    #   für den Juli   kann die Woche auf den 2024-07-01 0:00 bis 2024-07-08 0:00 eingetragen werden (Mo-So)

    ts = pd.read_csv(csv_path, parse_dates=True, index_col='datetime')

    # Select the week with the right jahreszeit
    months = typical_months(jahreszeit)
    ts_week = ts[ts.index.month.isin(months)]
    normalized_ts_values = resample_time_series_and_extract_values_for_oemof(ts_week['value'],
                                                                             base_sim_interval_in_min)

    start_idx = 24 * (60 // base_sim_interval_in_min) * start_of_week

    # Shiften und geschlossenes Intervall berücksichtigen ("Letzter Wert ist erster Wert der Folgewoche)" -> ändert
    # sich durch den Shift
    shifted_normalized_values = np.append(normalized_ts_values[start_idx:-1], normalized_ts_values[:start_idx + 1])

    return shifted_normalized_values


def typical_week_from_yearly_data_csv(csv_path: str, jahreszeit: Jahreszeit, start_of_week: int,
                                      base_sim_interval_in_min: int) -> pd.Series:
    """
    Creates, for the requested Jahreszeit, a typical week from a CSV file that contains values for a whole year.
    For averaging, the weekdays of the timeindex are considered.
    start_of_week: Day where the simulated typical week starts: 0 for monday, 1 for tuesday, 6 for sunday.

    """
    ts = pd.read_csv(csv_path, parse_dates=True, index_col='datetime')

    months = typical_months(jahreszeit)

    normalized_ts_values = helperFunctions.typical_week(ts, months, start_of_week, base_sim_interval_in_min)
    return normalized_ts_values


def create_fuel_cell_chp(input_bus_h2: solph.Bus, output_bus_el: solph.Bus, output_bus_th: solph.Bus,
                         electrical_efficiency: float, thermal_efficiency: float,
                         nominal_power_el: float) -> solph.components.Converter:
    # Funktioniert derzeit wie folgt (Validierung mit plots siehe validierungs_skripte/brennstoffzelle.py):
    # 1. Es wird angenommen, dass die Brennstoffzelle eine konstante Leistung hat (nominal_power_el)
    # 2. Diese Leistung ist die Ausgangsleistung der Brennstoffzelle (elektrische Energie)
    # d.h. bspw. 50 kW Leistung bei 0.4 elektrischem Wirkungsgrad bedeutet, dass 50 kW / 0.4 = 125 kW an Wasserstoff
    # benötigt werden, um 50 kW elektrische Energie zu erzeugen. Bei thermischen Wirkungsgraden von 0.3 bedeutet das, dass
    # gleichzeitig 125 kW * 0.3 = 37.5 kW thermische Energie erzeugt werden.
    # die nominal_power_el ist das Leistungsmaximum, was die Brennstoffzelle an Strom erzeugen kann

    if electrical_efficiency + thermal_efficiency > 1:
        raise ValueError("The sum of electrical and thermal efficiency must not exceed 1.")

    nom_power_norm_1 = nominal_power_el / electrical_efficiency
    nom_power_th = nom_power_norm_1 * thermal_efficiency

    conv = solph.components.Converter(label="Brennstoffzelle",
                                      inputs={input_bus_h2: solph.Flow()},
                                      outputs={output_bus_el: solph.Flow(nominal_value=nominal_power_el),
                                               output_bus_th: solph.Flow(nominal_value=nom_power_th)},
                                      conversion_factors={output_bus_el: electrical_efficiency,
                                                          output_bus_th: thermal_efficiency})

    return conv


def create_simple_inverter(input_bus: solph.Bus, output_bus: solph.Bus, efficiency: float,
                           label: str) -> solph.components.Converter:
    """
    Creates a simple inverter that converts DC to AC or vice versa.
    Currently with potentially infinite power.
    Simple Inverter like in https://oemof-solph.readthedocs.io/en/latest/examples/offset_converter.html that is only
    characterized by a (fixed) efficiency.

    Parameters
    ----------
    input_bus: solph.Bus
        The input bus
    output_bus: solph.Bus
        The output bus. If input bus is AC, this should be the DC electricity bus and vice versa.
    efficiency: float
        The efficiency of the inverter

    Returns
    -------
    solph.components.Converter
    """


    conv = solph.components.Converter(label=label,
                                      inputs={input_bus: solph.Flow()},
                                      outputs={output_bus: solph.Flow()},
                                      conversion_factors={output_bus: efficiency})

    return conv


def create_compressor_a(input_bus_h2: solph.Bus, compression_energy_kwh_per_kg: float, output_bus_h2: solph.Bus,
                        electrical_bus: solph.Bus, nominal_power_in_kg_per_h,
                        label: str) -> solph.components.Converter:
    # Should work for AC and DC respectively as long as you set electrical_bus to the correct bus

    # Allgemeines zum H2 Verdichter siehe PDF http://arxiv.org/pdf/1702.06015

    """ compression_energy_to_lhv: Energieaufwand für die Verdichtung (in % des LHV des H2)"""
    """ Dies machen wir, damit wir unten mit den Wirkungsgraden arbeiten könne. Da ist das Verhältnis relevant
    (Quasi bei 6,6 kWh/kg => ca. 20% des LHV an Energie zusätzlich nötig => für Verdichtung von Energiemenge von 100 kWh
    H2 im Input sind 100 kWh H2 und 13 kWh Strom nötig)"""
    compression_energy_to_lhv = compression_energy_kwh_per_kg / CONV_RATE_kWh_to_kg_H2

    # Konvertiere kg/h in kW (kWh / h = kW, also  1 kg / h = 33.33 kW)
    h2_nom = convert_kg_H2_to_kWh(nominal_power_in_kg_per_h)

    conv = solph.components.Converter(label=label,
                                      inputs={input_bus_h2: solph.Flow(),
                                              electrical_bus: solph.Flow()},
                                      outputs={output_bus_h2: solph.Flow(nominal_value=h2_nom)},
                                      conversion_factors={input_bus_h2: 1,
                                                          electrical_bus: compression_energy_to_lhv})

    return conv


def create_h2_storage(bus_h2: solph.Bus, storage_capacity_in_kg: float, balance_storage_level=False,
                      initial_storage_level=0) -> solph.components.GenericStorage:
    """

    :param bus_h2:
    :param storage_capacity_in_kg: Menge an speicherbarem H2 in kg
    :param initial_storage_level: Initialer Füllstand des Speichers in % (0-1). Nur berücktsichtigt, wenn balance_storage_level=False
    :param balance_storage_level: If True, the optimizer will force the storage level to have the same level at the end of the simulation as at the beginning
    :return:
    """


    # Naive Annahmen:   - keine Verluste im Tank / beim Speichern selbst;
    #                   - Geschwindigkeit beim Inflow und Outflow nicht beschränkt

    storage_cap_in_kWh = convert_kg_H2_to_kWh(storage_capacity_in_kg)

    if balance_storage_level:

        h2st = solph.components.GenericStorage(
            label="H2Tank",
            nominal_storage_capacity=storage_cap_in_kWh,
            inputs={bus_h2: solph.Flow()},
            outputs={bus_h2: solph.Flow()},
            balanced=True, # Randbedingung setzen, dass Tank am Ende wieder denselben Füllstand haben muss wie am Anfang
        )

    else:

        h2st = solph.components.GenericStorage(
            label="H2Tank",
            nominal_storage_capacity=storage_cap_in_kWh,
            inputs={bus_h2: solph.Flow()},
            outputs={bus_h2: solph.Flow()},
            initial_storage_level=initial_storage_level, # MUSS zwingend gesetzt sein wenn balanced=False, sonst crasht oemof
            balanced=False,

        )

    return h2st


def create_battery_storage(bus_el: solph.Bus, storage_capacity_in_kWh: float,
                           soc_min, soc_max) -> solph.components.GenericStorage:
    """

    :param bus_el: The bus where the battery is connected to
    :param storage_capacity_in_kWh: Menge an speicherbarer elektrischer Energie in kWh
    :return:
    """

    # TODO Add possibility to balance the storage level between start and end of the simulation (currently only
    #  possible for H2 storage, see there)

    # Annahme: keine Verluste im Tank / beim Speichern selbst

    c_rate = 0.5  # 0.5 means that the battery can be charged or discharged in 2 hours -> the nominal power in kW is 0.5/h * storage_capacity_in_kWh
    nominal_power = storage_capacity_in_kWh * c_rate

    bs = solph.components.GenericStorage(
        label="BatteryStorage",
        nominal_storage_capacity=storage_capacity_in_kWh,
        inputs={bus_el: solph.Flow(nominal_value=nominal_power)},
        outputs={bus_el: solph.Flow(nominal_value=nominal_power)},
        min_storage_level=soc_min,
        max_storage_level=soc_max,
        initial_storage_level=soc_min,  # wenn nicht gesetzt crasht oemof (muss gesetzt sein, wenn balanced=False)
        balanced=False, # no balancing, todo allow it via a parameter (s.a.)
        inflow_conversion_factor=0.95,
        outflow_conversion_factor=0.95

    )

    return bs


def create_pv_plant_time_series(latitude: float, longitude: float,
                                jahreszeit: Jahreszeit, peakpower_in_kW: float,
                                base_sim_interval_in_min: int,
                                sim_sow: int,
                                surface_tilt: float = 0, surface_azimuth: float = 0,
                                pvtechchoice: str = 'crystSi',
                                # Start of week (0 for monday, 1 for tuesday, 6 for sunday)
                                ) -> pd.Series:
    """

    Calculates a time series with given parameters of the plant, using the PVGIS API.
    The time series has the right length and units for our simulation and is resampled to the right interval.

    Parameters
    ----------
    latitude: Latitude gem. (ISO 19115), siehe https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html
    longitude: Longitude gem ISO 19115, siehe https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html
    jahreszeit: Jahreszeit (Sommer, Winter, Übergang) für welche die typische Woche der PV-Leistung zurückgegeben werden soll
    peakpower_in_kW: Nominal power of PV system in kWp
    base_sim_interval_in_min: Interval that our base simulation runs on.
    sim_sow: Start of week (0 for monday, 1 for tuesday, 6 for sunday) in the simulation
    surface_tilt: Tilt angle from horizontal plane
    surface_azimuth: Orientation (azimuth angle) of the plane, see https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html
    get_pvgis_hourly: PV Technology, see get_pvgis_hourly Function call


    Returns
    -------
    pd.Series .. Time series in the right format for the simulation
    """

    # The get_pvgis_hourly call below has more options for more detailed calculations, see its documentation. E. g.,
    # one could specify there whether the PV plant is free-standing or building-integrated.

    # Unfortunately, we can currently only retrieve weather data from 2005 up to 2015 with the PVGIS Version 5.1 (default for pvlib).
    # v5.2 supports up to 2020 but I currently have not gotten it to work.
    # We average the values over the years to get a typical year.
    try:
        w1 = pvlib.iotools.get_pvgis_hourly(latitude, longitude, start=2005, end=2016, components=True,
                                            surface_tilt=surface_tilt, surface_azimuth=surface_azimuth,
                                            outputformat='json',
                                            pvcalculation=True,
                                            peakpower=peakpower_in_kW,
                                            pvtechchoice=pvtechchoice)  # , raddatabase='PVGIS-SARAH')
    except requests.exceptions.ConnectionError:
        raise ConnectionError("Could not connect to the PVGIS server. Please check your internet connection.")
    except requests.exceptions.ReadTimeout:
        raise ConnectionError(
            "Get a timeout while connecting to the PVGIS server. Please check your internet connection.")

    # Oftentimes we get values for times like 0:11, 1:11, 2:11, ... 22:11, 23:11, therefore we need to remove the minutes
    # For some reason we need to do this BEFORE we do the timezone conversion, otherwise it will crash

    # Step 1: Determine the minutes in the first entry of the index
    minute_offset = w1[0].index.minute[0]

    # Step 2: Adjust all datetimes in the dataframe
    if minute_offset < 30:
        # Subtract the minute offset from all datetime indices
        new_index = w1[0].index.floor('h')
    else:
        # Subtract the minute offset and then round up to the next hour
        new_index = w1[0].index.ceil('h')

    # Assign the new index to the dataframe
    w1[0].index = new_index

    # As the PVGIS data is in UTC, we need to convert it to the local timezone
    # Summer time seems to be automatically considered by the pvlib library, so e.g. for Berlin, the peak power is then
    # usually correctly at 13:00 in summer and 12:00 in winter

    # Retrieve time zone from latitude and longitude
    tf = TimezoneFinder()
    tz = tf.timezone_at(lng=longitude, lat=latitude)  # e.g. 'Europe/Berlin'
    print(tz)
    w1[0].index = w1[0].index.tz_convert(tz)

    # Mittelung der Werte
    # Durch die verwendete Weise umgehe ich auch Probleme mit dem 29. Februar, was jedoch unklar ist was abgeht ist bei Sommer-/Winterzeit Wechsel (trotzdem den Offset nochmal betrachten, glaube er wird durch die Mittelung "aufgelöst"
    # auch unproblematisch ist jetzt, wenn der 1. Januar bspw. erst um 1:00 beginnt (wenn normalisierung auf Volle Stunden oben ein aufrunden ergab)

    df = w1[0].rename(columns={'P': 'value'})

    # We need to scale the results to kW as get_pvgis_hourly returns values in W (see https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html)
    df['value'] = df['value'] / 1000

    months = typical_months(jahreszeit)

    # Get typical week but take average without differentiating between the day of the week (method 'weather_avg') => start_of_week has no effect on result
    ts_resampled_values = helperFunctions.typical_week(df, months, sim_sow, base_sim_interval_in_min,
                                                       method='weather_avg')

    return ts_resampled_values


def __import_bdew_values__(kundengruppe: BDEW_Kundengruppe, tagesart: BDEW_Tagesart,
                           jahreszeit: Jahreszeit, annual_consumption: float) -> list[float]:
    """
    Based on the Kundengruppe, Tagesart and Jahreszeit, this function imports the BDEW values from the Excel file
    and returns the values as a list containing the power values in [W] for each 15 mins in this day (0:00, 0:15, .., 23:45)

    annual_consumption: Annual (electric) consumption of the micro grid in kWh/a

    """

    # Importing the BDEW values by selecting Kundengruppe as Worksheet, then selecting the correct three columns based on the Jahreszeit.

    if jahreszeit == Jahreszeit.WINTER:
        cols = "A,B:D"
    elif jahreszeit == Jahreszeit.SOMMER:
        cols = "A,E:G"
    else:  # Übergangszeit
        cols = "A,H:J"

    # define file path of bdew_data xls data
    datapath = os.path.join(os.path.dirname(__file__), "bdew_data")
    file_path = os.path.join(datapath, "repraesentative_profile_vdew.xls")

    # Check if the BDEW file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Could not find the XLS file containing the BDEW load profiles at {file_path}. Please downloading it from the BDEW website first (e.g. using the download_bdew.py script).")

    werte_df = pd.read_excel(file_path, sheet_name=kundengruppe.value, index_col=0,
                             skiprows=2, usecols=cols, nrows=96)

    # Werktag, Samstag, Sonntag ursprünglich doppelt, so rename them
    werte_df.rename(columns={'Werktag.1': 'Werktag', 'Samstag.1': 'Samstag', 'Sonntag.1': 'Sonntag',
                             'Werktag.2': 'Werktag', 'Samstag.2': 'Samstag', 'Sonntag.2': 'Sonntag'}, inplace=True)

    # Sort by time HH:MM as the rows in the excel are 0:15, 0:30, .., 23:30, 23:45, 0:00; but I want 0:00 to be at the start
    werte_df.sort_index(inplace=True)

    # Scaling Factor: As the BDEW values are based off an annual consumption of 1000 kWh, we need to scale the values
    # Additional division by 1000 is required as the values in the excel are in W, not kW
    scale_factor = annual_consumption / 1e6
    power_values_nom = werte_df.loc[:, tagesart.value].values
    power_values_scaled = power_values_nom * scale_factor

    return power_values_scaled
