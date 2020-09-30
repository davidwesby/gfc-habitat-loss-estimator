import os
from datetime import datetime

import ee

SCI_NAME_RASTER_FILENAME_MAPPING_FP = 'out/sci_name_raster_filename_mapping.csv'


def map_sisid_breeding_to_filename(sisid: str, breeding: str, uncompressed: bool):
    """Generate a raster filename from a SISID and breeding status. This function
    should be the inverse of map_filename_to_sisid_breeding.

    :param sisid: SISID
    :param breeding: Breeding status
    :param uncompressed: Whether the filename is for a compressed or uncompressed file.
    :return: Generated filename
    """
    filename = sisid + '_' + breeding
    if uncompressed:
        filename = filename + '_uncompressed'
    else:
        filename = filename + '_compressed'
    filename = filename + '.tif'

    return filename


def map_filename_to_sisid_breeding(filename):
    """Extract the SISID and breeding status from a raster filename. This function
    should be the inverse of map_sisid_breeding_to_filename.

    :param filename: The filename of the raster representation of a range map.
    :return: The SISID and breeding status of the corresponding range map.
    """
    filename_wo_extension = filename[:-4]
    components = filename_wo_extension.split('_')
    sisid = components[0]
    breeding = components[1]

    return {'sisid': sisid, 'breeding': breeding}


def print_w_timestamp(str_to_print, end='\n'):
    """Print str_to_print with a prepended formatted timestamp.

    :param str_to_print: The string to print after the timestamp.
    :param end: The terminating character of the combined string.
    """
    print('[%s] %s' % (str(datetime.now().time()), str_to_print), end=end)


def get_pending_or_running_task_ids():
    """Get a list of the names of all GEE tasks which are either pending or running.

    :return: A list of the names of all GEE tasks which are either pending or running.
    """
    task_ids = []

    tasks = ee.data.listOperations()

    for task in tasks:
        state = task['metadata']['state']
        if state == 'RUNNING' or state == 'PENDING':
            task_id = os.path.basename(task['name'])
            task_ids.append(task_id)

    return task_ids


def wait_until_all_tasks_complete():
    """Continually check whether all running tasks have finished. Delay further
    execution until everything is done.
    """
    task_ids = get_pending_or_running_task_ids()
    while task_ids:
        os.system('earthengine task wait %s' % task_ids[0])
        task_ids = get_pending_or_running_task_ids()
