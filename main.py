import os

import ee

from preprocessor import preprocess
from gfc_calculator import analyse
from postprocessor import postprocess
from utilities import wait_until_all_tasks_complete, print_w_timestamp


def main(range_map_geodatabase_path,
         layer_name,
         forest_dependency_spreadsheet_path,
         global_canopy_cover_thresh,
         aoo_canopy_cover_thresh,
         altitude_limits_table_path,
         generation_lengths_table_path):
    """This function is the core of the application. It performs the pre-processing,
    analysis and post-processing.

    :param range_map_geodatabase_path: Path to an ESRI file geodatabase containing range
        maps to be analysed. See README for required format.
    :param layer_name: Name of the layer in the geodatabase at geodatabase_path
        containing the range maps to be analysed.
    :param forest_dependency_spreadsheet_path: Path to a spreadsheet containing species'
        forest dependency information. See README for required format.
    :param global_canopy_cover_thresh: Pixels in the "treecover2000" layer with an
        intensity less than this threshold are excluded from all computations: they
        are not counted as tree cover.
    :param aoo_canopy_cover_thresh: 2km by 2km grid cells containing a proportion of
        tree cover greater than aoo_canopy_cover_thresh are counted as forested cells
        for the purpose of AOO estimation.
    :param altitude_limits_table_path: Path to a CSV file containing species' minimum
        and maximum altitudes. See README for required format.
    :param generation_lengths_table_path: Path to a CSV file containing species'
        generation lengths. See README for required format.
    :return:
    """
    # Google Cloud Platform authentication.
    os.system('gcloud auth login')
    # Google Earth Engine authentication.
    ee.Authenticate()

    ee.Initialize()

    range_map_ic_gee_path = preprocess(range_map_geodatabase_path, layer_name,
                                       forest_dependency_spreadsheet_path)

    print_w_timestamp('Waiting for all GEE tasks to complete...')
    wait_until_all_tasks_complete()
    print_w_timestamp('Done.')

    if global_canopy_cover_thresh:
        if aoo_canopy_cover_thresh:
            analyse(altitude_limits_table_path,
                    range_map_ic_gee_path,
                    global_canopy_cover_thresh,
                    aoo_canopy_cover_thresh)
        else:
            analyse(altitude_limits_table_path,
                    range_map_ic_gee_path,
                    global_canopy_cover_thresh)
    else:
        if aoo_canopy_cover_thresh:
            analyse(altitude_limits_table_path,
                    range_map_ic_gee_path,
                    aoo_canopy_cover_thresh)
        else:
            analyse(altitude_limits_table_path,
                    range_map_ic_gee_path)

    print_w_timestamp('Waiting for all GEE tasks to complete...')
    wait_until_all_tasks_complete()
    print_w_timestamp('Done.')

    postprocess(generation_lengths_table_path)
