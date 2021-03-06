Concepts within Bento
=====================

These two example dashboard descriptors will be useful for reference:
 - `Simple <https://github.com/dereklarson/bento/blob/master/bento/dashboards/simple.py>`_
 - `Demo <https://github.com/dereklarson/bento/blob/master/bento/dashboards/demo.py>`_

Data
----
Everything begins with data, and Bento doesn’t try to assist with the data processing.
It is assumed you will supply your dashboard with prepared data in a pandas DataFrame.
This helps decouple your visualization code from any data preparation code.
However, Bento does inform the dashboard by what’s in the data. For example, dropdown menus
for filters can be automatically populated by what is in the dataframe.

You define all datasets used in the dashboard up front in the “data” key of the descriptor.
Each dataset needs a unique ID (uid) and a module that contains the code to load it.
In the *Simple* example, we loaded the data by the uid “covid” via the module
``bento.sample_data.covid``
which contains a method “load” that returns an object containing the dataframe. 

In your generated Bento app, the data is stored in a global variable and accessed by key.
This tends to be simplest at the page level, through the “dataid” key.
This can be overridden at the bank level, however, if needed.

Pages
-----
To Bento, a page is just about what you'd expect:  everything associated with a given URL.
Bento tries to make page navigation easy out of the box, with an autogenerated appbar.
The downside to this:  you still have to define your “pages” even if you want a single-page app. 

Overall, the page definition is rather easy--each page needs a unique ID.
The main descriptor “pages” key defines a dictionary with these unique IDs as keys and
the individual page descriptors as values. 

The *Simple* example demonstrates a single page while the *Demo* has multiple.

Banks
-----
The banks are the building blocks of your Bento app.

You define your banks under a page’s “banks” key, each with a uid and a dictionary
containing at least the “type” key, which would be chosen from the list below.

Connections
-----------
One of the trickiest parts of making an interactive dashboard in Plotly Dash is getting
components to properly work together. At the same time, it’s one of the areas which
tends to be the most repetitive once you understand it. This is a big part of what makes
Bento useful. Bento abstracts away any need for writing callbacks by defining
“connections”:  which banks feed which other banks. If you want a bank to affect another
one, connect them.

In a page descriptor, the “connections” key is just the set of “source” bank uids which
defines, for each, the set of “sink” bank uids. In the *Simple* example, our axis_controls
named “axis” feeds our graph called ”trend”.

Layout
------
This is the easiest part. Just write a 2D-list of the bank ids, imagining a grid. Each
page descriptor should have this in a key “layout”, such as in *Simple* where we have two
rows, one bank per row.

Bento uses the CSS Grid system to size the banks, and also comes with a sense of how big
each bank should be depending on its inputs. For example, an axis_control bank might be
2 rows by 2 columns (2x2) for 1 axis, and it will try for 2x6 if you have 3 axes
defined. If you try to pack in a lot in a row, Bento will trim from each until they fit.
