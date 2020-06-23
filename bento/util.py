import pandas as pd
import numpy as np
import math
import plotly.express as px

from bento.common import logger, logutil, dictutil  # noqa

logging = logger.fancy_logger(__name__)


def desnake(text):
    """Turns underscores into spaces"""
    return text.strip().replace("_", " ")


def titlize(text):
    return desnake(text.title())


def get_unit(num):
    scale = ["f", "n", "u", "m", "", "K", "M", "G", "T", "P"]
    offset = 4
    try:
        exp = min(9, offset + math.log10(num) / 3)
        if exp < 0:
            return num, ""
        exp = int(exp)
        sig = round(num / 10 ** ((exp - 4) * 3), 2)
        return sig, scale[exp]
    except Exception:
        return num, ""


# @logutil.loginfo(logger=logging)
def prepare_transforms(inputs):
    transforms = []
    for key, value in dictutil.extract("_transform", inputs, pop=False).items():
        if not value:
            continue
        if "window" in key:
            y_column = dictutil.extract("y_column", inputs, pop=False, unique=True)
            transforms.append((y_column, ["rolling", "mean"], [(value,), ()]))
    return transforms


# @logutil.loginfo(logger=logging)
def prepare_filters(inputs):
    filters = []
    for key, values in dictutil.extract("_filter", inputs, pop=False).items():
        if not values:
            continue
        if not isinstance(values, list):
            values = [values]
        if "date" in key and len(values) == 2:
            filters += [("between", key.replace("_filter", ""), values)]
        else:
            filters += [("or", key.replace("_filter", ""), values)]
    return filters


# @logutil.loginfo(logger=logging)
def filter_df(idf, filters):
    odf = idf
    for logic, column, values in sorted(filters):
        if "datetime" in str(type(values[0])):
            values = [np.datetime64(item) for item in values]
        if logic == "between":
            odf = odf[(odf[column] >= values[0]) & (odf[column] <= values[1])]
        elif logic == "or":
            odf = odf[odf[column].isin(values)]

    return odf


def rank(idf, count, key, column):
    fdf = idf.groupby([key]).sum().reset_index()
    fdf = fdf.nlargest(count, column)
    return zip(fdf[key], fdf[column])


# @logutil.loginfo(logger=logging)
def prepare_traces(idf, filters):
    # NOTE Brought over from figure callback, default multi-column approach
    # TODO Figure out how to determine default columns from df
    # column = self.data.get("keys", self.data["columns"][0])[0]
    # def_x_column = self.data["columns"][1]
    # idf.groupby(column).max().reset_index().nlargest(8, def_x_column)[column]
    idf["label"] = ""
    idf.name = ""
    traces = [idf]
    for logic, column, values in sorted(filters):
        new_traces = []
        if logic == "between":
            for df in traces:
                new = df[(df[column] >= values[0]) & (df[column] <= values[1])]
                new.name = ""
                new_traces.append(new)
        elif logic == "or":
            for df in traces:
                for value in values:
                    new = df[df[column] == value]
                    try:
                        new["label"] += " " + new[column]
                    except Exception:
                        logging.warning(f"Can't add {column} to label")
                    new.name = df.name + " " + value
                    new_traces.append(new)
        traces = new_traces

    new_traces = []
    for df in traces:
        new = df.groupby(["date", "label"]).sum().reset_index()
        new.name = df.name
        new_traces.append(new)
    traces = new_traces

    return traces


# @logutil.loginfo(logger=logging)
def trace_analytics(traces, transforms):
    for transform in transforms:
        column, operations, arg_list = transform
        for trace in traces:
            buff = trace[column]
            for op, args in zip(operations, arg_list):
                buff = getattr(buff, op)(*args)
            trace[column] = buff
    return traces


def aggregate(idf, y_column=None, filters=[], logic="sum", **kwargs):
    filters += kwargs.get("fixed_filters", [])
    traces = prepare_traces(idf, filters)
    agg_df = pd.concat(traces)
    if not y_column:
        return len(agg_df), ""
    quantity = getattr(agg_df[y_column], logic)()
    return get_unit(quantity)


def _date_marks(ordered):
    spacing = 7
    style = {}
    labels = {item: pd.Timestamp(item).date().day for item in ordered[::spacing]}
    marks = {
        int(key): {"label": label, "style": style} for key, label in labels.items()
    }
    return marks


def gen_marks(series, variant="auto"):
    """Processes a dataframe column into a valid slider series"""
    ordered = sorted(series)
    spacing = math.ceil(len(ordered) / 10)
    if variant == "date":
        marks = _date_marks(ordered)
    else:
        marks = {item: str(item) for item in series[::spacing]}
    return marks


def gen_options(option_input):
    # In this case, we're given just the set of options only, assuming first is default
    if isinstance(option_input, list):
        option_list = option_input
        default = option_list[0]
    # The default may be specified in the dict version
    elif isinstance(option_input, dict):
        # TODO Make this more robust
        if "value" in option_input:
            return option_input
        option_list = option_input["options"]
        default = option_input.get("default", option_list[0])
    options = [{"label": desnake(item).title(), "value": item} for item in option_list]
    return {"options": options, "value": default}


def get_first_numeric(data_types):
    for dtype in data_types:
        if "log" in data_types[dtype]:
            return dtype


def log_color_scale(name, base=2.718, category="sequential"):
    color_category = getattr(px.colors, category)
    color_sequence = getattr(color_category, name)
    # print(color_sequence)
    log_val = [round(1 / base ** idx, 10) for idx in range(len(color_sequence))][::-1]
    log_val[0] = 0
    log_sequence = list(zip(log_val, color_sequence))
    return log_sequence


# @logutil.loginfo(logger=logging)
def data_range(pd_df_list, column, scale="category"):
    minimum = pd_df_list[0][column].min()
    maximum = pd_df_list[0][column].max()
    for df in pd_df_list:
        series = df[column]
        minimum = min(minimum, series.min())
        maximum = max(maximum, series.max())
        if scale == "log":
            minimum = max(0.1, minimum)
            minimum = np.floor(max(-1, np.log10(minimum)))
            maximum = np.ceil(np.log10(maximum))
        elif scale == "linear":
            minimum = np.floor(minimum)
            maximum = np.ceil(maximum)
    return [minimum, maximum]


if __name__ == "__main__":

    log_color_scale("Viridis", base=10)

    for i in range(-18, 19):
        unit = "Hz"
        sig, scale = get_unit(10 ** i)
        print(f"{sig} {scale}{unit}")