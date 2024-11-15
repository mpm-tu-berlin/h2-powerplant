# -*- coding: utf-8 -*-

"""Module to render an oemof energy model network in a graph.
SPDX-FileCopyrightText: Pierre-Francois Duc <pierre-francois.duc@rl-institut.de>
SPDX-FileCopyrightText: Uwe Krien <krien@uni-bremen.de>
SPDX-FileCopyrightText: Patrik Schönfeldt
SPDX-License-Identifier: MIT

Based on the energy_system_graph.py from oemof-visio
(https://github.com/oemof/oemof-visio/blob/09fca323ff72ccc358e23b1efe1c8e61ce2f1bd0/oemof_visio/energy_system_graph.py),
fixed to work with oemof.solph components that were leading to errors

MIT License

Copyright (c) 2019 oemof developer group, modified 2024 by Jonas Christiansen (TU Berlin, FG MPM)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import logging
import math
import os


try:
    import graphviz
    GRAPHVIZ_MODULE = True
except ModuleNotFoundError:
    GRAPHVIZ_MODULE = False

# Checks if solph is installed
try:
    import oemof.solph
    SOLPH_MODULE = True
except ModuleNotFoundError:
    SOLPH_MODULE = False

# checks if the solph version includes the necessary Classes
try:
    from oemof.solph.buses import Bus
    from oemof.solph.components import Sink, Source, Converter, GenericStorage
    SOLPH_IMPORTS = True
except ModuleNotFoundError:
    SOLPH_IMPORTS = False
except ImportError:
    SOLPH_IMPORTS = False



def fixed_width_text(text, char_num=10):
    """Add linebreaks every char_num characters in a given text.

    Parameters
    ----------
    text: obj:'str'
        text to apply the linebreaks
    char_num: obj:'int'
        max number of characters in a line before a line break
        Default: 10
    Returns
    -------
    obj:'str'
        the text with line breaks after every char_num characters

    Examples
    --------
    >>> fixed_width_text("12345", char_num=2)
    '12\\n34\\n5'
    >>> fixed_width_text("123456")
    '123456'
    >>> fixed_width_text("12345", 5)
    '12345'
    >>> fixed_width_text("", 2)
    ''
    """
    # integer number of lines of `char_num` character
    n_lines = math.ceil(len(text) / char_num)

    # split the text in lines of `char_num` character
    split_text = []
    for i in range(n_lines):
        split_text.append(text[(i * char_num):((i + 1) * char_num)])

    return "\n".join(split_text)


class ESGraphRenderer:
    def __init__(
        self,
        energy_system=None,
        filepath=None,
        img_format=None,
        legend=False,
        txt_width=10,
        txt_fontsize=10,
        **kwargs
    ):
        """Render an oemof energy system using graphviz.

        Parameters
        ----------
        energy_system: `oemof.solph.network.EnergySystem`
            The oemof energy stystem

        filepath: str
            path, where the rendered result shall be saved, if an extension
            is provided, the format will be automatically adapted except if
            the `img_format` argument is provided
            Default: "energy_system.gv"

        img_format: str
            extension of the available image formats of graphviz (e.g "png",
            "svg", "pdf", ... )
            Default: "pdf"

        legend: bool
            specify, whether a legend will be added to the graph or not
            Default: False

        txt_width: int
            max number of characters in a line before a line break
            Default: 10

        txt_fontsize: int
            fontsize of the image's text (components labels)
            Default: 10

        **kwargs: various
            optional arguments of the graphviz.Digraph() class

        Returns
        -------
        None: render the generated dot graph in the filepath
        """
        missing_modules = []
        if SOLPH_MODULE is False or GRAPHVIZ_MODULE is False:
            if SOLPH_MODULE is False:
                missing_modules.append("oemof.solph")
            if GRAPHVIZ_MODULE is False:
                missing_modules.append("graphviz")
            raise ModuleNotFoundError(
                "You have to install the following packages to plot a graph\n"
                "pip install {0}".format(" ".join(missing_modules))
            )

        if SOLPH_IMPORTS is False:
            raise ImportError(
                "Some of the required modules or classes of solph could not be imported.\n"
                "Maybe you are using an outdated version of solph or your oemof-visio version is currently not working with the newer versions of oemof.solph."
            )

        if filepath is not None:
            file_name, file_ext = os.path.splitext(filepath)
        else:
            file_name = "energy_system"
            file_ext = ""

        kwargs.update(dict(filename=file_name))

        # if the `img_format` argument is not provided then the format is
        # automatically inferred from the file extension or defaults to "pdf"
        if img_format is None:
            if file_ext != "":
                img_format = file_ext.replace(".", "")
            else:
                img_format = "pdf"

        self.dot = graphviz.Digraph(format=img_format, **kwargs)
        self.txt_width = txt_width
        self.txt_fontsize = str(txt_fontsize)
        self.busses = []

        if legend is True:
            with self.dot.subgraph(name="cluster_1") as c:
                # color of the legend box
                c.attr(color="black")
                # title of the legend box
                c.attr(label="Legends")
                self.add_bus(subgraph=c)
                self.add_sink(subgraph=c)
                self.add_source(subgraph=c)
                self.add_transformer(subgraph=c)
                self.add_storage(subgraph=c)

        # draw a node for each of the energy_system's component.
        # the shape depends on the component's type.
        for nd in energy_system.nodes:
            if isinstance(nd, Bus):
                self.add_bus(nd.label)
                # keep the bus reference for drawing edges later
                self.busses.append(nd)
            elif isinstance(nd, Sink):
                self.add_sink(nd.label)
            elif isinstance(nd, Source):
                self.add_source(nd.label)
            elif isinstance(nd, Converter):
                self.add_transformer(nd.label)
            elif isinstance(nd, GenericStorage):
                self.add_storage(nd.label)
            else:
                logging.warning(
                    "The oemof component {} of type {} is not implemented in "
                    "the rendering method of the energy model graph drawer. "
                    "It will be therefore rendered as an ellipse".format(
                        nd.label,
                        type(nd)
                    )
                )
                self.add_component(nd.label)

        # draw the edges between the nodes based on each bus inputs/outputs
        for bus in self.busses:
            for component in bus.inputs:
                # draw an arrow from the component to the bus
                self.connect(component, bus)
            for component in bus.outputs:
                # draw an arrow from the bus to the component
                self.connect(bus, component)

    def add_bus(self, label="Bus", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            label,
            shape="rectangle",
            fontsize="10",
            fixedsize="shape",
            width="4.1",
            height="0.3",
            style="filled",
            color="lightgrey",
        )

    def add_sink(self, label="Sink", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            fixed_width_text(label, char_num=self.txt_width),
            shape="trapezium",
            fontsize=self.txt_fontsize,
        )

    def add_source(self, label="Source", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            fixed_width_text(label, char_num=self.txt_width),
            shape="invtrapezium",
            fontsize=self.txt_fontsize,
        )

    def add_transformer(self, label="Transformer", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            fixed_width_text(label, char_num=self.txt_width),
            shape="rectangle",
            fontsize=self.txt_fontsize,
        )

    def add_storage(self, label="Storage", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            fixed_width_text(label, char_num=self.txt_width),
            shape="rectangle",
            style="rounded",
            fontsize=self.txt_fontsize,
        )

    def add_component(self, label="component", subgraph=None):
        if subgraph is None:
            dot = self.dot
        else:
            dot = subgraph
        dot.node(
            fixed_width_text(label, char_num=self.txt_width),
            fontsize=self.txt_fontsize,
        )

    def connect(self, a, b):
        """Draw an arrow from node a to node b

        Parameters
        ----------
        a: `oemof.solph.network.Node`
            An oemof node (usually a Bus or a Component)

        b: `oemof.solph.network.Node`
            An oemof node (usually a Bus or a Component)
        """
        if not isinstance(a, Bus):
            a = fixed_width_text(a.label, char_num=self.txt_width)
        else:
            a = a.label
        if not isinstance(b, Bus):
            b = fixed_width_text(b.label, char_num=self.txt_width)
        else:
            b = b.label

        self.dot.edge(a, b)

    def view(self, **kwargs):
        """Call the view method of the DiGraph instance"""
        self.dot.view(**kwargs)

    def render(self, **kwargs):
        """Call the render method of the DiGraph instance"""
        print(self.dot.render(**kwargs))

    def pipe(self, **kwargs):
        """Call the pipe method of the DiGraph instance"""
        self.dot.pipe(**kwargs)
