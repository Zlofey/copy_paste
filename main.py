"""

Copy/paste files listed in  xml config

"""
import datetime
import os
import shutil
import xml
import xml.etree.ElementTree as ET
import logging
import psutil as psutil

# Command Line Interface Creation Kit
# import click
# @click.command()
# @click.option('--xml_path', prompt='path to config xml file')
xml_path = 'config.xml'  # TODO replace with click

LOG_FORMAT = "\n%(asctime)s %(levelname)s %(message)s"
LOG_PATH = 'copy_paste.log'
logging.basicConfig(filename=LOG_PATH, format=LOG_FORMAT)
logger = logging.getLogger()


def find_sdiskpart(path):
    """
    get mountpoint and device info by path
    """
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    p = [p for p in psutil.disk_partitions(all=True) if p.mountpoint == path.__str__()]
    l = len(p)
    if len(p) == 1:
        #print(type(p[0]))
        return p[0]
    raise psutil.Error


def get_tree(xml_path):
    """
    parse XML document into element tree
    """
    try:
        tree = ET.parse(xml_path)
        return tree
    except FileNotFoundError:
        print("file not found, please enter correct config file path")
        print("")
        logging.exception("FileNotFoundError")
        exit()
    except xml.etree.ElementTree.ParseError:
        print("parsing error, not well-formed xml")
        logging.exception("ParseError")
        exit()
    except PermissionError:
        print("permission denied: no read access")
        logging.exception("PermissionError")
        exit()
    except Exception:
        print('something wrong with config file')
        logging.exception("something wrong with config file")


def get_files(tree):
    """
    get file info from xml element tree
    """
    files = []
    if tree.findall('file'):
        for file in tree.findall('file'):
            files.append({
                "source_path": os.path.abspath(file.get("source_path")),
                "destination_path": os.path.abspath(file.get("destination_path")),
                "file_name": file.get("file_name"),
                "file_path": os.path.join(os.path.abspath(file.get("source_path")),
                                          file.get("file_name")),
            })
    else:
        print('files to copy not found in the config file')
        exit()
    #print(files)
    return files


def copy(file):
    """
    copy file
    """
    try:
        shutil.copy(
            file['file_path'],
            file['destination_path']
        )
    except Exception as e:
        print(e)
        logging.exception("error while copying file")


def disk_space_check(files):
    """
    calculate required disk space.
    if disk is out of space, remove files that need to be copied to this disk from "files".
    """
    def _checking(files):
        files_to_check = []  # add "files" with disk usage information
        for file in files:
            files_to_check.append({
                "file_name": file["file_name"],
                "source_path": file["source_path"],
                "destination_path": file["destination_path"],
                "file_path": file['file_path'],
                "file_size": os.path.getsize(file['file_path']),
                "dest_mountpoint": find_sdiskpart(file["destination_path"]).mountpoint,
            })

        # filter files_to_check by mountpoint and calculating  disk space
        dest_mountpoints = set(f["dest_mountpoint"] for f in files_to_check)
        devices = []
        for mountpoint in dest_mountpoints:
            device_files = [f for f in files_to_check if f["dest_mountpoint"] == mountpoint]
            required_space = sum([f["file_size"] for f in device_files])
            free_disk_space = psutil.disk_usage(mountpoint).free
            enough_space = free_disk_space > required_space
            devices.append({
                "dest_mountpoint": mountpoint,
                "dest_device": find_sdiskpart(mountpoint).device,
                "files": device_files,
                "enough_space": enough_space,
                "free_disk_space": free_disk_space,
                "required_space": required_space,
            })
        return devices

    devices = _checking(files)
    if False in [d["enough_space"] for d in devices]:
        # make list of non-copied files
        try:
            with open("not_enough_space.txt", "w") as not_enough_space:
                not_enough_space.write(f'{datetime.datetime.now()}\n')
                for device in devices:
                    if not device["enough_space"]:
                        m = (f'device: {device["dest_device"]}'
                             f'\nmountpoint: {device["dest_mountpoint"]}'
                             f'\nrequired_space: {device["required_space"]} B'
                             f'\nfree_dsk_space: {device["free_disk_space"]} B'
                             f'\nnon-copied files list:')
                        not_enough_space.write(m)
                        for file in device["files"]:
                            not_enough_space.write(f'\n{file["file_path"]} {file["file_size"]} B')
        except Exception as e:
            logging.exception(f'Exception trying to make not_enough_space.txt\nException:{e}')

        # logging
        for device in devices:
            if not device["enough_space"]:
                m = (f'Not enough space on'
                      f'\ndevice: {device["dest_device"]}'
                      f'\nmountpoint: {device["dest_mountpoint"]}'
                      f'\nrequired_space: {device["required_space"]} B'
                      f'\nfree_dsk_space: {device["free_disk_space"]} B'
                     f'\nsome files are not copied, see {os.path.abspath("not_enough_space.txt")} for details')
                print(m)
                logging.warning(m)

        # make "new_list" from files, which destination disk has enough space
        new_list = []
        for device in devices:
            if device["enough_space"]:
                for file in device["files"]:
                    new_list.append({
                        "source_path": file["source_path"],
                        "destination_path": file["destination_path"],
                        "file_name": file["file_name"],
                        "file_path": file["file_path"],
                    })
        return new_list

    else:
        return files


def file_check(file):
    """
    File_path existence and read access check.
    Destination_path existence and write access check. If Destination_path not exists, try to create.
    If all checks are True, return result = True
    """

    def _source_check(file):
        # file path exist
        if os.path.exists(file["file_path"]):
            # file read access check
            try:
                open(file["file_path"]).close()
                return True
            except Exception as e:
                logging.warning(f'{file["file_name"]} read access check failed\nfile_path: {file["file_path"]}\nException: {e}')
        else:
            logging.warning(f'{file["file_name"]} no such file or directory\nfile_path: {file["file_path"]}')
        return False

    def _destination_check(file):
        # destination_path  exist/create
        try:
            os.makedirs(file["destination_path"], exist_ok=True)
            # destination_path write access check
            try:
                open(os.path.join(file["destination_path"], 'tempfile.txt'), 'w').close()
                os.remove(os.path.join(file["destination_path"], 'tempfile.txt'))
                return True
            except Exception as e:
                logging.warning(f'{file["file_name"]} write access check failed\ndestination_path: {file["destination_path"]}\nException:{e}')
        except Exception:
            logging.warning(f'{file["file_name"]} failed to make path: \ndestination_path: {file["destination_path"]}')
        return False

    return _source_check(file) and _destination_check(file)


if __name__ == '__main__':
    tree = get_tree(xml_path)
    files = get_files(tree)
    files = [f for f in files if file_check(f)]
    files = disk_space_check(files)
    for f in files:
        copy(f)


#TODO Сделать проверку на уже существующий в destination_path файл. если есть, то запрос на overwrite. можно добавить сравнение файлов по хеш суммам

#TODO  можно с помощью https://github.com/magmax/python-inquirer вывести список файлов для копирования, если места недостаточно.

#TODO  unit тесты