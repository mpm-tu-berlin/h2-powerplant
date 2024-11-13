# -*- coding: utf-8 -*-

"""

Originally based on the eflips TCO (https://github.com/mpm-tu-berlin/eflips/blob/main/eflips/tco.py).
Modified to fit the needs of the H2Powerplant, as well as excessively extended with new plots.

"""


from typing import Literal

import pandas as pd
import numpy as np
import math
import os
from matplotlib import pyplot as plt
import plotly.express as px
import plotly.graph_objects as go

# Disable MathJax for Kaleido so that we will not get the "loading MathJax..." message on our PDF exports
import plotly.io as pio
from plotly.subplots import make_subplots

pio.kaleido.scope.mathjax = None


# Color Mappings to have the same colors for the categories in all plots
h2pp_color_mappings = {
                    "Elektrolyseur": px.colors.qualitative.Plotly[0],
                    "Brennstoffzelle": px.colors.qualitative.Plotly[1],
                    "Tank_LP": px.colors.qualitative.Plotly[3],
                    "Batterie": px.colors.qualitative.Plotly[3],
                    "HRS_Infrastruktur": px.colors.qualitative.Plotly[2],
                    "Electricity_Buy": px.colors.qualitative.Plotly[9],
                    "OMC_EL_BZ_LPTank": px.colors.qualitative.Plotly[6],
                    "OMC_HRS_Infra": px.colors.qualitative.Plotly[8],
                    "H2_Buy": px.colors.qualitative.Plotly[5],
                    "Electricity_Sell": px.colors.qualitative.Plotly[4],
                    "Heat_Savings": px.colors.qualitative.Plotly[7],
                }

h2pp_groupings = {
                'OMC_EL_BZ_LPTank': ['OMC_Elektrolyseur', 'OMC_Brennstoffzelle', 'OMC_Tank_LP'],
                'HRS_Infrastruktur': ['Cooling', 'Dispenser', 'Compressor', 'Tank_HP'],
                'OMC_HRS_Infra': ['OMC_Cooling', 'OMC_Dispenser', 'OMC_Compressor', 'OMC_Tank_HP'],
            }
def create_h2pp_overview_dict(cost_data):
    """
    Creates a dictionary with the overview of the cost data for the TCO Object creation / plots
    cost_data is the dict that is also used for TCO creation...
    """
    overview_dict = {}
    for cost_type in cost_data.keys():
        for component in cost_data[cost_type].keys():
            overview_dict[component] = [component]


    for grouping in h2pp_groupings:
        overview_dict[grouping] = h2pp_groupings[grouping]
        # Delete The keys that belong to the grouping (they are already in the grouping)
        for key in h2pp_groupings[grouping]:
            if key in overview_dict:
                del overview_dict[key]

    return overview_dict


class TCO:
    """
    TCO model with dynamic costing; Net present value (Kapitalwertmethode)

    DJ + PB
    """

    def __init__(self, cost_data, start_year, project_duration, i_discount,
                 repeat_procurements, use_salvage_value=False, i_capital=0,
                 annualise=False, base_year=None, production_data=None,
                 **kwargs):
        """Initialise TCO calculation. cost_data must be a dict of the
        following form (example):

        cost_data = {
            'CAPEX': {
                'vehicle': {
                    'escalation':
                        dict([(year, 0.02) for year in
                              range(2015, 2030)]),
                    'escalation_type': 'compound',
                    'unit_cost': 450000,  # €
                    'base_year': 2015,
                    'quantity': 35,
                    'depreciation_period': 10,
                    'salvage_value': 'linear'
                },
                'battery': {
                    'escalation':
                        dict([(year, -0.08) for year in
                              range(2015, 2021)]
                             + [(year, -0.04) for year in
                                range(2021, 2030)]),
                    'escalation_type': 'linear',
                    'unit_cost': 1200,  # €/kWh
                    'base_year': 2015,
                    'quantity': 35 * 180,  # kWh
                    'depreciation_period': 6,
                    'salvage_value': 'linear'
                }
            },
            'OPEX': {
                'electricity': {
                    'escalation':
                        dict([(year, 0.03) for year in
                              range(2015, 2030)]),
                    'unit_cost': 0.015,  # €/kWh
                    'base_year': 2015,
                    'quantity': 2.5e6  # kWh/a
                }
            }
        }

        The keys on the first level MUST be 'CAPEX' and 'OPEX' and none of them
        may be omitted. Each category can include any number of cost components
        ('vehicle' etc.).

        'escalation' must be a dict with the following syntax:
            keys:
                all years covered by the project duration as well as all years
                between base year and project start or end (required for cost
                adjustments)
            values:
                price escalation from previous to current year

        'escalation_type' must be 'compound' or 'linear': determines how the
            value escalation is performed (if escalation_type is missing,
           'compound' is the default)
            'compound': from previous to current year
            'linear': based on first year

        'unit_cost': unit cost of the specified component at the time
            specified by 'base_year'.

        'quantity':
            for CAPEX: quantity of investment object (e.g., 35 vehicles)
            for OPEX: yearly quantity (e.g., energy consumption)

        'depreciation_period': = component lifetime. Only required
            for CAPEX.

        'salvage_value':
            determination of the salvage value at the end of the period;
            if deprecation period is longer than end of project duration
            string:'linear', 'arithm-degres' or geometr-degres
            or number: (10000)
            or string: 'adjust_sum' --> to be used only with annualised method


        Other positional arguments:

        i_discount: discount rate (Kalkulationszinssatz)

        repeat_procurements: boolean specifying whether or not to model
        repeated procurements of components where
        depreciation_period < project_duration.
        If this is set to False, the project duration MUST be set
        to the SHORTEST depreciation_period, otherwise
        the results will be incorrect.


        Keyword arguments:

        use_salvage_value:
            boolean; True: subtract the salvage value at the end of the period
            according to 'salvage_value'; if False: salvageValue = 0

        i_capital: interest rate for the lended money (WACC)
            if set to 0 --> capital is not lended
            else capital is lended and annualise must be set to True

        annualise: boolean; if True: CAPEX will be divided into equal
                   yearly sums; if False, i_capital is automatically set to
                   zero (= only own capital is used)

        base_year: Year for which all currency will be adjusted. If None,
            defaults to start_year.

        production_data: Optional dict with annual production volumes by
        category, e.g.:
            production_data = {'fleetMileage_productive': 32e6,
                              'fleetMileage_total': 40e6}
            If specified, NPV values can be determined per unit production
            volume using sumCashFlows_NPV_spec() and npv_total_spec().

        kwargs:
             overview_dict: dict with summary for stacked bar plot
            (only keys are plotted)
            overview_train = {
            'Fahrzeug': ['Fahrzeug', 'Batterie', 'Fahrzeug_Instandhaltung'],
            'Infrastruktur': ['Energieinfrastruktur',
                              'Energieinfrastruktur_Instandhaltung'],
            'Energie': ['Energie']
            }
        """
        self._cost_data = cost_data
        self._production_data = production_data
        self._start_year = start_year
        self._project_duration = project_duration
        self._i_discount = i_discount
        self._repeat_procurements = repeat_procurements
        self._use_salvage_value = use_salvage_value
        self._i_capital = i_capital
        self._annualise = annualise
        self._base_year = base_year if base_year else start_year
        if 'overview_dict' in kwargs:
            self._overview_dict = kwargs['overview_dict']
            self._sum_cash_flows_npv_overview = {}
        self._calculate()

    @staticmethod
    def discount_factor(interest, duration):
        return 1 / (1 + interest) ** duration

    @staticmethod
    def crf(interest, duration):
        """capital recovery factor"""
        return (interest * (1 + interest) ** duration)/ \
               ((1 + interest) ** duration - 1)

    def _calculate(self):
        self._end_year = self._start_year + self._project_duration - 1
        self._cash_flows = {}
        self._cash_flows_npv = {}
        self._sum_cash_flows_npv_not_adjusted = {}
        self._sum_cash_flows_npv = {}
        self._sum_cash_flows_npv_spec = {}
        self._npv_total_spec = {}
        self._df_nominal = pd.DataFrame()
        self._df_npv = pd.DataFrame()

        # Determine unit cost for all years for which escalation data
        # is supplied:
        self._unit_cost = {}
        for cost_type in self._cost_data.keys():
            for component, params in self._cost_data[cost_type].items():
                self._unit_cost.update({component: {}})
                escalation_type = params['escalation_type'] if \
                    'escalation_type' in params else 'compound'
                for year in params['escalation'].keys():
                    cost = params['unit_cost']
                    increment = 1 if year >= params['base_year'] else -1
                    for t in range(params['base_year'] + increment,
                                   year + increment,
                                   increment):
                        shift = 1 if increment == -1 else 0
                        if escalation_type == 'compound':
                            cost = cost * (1 + params['escalation'][
                                t + shift]) ** increment
                        elif escalation_type == 'linear':
                            factor = params['unit_cost'] * params['escalation'][
                                t + shift]
                            cost = cost + factor * increment

                        elif escalation_type == 'custom_per_year_jc':
                            # TODO schöner machen, das ist ein simpler und schmutziger workaround!!
                            # Hack, um manuell für jedes Jahr Kosten berechnen zu können.
                            # kosten werden ausschließlich aus "escalation" bezogen,
                            # quantity MUSS im TCO dict auf 1 gesetzt werden, da unten damit noch multipliziert wird,
                            # unit_cost dürfte egal sein. bspw. es auf 0 setzen, dann sehen wir die fehler viel leichter, weil es dann eher komplett fehlen würde als falsche Werte zu haben
                            cost = params['escalation'][t + shift]

                        else:
                            ValueError('Please select "compound" or "linear" '
                                       'as escalation type!')
                    self._unit_cost[component].update({year: cost})

        # CAPEX
        self._capex = {}
        use_durations = {}
        self._cash_flows.update({'CAPEX': {}})
        # helper list for 'adjust_sum' salvage (all components must be true)
        adjust_sum_list = []
        for component, params in self._cost_data['CAPEX'].items():
            if not int(params['depreciation_period']) \
                   == params['depreciation_period']:
                raise ValueError('depreciation_period must be supplied in '
                                 'whole years!')
            # Make sure depreciation period is an integer:
            params['depreciation_period'] = int(params['depreciation_period'])
            self._capex.update({component: {}})
            self._cash_flows['CAPEX'].update({component: {}})

            # Determine total usage period (including all replacements)
            if self._repeat_procurements:
                # Number of procurements during project; at least 1:
                num_procurements = math.ceil(self._project_duration /
                                            params['depreciation_period'])
            else:
                # Component only procured once at beginning of project:
                num_procurements = 1

            use_durations.update({component: num_procurements
                                            * params['depreciation_period']})

            # Years of procurement
            procurement_years = \
                [self._start_year + i * params['depreciation_period']
                 for i in range(0, num_procurements)]

            # Investment per procurement
            for year in procurement_years:
                self._capex[component].update(
                    {year: self._unit_cost[component][year] \
                           * params['quantity']})

            if self._use_salvage_value:
                salvage_value = \
                    self._cost_data['CAPEX'][component]['salvage_value']
                last_replacement_value = \
                    self._capex[component][procurement_years[-1]]
                if salvage_value == 'adjust_sum':
                    # sanity check
                    if self._annualise is not True:
                        ValueError("To use 'adjust_sum', "
                                   "annulise must be True")
                    # component has 'adjust_sum' as salvage
                    adjust_sum_list.append(True)
                    salvage = 0
                elif salvage_value == 'linear':
                    one_year_value = \
                        last_replacement_value \
                        / self._cost_data['CAPEX'][component][
                            'depreciation_period']
                    years_not_used = \
                        use_durations[component] - self._project_duration
                    salvage = - one_year_value * years_not_used
                    adjust_sum_list.append(False)
                elif (isinstance(salvage_value, int) or
                      isinstance(salvage_value, float)):
                    salvage = - salvage_value
                    adjust_sum_list.append(False)
                else:  # arithmetisch-degressiv or geometrisch-degressiv
                    # not implemented
                    salvage = 0
                    adjust_sum_list.append(False)
                if salvage != 0:
                    self._capex[component].update(
                        {self._end_year: salvage})

            # cashflow CAPEX
            if self._annualise:
                if self._i_capital != 0:  # if lended capital
                    # Annualised investments if capital is lended
                    crf = \
                        self.crf(self._i_capital,
                                 params['depreciation_period'])
                    for year in procurement_years:
                        invest = self._capex[component][year]
                        for t in range(year,
                                       year + params['depreciation_period']):
                            self._cash_flows['CAPEX'][component].update(
                                {t: invest * crf})
                else:
                    # capital not lended (no interest --> i_capital = 0;
                    # linear depreciation)
                    for year in procurement_years:
                        invest = self._capex[component][year]
                        for t in range(year,
                                       year + params['depreciation_period']):
                            self._cash_flows['CAPEX'][component].update(
                                {t: invest / params['depreciation_period']})
            else:  # do not annualise (i_capital = 0)
                for t in range(self._base_year, self._end_year):
                    invest = \
                        self._capex[component][
                            t] if t in procurement_years else 0
                    self._cash_flows['CAPEX'][component].update({t: invest})
                if self._end_year in self._capex[component]:
                    self._cash_flows['CAPEX'][component].update(
                        {self._end_year: self._capex[component][self._end_year]})
        # OPEX
        self._cash_flows.update({'OPEX': {}})
        for component, params in self._cost_data['OPEX'].items():
            self._cash_flows['OPEX'].update({component: {}})
            for year in range(self._start_year, self._end_year + 1):
                self._cash_flows['OPEX'][component].update(
                    {year: self._unit_cost[component][year]
                           * params['quantity']})

        # Net present values
        for cost_type in self._cash_flows.keys():
            self._cash_flows_npv.update({cost_type: {}})
            for component, params in self._cash_flows[cost_type].items():
                self._cash_flows_npv[cost_type].update({component: {}})
                for year, cash_flow in params.items():
                    npv = \
                        cash_flow * self.discount_factor(self._i_discount,
                                                        year - self._base_year)
                    self._cash_flows_npv[cost_type][component].update(
                        {year: npv})

        # NPV sums
        # check if any, but not all salvage values are 'adjust_sum'
        if all(adjust_sum_list) is False and any(adjust_sum_list) is True:
            raise ValueError("Salvage values for the CAPEX components "
                             "are mixed! If you want to use 'adjust_sum', "
                             "all components must have salvage value "
                             "'adjust_sum'.")
        # if 'adjust_sum' is True for all CAPEX components
        elif all(adjust_sum_list):
            for cost_type in self._cash_flows_npv.keys():
                self._sum_cash_flows_npv_not_adjusted.update({cost_type: {}})
                for component, params in \
                        self._cash_flows_npv[cost_type].items():
                    self._sum_cash_flows_npv_not_adjusted[cost_type].update(
                        {component: 0})
                    for year, cash_flow in params.items():
                        self._sum_cash_flows_npv_not_adjusted[cost_type][
                            component] += cash_flow

            # Adjust NPV sums for project length (only for CAPEX)
            self._sum_cash_flows_npv.update({'CAPEX': {}})
            for component, val in \
                    self._sum_cash_flows_npv_not_adjusted['CAPEX'].items():
                npv_adjusted = self._project_duration / use_durations[
                    component] * val
                self._sum_cash_flows_npv['CAPEX'].update(
                    {component: npv_adjusted})

            self._sum_cash_flows_npv.update(
                {'OPEX': self._sum_cash_flows_npv_not_adjusted['OPEX']})

        else:  # salvageValues are not 'adjust_sum'
            for cost_type in self._cash_flows_npv.keys():
                self._sum_cash_flows_npv.update({cost_type: {}})
                for component, params in \
                        self._cash_flows_npv[cost_type].items():
                    self._sum_cash_flows_npv[cost_type].update({component: 0})
                    for year, cash_flow in params.items():
                        self._sum_cash_flows_npv[cost_type][component] \
                            += cash_flow

        if hasattr(self, '_overview_dict'):
            for costType_new, items in self._overview_dict.items():
                self._sum_cash_flows_npv_overview.update({costType_new: 0})
                for item in items:  # component in _sumCashFlows_NPV
                    for cost_type in self._sum_cash_flows_npv.keys():
                        for component, cash_flow in \
                                self._sum_cash_flows_npv[cost_type].items():
                            if component == item:
                                self._sum_cash_flows_npv_overview[costType_new]\
                                    += cash_flow

        # Determine total project NPV
        self._npv_total = 0
        for cost_type in self._sum_cash_flows_npv.keys():
            for component, val in self._sum_cash_flows_npv[cost_type].items():
                self._npv_total += val

        # Determine specific NPV values
        if self._production_data is not None:
            for product, prod_volume in self._production_data.items():
                self._sum_cash_flows_npv_spec.update({product: {}})
                self._npv_total_spec.update(
                    {product: self._npv_total / (prod_volume
                                                 * self._project_duration)})
                for cost_type in self._sum_cash_flows_npv.keys():
                    self._sum_cash_flows_npv_spec[product].update({cost_type: {}})
                    for component, npv_sum in \
                            self._sum_cash_flows_npv[cost_type].items():
                        self._sum_cash_flows_npv_spec[product][cost_type].update(
                            {component: npv_sum / (prod_volume *
                                                   self._project_duration)}
                        )
        else:
            self._sum_cash_flows_npv_spec = None
            self._npv_total_spec = None

        # dataframes
        for cost_type in self._cash_flows.keys():
            for component, params in self._cash_flows[cost_type].items():
                temp_df_nom = \
                    pd.DataFrame.from_dict(
                        self._cash_flows[cost_type][component],
                        orient='index', columns=[component])
                self._df_nominal = pd.concat([self._df_nominal, temp_df_nom],
                                             axis=1)
        for cost_type in self._cash_flows_npv.keys():
            for component, params in self._cash_flows_npv[cost_type].items():
                temp_df_npv = pd.DataFrame.from_dict(
                    self._cash_flows_npv[cost_type][component],
                    orient='index', columns=[component])
                self._df_npv = pd.concat([self._df_npv, temp_df_npv], axis=1)

    # Lots of silly getters and setters to ensure proper updating of data
    # when parameters are changed
    @property
    def cost_data(self):
        return self._cost_data

    @cost_data.setter
    def cost_data(self, new_val):
        self._cost_data = new_val
        self._calculate()

    @property
    def production_data(self):
        return self._production_data

    @production_data.setter
    def production_data(self, new_val):
        self._production_data = new_val
        self._calculate()

    @property
    def start_year(self):
        return self._start_year

    @start_year.setter
    def start_year(self, new_val):
        self._start_year = new_val
        self._calculate()

    @property
    def project_duration(self):
        return self._project_duration

    @project_duration.setter
    def project_duration(self, new_val):
        self._project_duration = new_val
        self._calculate()

    @property
    def i_discount(self):
        return self._i_discount

    @i_discount.setter
    def i_discount(self, new_val):
        self._i_discount = new_val
        self._calculate()

    @property
    def i_capital(self):
        return self._i_capital

    @i_capital.setter
    def i_capital(self, new_val):
        self._i_capital = new_val
        self._calculate()

    @property
    def repeat_procurements(self):
        return self._repeat_procurements

    @repeat_procurements.setter
    def repeat_procurements(self, new_val):
        self._repeat_procurements = new_val
        self._calculate()

    @property
    def base_year(self):
        return self._base_year

    @base_year.setter
    def base_year(self, new_val):
        self._base_year = new_val
        self._calculate()

    @property
    def cash_flows(self):
        return self._cash_flows

    @property
    def cash_flows_npv(self):
        return self._cash_flows_npv

    @property
    def sum_cash_flows_npv(self):
        return self._sum_cash_flows_npv

    @property
    def sum_cash_flows_npv_spec(self):
        return self._sum_cash_flows_npv_spec

    @property
    def sum_cash_flows_npv_overview(self):
        if hasattr(self, "_sum_cash_flows_npv_overview"):
            return self._sum_cash_flows_npv_overview

    @property
    def npv_total(self):
        return self._npv_total

    @property
    def npv_total_spec(self):
        return self._npv_total_spec

    @property
    def df_nominal(self):
        return self._df_nominal

    @property
    def df_NPV(self):
        return self._df_npv

    # --------PLOT FUNCTIONS---------------------

    def plot_unit_cost_development(self, unit, title='unit name',
                                   unit_value='€', plot_percentage=False,
                                   saveplot=False,
                                   filename='unit_cost_development', **kwargs):
        # TODO this is eflips-tco legacy code, never used in the project, only left in for now
        """plots the time development of a unit cost
        kwargs:
            figsize: sets the size of the figure"""
        fig, ax1 = plt.subplots()
        plt.title(title)
        ax1.set_xlabel(xlabel='Jahr', fontsize=10)
        if plot_percentage:
            ax1.set_ylabel(ylabel='Kosten pro Einheit [%]', fontsize=10)
        else:
            ax1.set_ylabel(ylabel='Kosten pro Einheit [' + unit_value + ']',
                           fontsize=10)
        # sorted by key, return a list of tuples
        lists = sorted(self._unit_cost[unit].items())
        x, y = zip(*lists)  # unpack a list of pairs into two tuples
        if plot_percentage:
            base = y[0]
            y = [val / base * 100 for val in y]
        plt.plot(x, y)
        if 'figsize' in kwargs:
            fig.set_size_inches(kwargs['figsize'], forward=True)
        plt.tight_layout()
        if saveplot:
            plt.savefig(filename + '.png', dpi=200)

    def plot_stacked_bar_over_period_cumulated(self, saveplot=False,
                                               xlimit=None,
                                               filename='stacked_bar_over_'
                                                        'period_cumulated',
                                               **kwargs):
        # TODO this is eflips-tco legacy code, never used in the project, only left in for now
        fig, ax1 = plt.subplots()
        ax1.set_xlabel(xlabel='Jahr', fontsize=10)
        ax1.set_ylabel(ylabel='Mio. €', fontsize=10)
        xlim = [self._start_year, self._end_year] if xlimit is None else xlimit
        if 'colors' in kwargs.keys():
            colors = kwargs['colors']
        else:
            colormap = plt.get_cmap('Set3')
            colors = colormap.colors
        (self._df_npv.cumsum() / 1000000).plot.bar(stacked=True, ax=ax1,
                                                   xlim=xlim,
                                                   color=colors
                                                   )
        ax1.legend(loc='upper right',
                   fancybox=True, fontsize=8)
        plt.tight_layout()
        plt.show()
        if saveplot:
            plt.savefig(filename + '.png', dpi=200)

    def plot_stacked_bar_over_period(self, include_title=False):
        """
        Plottet die in jedem Jahr anfallenden Kosten (NPV) für die verschiedenen Komponenten als gestapelte Balken.
        In y-Richtung werden die Kosten in Mio. € dargestellt, in x-Richtung die jeweiligen Jahre des Projektzeitraums.
        Ausgaben werden in die >0 Richtung gestapelt, Einnahmen in die <0 Richtung.
        Darstellung der einzelnen Komponenten oder -gruppen (Gruppierung gem. Festlegung in h2pp_groupings oben im tco.py) mit unterschiedlichen Farben.

        @param include_title: bool, gibt an, ob der Plot mit einem Titel versehen werden soll
        @return: Plotly figure
        """

        # Transformiere das DataFrame, sodass die Jahre die Zeilen und die Typen die Spalten sind
        # Melt the DataFrame in order to perform bar plot
        # melting turns the columns into rows, see https://pandas.pydata.org/docs/reference/api/pandas.melt.html
        the_df = self.df_NPV.copy(deep=True)
        the_df['year'] = the_df.index
        the_df = pd.melt(the_df, id_vars='year', var_name='type', value_name='value')

        # the_df now is a dataframe with columns 'year', 'type', 'value'
        # for better readibility, we combine some of the types together and calculate their total value (for each of the years)
        # the trick is as follows: we first rename the types we want to combine, then we group by year and type and sum the values

        for key in h2pp_groupings.keys():
            ziel_row = key
            types_to_combine = h2pp_groupings[key]

            for typ in types_to_combine:
                the_df.loc[the_df['type'] == typ, 'type'] = ziel_row

        # combining the rows with same (year, type) and summing their values
        the_df = the_df.groupby(['year', 'type']).sum().reset_index()

        # alles auf Mio. € umrechnen
        the_df['value'] = the_df['value'] / 1000000

        total_npv_in_mio = np.round(self.npv_total / 1000000, 2)

        # füge die Gesamtkosten je type hinzu:
        # Calculate the total cost for each type
        totals = the_df.groupby('type')['value'].sum().reset_index()

        # Create a dictionary mapping each type to its total cost
        totals_dict = totals.set_index('type')['value'].to_dict()

        # Add hover information with total costs for each type
        the_df['the_hover_text'] = the_df.apply(
            lambda
                row: f"Year: {row['year']}<br>Cost: {row['value']} Mio. €<br>Total {row['type']}: {totals_dict[row['type']]:,.2f} Mio. €",
            axis=1
        )

        # Barmode "relative" to stack bars on top of eachother like in "stacked", but with positive values above the x-axis and negative values below
        # The manual setting of colors requires that every type is assigned a color, otherwise, multiple types might have the same color
        # as we only have 10 different colors in the color scheme, we need to ensure that the types we dont need are not passed to the TCO cost data dict, e.g. Battery in the H2PP case, or Fuel Cell in the Battery case.
        fig_plotly = px.bar(the_df, barmode='relative',
                            x="year", y="value", color="type",
                            title="Total Cost of Ownership: " + str(total_npv_in_mio) + " Mio. €" if include_title else None,
                            labels={"value": "NPV in Mio. €", "year": "Jahr", "type": "Komponente"},
                            hover_name="the_hover_text",
                            color_discrete_map=h2pp_color_mappings
                            )


        # Füge eine dicke schwarze Linie bei y=0 hinzu
        fig_plotly.add_shape(
            type="line",
            x0=the_df['year'].min(), x1=the_df['year'].max(),
            y0=0, y1=0,
            line=dict(color="black", width=4, dash='dash')  # Farbe Schwarz und Breite 4
        )

        fig_plotly.update_layout(
            height=800,
            # analog zu den Winter/Sommer/Übergang Plots damit die anderen Tabs nicht kleiner werden wenn das hier geplottet
        )
        # x-Achsenbeschriftung (Jahreszahlen) um 45 Grad drehen
        fig_plotly.update_xaxes(tickangle=-45)

        return fig_plotly

    def plot_stacked_line_over_period_cumulated(self, save_plot=False,
                                                xlimit=None, file_format=".png",
                                                **kwargs):
        # TODO this is eflips-tco legacy code, never used in the project, only left in for now
        fig, ax1 = plt.subplots()
        ax1.set_xlabel(xlabel='Jahr', fontsize=10)
        ax1.set_ylabel(ylabel='Mio. €', fontsize=10)
        xlim = [self._start_year, self._end_year] if xlimit is None else xlimit
        if 'colors' in kwargs.keys():
            colors = kwargs['colors']
        else:
            colormap = plt.get_cmap('Set3')
            colors = colormap.colors
        (self._df_npv.cumsum() / 1000000).plot.area(ax=ax1, stacked=True,
                                                    xlim=xlim,
                                                    color=colors
                                                    )
        ax1.legend(loc='upper right',
                   fancybox=True, fontsize=8)
        plt.tight_layout()
        plt.show()
        if save_plot:
            f_name_no_format = kwargs['file_name'] if 'file_name' in kwargs.keys() \
                else 'stacked_line_over_period_cumulated',
            f_name = f_name_no_format + file_format
            if 'file_path' in kwargs.keys():
                path = kwargs['file_path']
                plt.savefig(os.path.join(path, f_name), dpi=300)
                print("Plot '%s' saved in %s" % (f_name, path))
            else:
                plt.savefig(f_name, dpi=300)
                print("Plot %s saved." % f_name)
        if 'show_plot' in kwargs.keys():
            plt.show() if kwargs['show_plot'] is True else plt.close()
        else:
            plt.close()

    def plot_sum_stacked(self, xlabel='Triebzug', plot_as_summary=False,
                         saveplot=False, filename='sum_stacked',
                         annotate=False, **kwargs):
        # TODO this is eflips-tco legacy code, never used in the project, only left in for now
        """plot stacked NPV sum;
            kwargs:
            colors: dict with components as keys and colors as value
        """
        fig, ax1 = plt.subplots()
        ax1.set_xlabel(xlabel=xlabel, fontsize=10)
        ax1.set_ylabel(ylabel='Mio. €', fontsize=10)
        if 'colors' in kwargs.keys():
            colors = kwargs['colors']
        else:
            colormap = plt.get_cmap('tab20c')
            colors = {'Fahrzeug': colormap(5),  # orange
                      'Batterie': colormap(9),  # green
                      'PowerPack': colormap(9),  # green
                      'Energieinfrastruktur': colormap(1),  # blue
                      'Infrastruktur': colormap(1),  # blue
                      'Fahrzeug_Instandhaltung': colormap(7),  # light orange
                      # light blue
                      'Energieinfrastruktur_Instandhaltung': colormap(3),
                      'Energie': colormap(17)}  # grey
        bottom = 0
        if plot_as_summary is False:
            for costType in self.sum_cash_flows_npv.keys():
                for component, value in \
                        self.sum_cash_flows_npv[costType].items():
                    plt.bar(0, value / 1000000, width=0.8, bottom=bottom,
                            color=colors[component],
                            label=component.replace('_', ': '))
                    bottom += value / 1000000
        else:
            if self._sum_cashflows_npv_overview:
                for costType, value in self._sum_cashflows_npv_overview.items():
                    plt.bar(0, value / 1000000, width=0.8, bottom=bottom,
                            color=colors[costType],
                            label=costType.replace('_', ': '))
                    bottom += value / 1000000
        if annotate:
            ax1.annotate("{:0.1f}".format(bottom),
                         (0, bottom),
                         xytext=(0, 5),
                         textcoords='offset pixels',
                         fontsize=8,
                         horizontalalignment='center',
                         verticalalignment='bottom'
                         )
        plt.xticks([])
        ax1.set(xlim=[-2, 2])
        handles, labels = ax1.get_legend_handles_labels()
        ax1.legend(handles[::-1], labels[::-1], loc='upper right',
                   fancybox=True, fontsize=8)
        plt.tight_layout()
        plt.show()
        if saveplot:
            plt.savefig(filename + '.png', dpi=200)

    def plot_sum_separated(self, plot_percentage=False, saveplot=False,
                           filename='sum_separated', annotate=False):
        # TODO this is eflips-tco legacy code, never used in the project, only left in for now
        fig, ax1 = plt.subplots()
        if plot_percentage is False:
            ax1.set_ylabel(ylabel='Mio. €', fontsize=10)
            (self._df_npv.sum() / 1000000).plot.bar(ax=ax1)
            if annotate:
                for ind, k in enumerate(self._df_npv.sum().index):
                    ax1.annotate("{:0.1f}".format(self._df_npv.sum()[k]),
                                 (ind, (self._df_npv.sum()[k]) / 1000000),
                                 xytext=(0, 5),
                                 textcoords='offset pixels',
                                 fontsize=8,
                                 horizontalalignment='center',
                                 verticalalignment='bottom'
                                 )
        else:
            ax1.set_ylabel(ylabel='Prozent von NPV [%]', fontsize=10)
            ax1.set(xlim=[0, 40])
            ans = self._df_npv.sum() / self._df_npv.sum().sum() * 100
            ans.plot.bar(ax=ax1)
            if annotate:
                for ind, k in enumerate(ans.index):
                    ax1.annotate("{:0.1f}".format(ans[k]) + "%",
                                 (ind, (ans[k])),
                                 xytext=(0, 5),
                                 textcoords='offset pixels',
                                 fontsize=8,
                                 horizontalalignment='center',
                                 verticalalignment='bottom'
                                 )
        plt.tick_params(
            axis='x',
            which='both',
            labelsize=8)
        plt.show()
        plt.tight_layout()
        if saveplot:
            plt.savefig(filename + '.png', dpi=200)


def plot_donut_tco_fractions(list_of_tcos, list_of_hover_labels, list_of_short_labels):
    """
    Plot a donut plot of the total costs for each type for each TCO object in the list.
    This only plots the costs, not the revenues(!).
    The list_of_hover_labels and list_of_short_labels should have the same length as list_of_tcos and should contain the labels corresponding to the tco object at the same index.
    :param list_of_tcos: list of TCO objects
    :param list_of_hover_labels:
    :param list_of_short_labels:
    :return: The plotly figure
    """
    number_of_tcos = len(list_of_tcos)
    # Create subplots: use 'domain' type for Pie subplot
    fig = make_subplots(rows=1, cols=number_of_tcos, specs=[[{'type': 'domain'}]*number_of_tcos])
    for i in range(0, number_of_tcos):

        sum_cashflows_overview = list_of_tcos[i].sum_cash_flows_npv_overview

        # Remove the negative values (revenues) from the overview (only plot costs)
        sum_cashflows_overview = {key: value for key, value in sum_cashflows_overview.items() if value > 0}
        labels = []
        values = []
        corresponding_colors = []
        for key, value in sum_cashflows_overview.items():
            labels.append(key)
            values.append(value)
            corresponding_colors.append(h2pp_color_mappings[key]) # TODO error handling falls er den Kostenposten nicht finde / std farbe?

        fig.add_trace(go.Pie(labels=labels, values=values, name=list_of_hover_labels[i], marker_colors=corresponding_colors),
                      1, i+1)

    # Use `hole` to create a donut-like pie chart
    fig.update_traces(hole=.4, hoverinfo="label+percent+name")

    annotations = []
    for i in range(0, number_of_tcos):
        annotations.append(dict(text=list_of_short_labels[i], x=sum(fig.get_subplot(1, i+1).x) / 2, y=0.5, font_size=12, showarrow=False, xanchor="center"))

    fig.update_layout(
        #title_text="Comparison of different TCOs (Only Costs without revenues)",
        # Add annotations in the center of the donut pies.
        annotations=annotations)

    return fig


def plot_multiple_tco_costs_and_revenue_bars(list_of_tcos, list_of_names):
    """
    Plots for each TCO a combined bar (for cost and revenues):
        - one for the costs (all components with > 0 total cost) in positive x direction (stacked bar plot with the components)
        - one for the revenues (all components with < 0 total cost) in negative direction (stacked bar plot with the components)

    :param list_of_tcos: list of TCO objects
    :param list_of_names: list of names for the TCO objects, used as labels in the plot, should have the same length as list_of_tcos and contain the names in the same order
    :return: The plotly figure
    """

    x_npv_values = []
    y_tco_item = []
    color_category = []

    for i in range(0, len(list_of_tcos)):
        tco = list_of_tcos[i]

        # Get the sum of the costs and revenues
        sum_cashflows_overview = tco.sum_cash_flows_npv_overview

        for key, value in sum_cashflows_overview.items():
            x_npv_values.append(value)
            y_tco_item.append(list_of_names[i])
            color_category.append(key)

    # create dataframe from the lists
    df = pd.DataFrame(list(zip(y_tco_item, x_npv_values, color_category)),
               columns =['y_tco_item', 'x_npv_values', 'Komponente'])

    # create the plot
    fig = px.bar(df, x='x_npv_values', y='y_tco_item', color='Komponente', color_discrete_map=h2pp_color_mappings, orientation='h',
                 height=500)

    fig.update_layout(xaxis_title="Kumulierte Anteile am NPV in Mio. €")
    fig.update_layout(yaxis_title="Szenario")


    return fig

def plot_multiple_tco_total_bars(list_of_tcos, list_of_names):
    """
    Plots for each TCO a bar for the total costs (sum of all components) in positive x direction
    (only the end NPV value, no categories)
    This value is the total NPV value of the TCO object, meaning the sum of all costs and revenues.

    :param list_of_tcos: list of TCO objects
    :param list_of_names: list of names for the TCO objects, used as labels in the plot, should have the same length as list_of_tcos and contain the names in the same order
    :return: The plotly figure
    """

    x_npv_values = []
    y_tco_item = []

    for i in range(0, len(list_of_tcos)):
        tco = list_of_tcos[i]
        x_npv_values.append(tco.npv_total)
        y_tco_item.append(list_of_names[i])

    # create dataframe from the lists
    df = pd.DataFrame(list(zip(y_tco_item, x_npv_values)),
               columns =['y_tco_item', 'x_npv_values'])

    # create the plot, with grey bars
    fig = px.bar(df, y='x_npv_values', x='y_tco_item', text='x_npv_values',
                 height=500, width=500, color_discrete_sequence=['grey'])
    fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
    fig.update_layout(xaxis_title="Szenario")
    fig.update_layout(yaxis_title="NPV in Mio. €")

    return fig
