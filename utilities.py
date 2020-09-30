import os
from datetime import datetime

import ee

SCI_NAME_RASTER_FILENAME_MAPPING_FP = 'out/sci_name_raster_filename_mapping.csv'


def map_sisid_breeding_to_filename(sisid: str, breeding: str, uncompressed: bool):
    """

    :param sisid:
    :param breeding:
    :param uncompressed:
    :return:
    """
    filename = sisid + '_' + breeding
    if uncompressed:
        filename = filename + '_uncompressed'
    else:
        filename = filename + '_compressed'
    filename = filename + '.tif'

    return filename


def map_filename_to_sisid_breeding(filename):
    """

    :param filename:
    :return:
    """
    filename_wo_extension = filename[:-4]
    components = filename_wo_extension.split('_')
    sisid = components[0]
    breeding = components[1]

    return {'sisid': sisid, 'breeding': breeding}


def print_w_timestamp(str_to_print, end='\n'):
    """

    :param str_to_print:
    :param end:
    :return:
    """
    print('[%s] %s' % (str(datetime.now().time()), str_to_print), end=end)


def get_pending_or_running_task_ids():
    """Get a list of the names of all GEE tasks which are either pending or running.

    :return:
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
    """

    :return:
    """
    task_ids = get_pending_or_running_task_ids()
    while task_ids:
        os.system('earthengine task wait %s' % task_ids[0])
        task_ids = get_pending_or_running_task_ids()
