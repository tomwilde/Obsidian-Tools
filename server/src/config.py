import os
import configparser

config = configparser.ConfigParser()
config.read('config.ini')


def determine_root_dir():
    rootdir = config['Obsidian']['rootdir']

    if os.path.exists(rootdir) and os.path.isdir(rootdir):
        print(f"Serving: {rootdir}")
        return rootdir
    else:
        raise Exception(f"The rootdir: {rootdir} could not be found or is not a directory.")
