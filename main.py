"""

Copy/paste files listed in  xml config

"""
import datetime
import os
import shutil
import xml
import xml.etree.ElementTree as ET
import logging

import click
import psutil as psutil
import filecmp
import toml


def main():
    with open("sample.toml", "r") as f:
        data = toml.load(f)
        
    print("job is done")
    print("\n*****Done!!!*****")
    print(data["foo"])

if __name__ == "__main__":
    main()
