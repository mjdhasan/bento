import glob
import hashlib
import inspect
import pathlib
import pickle
import pkgutil
import re
import subprocess
import time
import pandas as pd

from bento.common.structure import ENV
from bento.common.logger import fancy_logger

logging = fancy_logger(__name__)


def id_func(x):
    return x


def desnake(text):
    """Turns underscores into spaces"""
    return text.strip().replace("_", " ")


def snakify(text):
    for char in "()":
        text = text.replace(char, "")
    text = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text).strip()
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", text).lower().replace(" ", "_")


def snakify_column_names(df):
    col_map = {col_name: snakify(col_name) for col_name in df.columns}
    return df.rename(columns=col_map)


def nice_command(cmd):
    proc = subprocess.Popen(cmd)
    try:
        logging.info(f"Waiting on {cmd[0]}")
        logging.debug(cmd)
        proc.wait()
    except KeyboardInterrupt:
        logging.info(f"Letting {cmd[0]} clean up...")
        proc.wait()
        logging.info("...Done")


def loader(filename, package="bento", parse_date=True):
    args = {
        "index_col": 0,
        "parse_dates": ["date"] if parse_date else [],
        "infer_datetime_format": True,
    }
    try:
        df = pd.read_csv(f"./{filename}", **args)
    except FileNotFoundError:
        try:
            df = pd.read_csv(f"assets/{filename}", **args)
        except FileNotFoundError:
            try:
                package_path = pkgutil.get_loader(package)._path._path[0]
                df = pd.read_csv(f"{package_path}/assets/{filename}", **args)
            except FileNotFoundError:
                logging.warning(f"Couldn't find {filename}")
                return None

    data = {"df": df}
    logging.info(f"*** Loaded {filename} ***")
    # TODO Figure out some log-based way to get this output cleanly
    if logging.level <= 10:
        print(data["df"].head(3))
    return data


# Runs a supplied shell command, handling output
def logged_command(cmd, output_dir=".logs", shell=False):
    subprocess.run(["mkdir", "-p", output_dir])
    base_cmd = cmd[0]
    logging.info(f"Running command: {cmd}")
    output = ""
    errors = ""
    with open(f"{output_dir}/{base_cmd}_std.log", "w+") as fout:
        with open(f"{output_dir}/{base_cmd}_err.log", "w+") as ferr:
            result = subprocess.run(cmd, stdout=fout, stderr=ferr, shell=shell)
            try:
                fout.seek(0)
                output = fout.read()
                ferr.seek(0)
                errors = ferr.read()
                if errors:
                    logging.debug("Stderr: {}".format(errors))
            except Exception as exc:
                logging.warning("Issue with capturing log output of subprocess")
                logging.info(exc)

    # TODO refactor with dataclass or other?
    cmd_result = {
        "code": result.returncode,
        "out": output,
        "err": errors,
    }
    return cmd_result


# TODO Look at replacing this with functools.lru_cache
# Decorator: makes functions perform better by reusing cached results for same args
def memoize(func):
    cache = func.cache = {}

    def run(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        if key in cache:
            return cache[key]
        else:
            result = func(*args, **kwargs)
            cache[key] = result
            return result

    return run


def check_cache(fullhash, age_limit):
    timestamp_limit = int(time.time()) - age_limit
    for cache_file in glob.glob(f"{ENV.PYCACHE_DIR}/*.pkl"):
        if fullhash in cache_file:
            try:
                stamp = re.search(r"_t(\d{10})_", cache_file).groups()[0]
                if stamp < timestamp_limit:
                    continue
            except Exception:
                pass
            logging.info(f"Loading from cache {cache_file}")
            with open(cache_file, "rb") as fh:
                data = pickle.load(fh)
            return data


# Decorator: adds local file cache, based on data and func hash
def addcache(func):
    age_limit = 36000
    pathlib.Path(ENV.PYCACHE_DIR).mkdir(parents=True, exist_ok=True)

    def run(*args, **kwargs):
        cache_name = "default"
        funchash = hash_func(func)[:4]
        fullhash = funchash
        cargs = list(args + tuple(kwargs.values()))
        # TODO upgrade this simple check for filename
        if cargs and type(cargs[0]) == str:
            cache_name = cargs[0]
        if cargs and ".csv" in cargs[0]:
            data_path = cargs[0]
            cache_name = data_path.split("/")[-1]
            logging.info(f"Checking cache for {data_path}")
            filehash = hash_file(data_path)[:4]
            fullhash = funchash + filehash
            data = check_cache(fullhash, age_limit)
            if data is not None:
                return data

        elif cargs and hasattr(cargs[0], "columns"):
            df = cargs[0]
            # TODO log the name of df?
            cache_name = "df"
            size = f"{len(df)} x {len(df.columns)}"
            cols = df.columns if len(df.columns) < 5 else ""
            logging.info(f"Checking cache on {size} dataframe {cols}")
            objhash = hash_obj(df)[:4]
            fullhash = funchash + objhash
            data = check_cache(fullhash, age_limit)
            if data is not None:
                return data

        result = func(*args, **kwargs)
        ts = int(time.time())
        with open(f"{ENV.PYCACHE_DIR}/{cache_name}_{fullhash}_{ts}.pkl", "wb") as fh:
            pickle.dump(result, fh)
        return result

    return run


def _hash(string):
    h = hashlib.sha256()
    h.update(string)
    return h.hexdigest()


def hash_obj(obj):
    return _hash(pickle.dumps(obj))


@memoize
def hash_func(func):
    return _hash(inspect.getsource(func).encode())


@memoize
def hash_file(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()