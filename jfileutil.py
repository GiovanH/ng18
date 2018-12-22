import json
import pickle
from os import makedirs

# Version 1.3

# This is for change in the library, not change in runtime!
basepath = "./jobj/" 

# Runtime changes should be made to these:
basepath_json = basepath
basepath_pick = basepath


def ensure_dirs(destpath):
    # Make necessary directories, if they don't exist.
    try:
        makedirs(destpath)
    except FileExistsError:
        pass


def load(filename):
    return json_load(filename)


def save(object, filename):
    return json_save(object, filename)


def pickle_to_json(filename):
    json_save(pickle_load(filename), filename)


def json_to_pickle(filename):
    pickle_save(json_load(filename), filename)


def json_load(filename):
    with open(basepath_json + filename + ".json", 'r') as file:
        return json.load(file)


def json_save(object, filename):
    ensure_dirs(basepath_json)
    j = json.dumps
    with open(basepath_json + filename + ".json", 'w') as file:
        j = json.dump(object, file, indent=4)


def pickle_load(filename):
    filehandler = open(basepath_pick + filename + ".obj", 'rb')
    object = pickle.load(filehandler)
    return object


def pickle_save(object, filename):
    ensure_dirs(basepath_pick)
    filehandler = open(basepath_pick + filename + ".obj", 'wb')
    pickle.dump(object, filehandler)
