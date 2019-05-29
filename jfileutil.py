"""Utility functions for storing and loading json data.

Attributes:
    basepath (str): Basepath for object files.
    basepath_json (str): Basepath for json files.
    basepath_pick (str): Basepath for pickle files.
"""
import json
# import pickle
from os import makedirs, path
import shutil   
# import traceback


# Version 1.6

basepath_json = "./jobj/" 
basepath_pick = "./obj/" 


# def load(filename):
#     """Args:
#         filename (string): Identifier for object
    
#     Returns:
#         Object
#     """
#     return json_load(filename)


# def save(object, filename):
#     """Args:
#         object (object): Object to store
#         filename (string): Identifier for object
#     """
#     return json_save(object, filename)
def get_json_path(basepath, filename):
    return path.relpath(path.join(basepath, filename + ".json"))


def json_load(filename, basepath=basepath_json, default=None):
    """Args:
        filename (string): Identifier for object
    
    Returns:
        Object
    """
    json_path = get_json_path(basepath, filename)
    try:
        with open(json_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        # raise
        print("Error with file", json_path)
        # traceback.print_exc()
        if default is not None:
            # print("Load failed for file", filename, "; defaulting.")
            return default
        else:
            # print("Load failed for file", filename, "with no default provided")
            raise


def json_save(object, filepath, basepath=basepath_json):
    """Args:
        object (object)
        filename (string): Identifier for object
    """
    filepath = get_json_path(basepath, filepath)
    (fdirs, fname) = path.split(filepath)
    makedirs(fdirs, exist_ok=True)

    # Displace
    if path.isfile(filepath):
        shutil.move(filepath, filepath + ".bak")

    with open(filepath, 'w') as file:
        json.dump(object, file, indent=4)


load = json_load
save = json_save


class Handler():

    def __init__(self, name, default=None, basepath=basepath_json, readonly=False):
        self.name = name
        self.default = default
        self.readonly = readonly
        self.basepath = basepath
        self.obj = None

    def load(self):
        return load(self.name, basepath=self.basepath, default=self.default)

    def __enter__(self):
        self.obj = self.load()
        return self.obj

    def __exit__(self, type, value, traceback):
        if not self.readonly:
            self.flush()

    def flush(self):
        if self.readonly:
            raise NotImplemented("Cannot save if readonly is True.")
        else:
            # print("Flushing", self.name)
            save(self.obj, self.name, basepath=self.basepath)


class RotatingHandler(Handler):
    def load(self):
        try:
            self.obj = load(self.name, basepath=self.basepath)  # Don't handle failure; no default
            # File is good, so:
            self.backup()
            return self.obj
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print("Warning: data file '{}' corrupted. ".format(self.name))
            if shutil.os.path.isfile(get_json_path(self.basepath, self.name)):
                # If the file exists, but is corrupted
                print("Deleting corrupted data")
                shutil.os.remove(get_json_path(self.basepath, self.name))
            if path.exists(get_json_path(self.basepath, self.name) + ".bak"):
                # If backup exists
                print("Restoring backup")
                shutil.copy2(
                    get_json_path(self.basepath, self.name) + ".bak",
                    get_json_path(self.basepath, self.name)
                ) 
                self.obj = load(self.name, basepath=self.basepath)
                return self.obj
            elif self.default is not None:
                self.obj = load(self.name, basepath=self.basepath, default=self.default)
                return self.obj
            else:
                raise

    def backup(self):
        # print("Backing up", self.name)
        if path.exists(get_json_path(self.basepath, self.name)):
            shutil.copy2(
                get_json_path(self.basepath, self.name),
                get_json_path(self.basepath, self.name) + ".bak"
            ) 

    # def flush(self):
    #     super().flush()
        # self.backup()
