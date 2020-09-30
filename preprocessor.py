import csv
import random
import shutil
import string
import os
from configparser import ConfigParser
from fractions import Fraction
from math import ceil

import ee

from utilities import map_sisid_breeding_to_filename, \
    SCI_NAME_RASTER_FILENAME_MAPPING_FP, print_w_timestamp, \
    wait_until_all_tasks_complete

import geopandas as gpd
import pandas as pd
import rasterio
from rasterio.features import rasterize
from affine import Affine
from osgeo.gdal import Translate
import fiona

CHUNK_SIZE = 50
MODULE_PARENT_DIR_PATH = os.path.dirname(os.path.realpath(__file__))

RASTER_DIR_PATH = os.path.join(MODULE_PARENT_DIR_PATH, 'rasters')

CONFIG_FILE_PATH = os.path.join(MODULE_PARENT_DIR_PATH, 'config.ini')
CONFIG_PARSER = ConfigParser()
CONFIG_PARSER.read(CONFIG_FILE_PATH)

PIXEL_WIDTH_STR = CONFIG_PARSER['DEFAULT']['Pixel width']
PIXEL_HEIGHT_STR = CONFIG_PARSER['DEFAULT']['Pixel height']
GCS_BUCKET_NAME = CONFIG_PARSER['DEFAULT']['GCS bucket name for rasters']
GCS_BUCKET_PATH = 'gs://' + GCS_BUCKET_NAME


def _get_gee_home_folder_path():
    """

    :return:
    """
    earth_engine_ls_output = os.popen('earthengine ls').read()
    if "users" in earth_engine_ls_output:
        # User already has a home folder. Get a path to it.
        gee_home_folder_path = earth_engine_ls_output.split('assets/')[1][:-1]
    else:
        # User does not already have a home folder. Create one.
        # Generate a random suffix. (Home folder names must be unique.)
        random_suffix = ''.join(random.choices(string.digits, k=10))
        gee_home_folder_path = 'users/forest_loss_tool_user_' + random_suffix
        ee.data.createAssetHome(gee_home_folder_path)

    return gee_home_folder_path


def _create_forest_dep_df(forest_dep_spreadsheet_path):
    """Read the forest dependency spreadsheet into a pandas DataFrame and return it.

    :param forest_dep_spreadsheet_path: An Excel spreadsheet specifying species'
        forest dependency. The spreadsheet must contain a column titled "SIS ID" and a
        column titled "Forest dependency".
    :return A pandas DataFrame specifying species' forest dependency, with a column
        titled "SISID" and a column titled "Forest dependency".
    """
    # Construct a DataFrame from the forest dependency spreadsheet.
    forest_dep_df = pd.read_excel(forest_dep_spreadsheet_path)

    # Change the "SISID" column to "SIS ID".
    forest_dep_df_col_names = list(forest_dep_df.columns.values)
    forest_dep_df_col_names[forest_dep_df_col_names.index('SIS ID')] = 'SISID'
    forest_dep_df.columns = forest_dep_df_col_names

    return forest_dep_df


def _filter_gdf(botw_gdf_w_forest_deps):
    """

    :param botw_gdf_w_forest_deps:
    :return:
    """
    #   Filter out every row in which the forest dependency isn't "Medium" or "High".
    botw_gdf_w_forest_deps = botw_gdf_w_forest_deps[
        botw_gdf_w_forest_deps['Forest dependency'].isin(['Medium', 'High'])]

    #   Filter out every row in which the presence isn't 1 or 2.
    botw_gdf_w_forest_deps = botw_gdf_w_forest_deps[
        botw_gdf_w_forest_deps['PRESENCE'].isin(['1', '2'])]

    #   Filter out every row in which the origin isn't 1, 2 or 6.
    botw_gdf_w_forest_deps = botw_gdf_w_forest_deps[
        botw_gdf_w_forest_deps['ORIGIN'].isin(['1', '2', '6'])]

    #   Filter out every row in which the seasonality isn't 1, 2 or 3.
    botw_gdf_w_forest_deps = botw_gdf_w_forest_deps[
        botw_gdf_w_forest_deps['SEASONAL'].isin(['1', '2', '3'])]

    return botw_gdf_w_forest_deps


def _dissolve(botw_gdf_w_forest_deps):
    """

    :param botw_gdf_w_forest_deps:
    :return:
    """
    # Deep copy botw_geodatabase_gdf_with_forest_deps.
    botw_gdf_w_forest_deps_copy = botw_gdf_w_forest_deps.copy()

    # Filter out the records with season 3 from the season 2 copy and vice versa.
    breeding_gdf = botw_gdf_w_forest_deps[botw_gdf_w_forest_deps['SEASONAL']
        .isin(['1', '2'])]
    non_breeding_gdf = botw_gdf_w_forest_deps_copy[
        botw_gdf_w_forest_deps_copy['SEASONAL']
            .isin(['1', '3'])]

    # Dissolve by SISID.
    breeding_gdf = breeding_gdf.dissolve(by='SISID')
    non_breeding_gdf = non_breeding_gdf.dissolve(by='SISID')

    breeding_gdf.drop('SEASONAL', axis=1)
    non_breeding_gdf.drop('SEASONAL', axis=1)

    breeding_gdf['BREEDING'] = 1
    non_breeding_gdf['BREEDING'] = 0

    breeding_gdf.reset_index(inplace=True)
    non_breeding_gdf.reset_index(inplace=True)

    # Stick them back together.
    dissolved = gpd.GeoDataFrame(pd.concat((breeding_gdf, non_breeding_gdf),
                                           ignore_index=True), crs=breeding_gdf.crs)
    return dissolved


def _clear_dir(dir_path):
    """

    :param dir_path:
    :return:
    """
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path)

    os.mkdir(dir_path)


def _rasterise_gdf(dissolved):
    """Rasterise the

    :param dissolved:
    :return:
    """
    with open(SCI_NAME_RASTER_FILENAME_MAPPING_FP, 'a', newline='') as snrfmf:
        snrfmf_writer = csv.writer(snrfmf)

        for row in dissolved.itertuples():
            sisid_str = str(row.SISID)
            breeding_str = str(row.BREEDING)
            uncompressed_filename = map_sisid_breeding_to_filename(sisid_str,
                                                                   breeding_str,
                                                                   True)
            uncompressed_file_path = os.path.join(RASTER_DIR_PATH,
                                                  uncompressed_filename)

            least_longitude = row.geometry.bounds[0]
            least_latitude = row.geometry.bounds[1]

            longitude_range = row.geometry.bounds[2] - row.geometry.bounds[0]
            latitude_range = row.geometry.bounds[3] - row.geometry.bounds[1]

            pixel_width_float = float(Fraction(PIXEL_WIDTH_STR))
            pixel_height_float = float(Fraction(PIXEL_HEIGHT_STR))

            width = ceil(longitude_range / pixel_width_float)
            height = ceil(latitude_range / pixel_height_float)

            geotransform = (least_longitude, pixel_width_float, 0.0, least_latitude,
                            0.0, pixel_height_float)
            transform = Affine.from_gdal(*geotransform)

            print_w_timestamp('Generating %s...' % uncompressed_filename, end=' ')
            _generate_raster(uncompressed_file_path, width, height, transform,
                             row.geometry)
            print('Done.')

            compressed_filename = map_sisid_breeding_to_filename(sisid_str,
                                                                 breeding_str,
                                                                 False)
            compressed_file_path = os.path.join(RASTER_DIR_PATH, compressed_filename)

            print_w_timestamp('Compressing...', end=' ')
            _compress_raster(uncompressed_file_path, compressed_file_path)
            print('Done.')

            #   Delete uncompressed raster.
            os.remove(uncompressed_file_path)

            # Delete ".tif.aux.xml" file.
            xml_file_path = compressed_file_path + '.aux.xml'
            os.remove(xml_file_path)

            # At this point, I assert that a GeoTIFF has been generated and compressed
            # successfully. Therefore, a mapping is added.
            sci_name = str(row.SCINAME)
            snrfmf_writer.writerow((sci_name, compressed_filename))


def _generate_raster(uncompressed_file_path, width, height, transform, geometry):
    """Generate a raster width pixels wide and height pixels high with geotransform
    transform from the geometry geometry and save it to a GeoTIFF file with path
    uncompressed_file_path.

    :param uncompressed_file_path: Destination file path.
    :param width: Width of the generated raster.
    :param height: Height of the generated raster.
    :param transform: Geotransform of the generated raster.
    :param geometry: Geometry to rasterise.
    """
    with rasterio.open(uncompressed_file_path,
                       'w+',
                       driver='GTiff',
                       width=width,
                       height=height,
                       count=1,
                       dtype=rasterio.uint8,
                       crs='EPSG:4326',
                       transform=transform) as out:
        out_arr = out.read(1)

        # I don't know if I should be setting the all_touched parameter here
        # to true. I guess this isn't a big deal but it might be worth exploring
        # this situation if I want to discuss errors somehow.
        burned = rasterize(shapes=((geometry, 255),),
                           fill=0,
                           out=out_arr,
                           transform=out.transform)
        out.write_band(1, burned)


def _compress_raster(uncompressed_file_path, compressed_file_path):
    """Generate the 1-bit (compressed) GeoTIFF equivalent to the given 8-bit
    (uncompressed) GeoTIFF.

    :param uncompressed_file_path: Path to read the uncompressed raster from.
    :param compressed_file_path: Path to write the compressed raster to.
    """
    options = '-a_nodata 255 -co NBITS=1 -co COMPRESS=CCITTFAX4 -co ' \
              'PHOTOMETRIC=MINISWHITE -ot Byte'
    Translate(compressed_file_path, uncompressed_file_path, options=options)


def _upload_to_gee(local_dir_path, gee_dir_path):
    """Upload rasters from the user's file system to GEE.

    :param local_dir_path: The source directory: a path to a directory in the user's
        file system containing rasters to upload to GEE.
    :param gee_dir_path: The destination directory: a path to a directory in the GEE
        file system to upload the rasters to.
    """
    random_suffix = ''.join(random.choices(string.digits, k=10))
    gcs_raster_dir_path = GCS_BUCKET_PATH + '/' + random_suffix
    os.system('gsutil -m cp -r "%s" %s' % (local_dir_path + '/' + '*',
                                           gcs_raster_dir_path + '/'))

    # Upload to GEE (from GCS).
    raster_filenames = os.listdir(local_dir_path)

    for raster_filename in raster_filenames:
        gcs_file_path = gcs_raster_dir_path + '/' + raster_filename
        asset_id = gee_dir_path + '/' + raster_filename[:-4]

        os.system('earthengine upload image --asset_id %s %s' % (asset_id,
                                                                 gcs_file_path))


def _process_chunk(geodatabase_path, layer_name, forest_dep_df, start_row_no,
                   chunk_size, range_map_ic_gee_path, is_final_chunk):
    """Read, filter, dissolve, rasterise and upload a chunk of the range map
    geodatabase.

    :param geodatabase_path:
    :param layer_name:
    :param forest_dep_df:
    :param start_row_no:
    :param chunk_size:
    :param range_map_ic_gee_path:
    :return:
    """
    chunk_slice = slice(start_row_no, start_row_no + chunk_size)

    # Construct a GeoDataFrame from the range map geodatabase.
    botw_gdf = gpd.read_file(geodatabase_path, layer=layer_name, rows=chunk_slice)

    if not is_final_chunk:
        last_sisid = botw_gdf['SISID'].iloc[-1]
        botw_gdf = botw_gdf[botw_gdf.SISID != last_sisid]

    print_w_timestamp('Read rows %d-%d from "%s" layer.' % (start_row_no,
                                                            start_row_no + len(
                                                                botw_gdf.index) - 1,
                                                            layer_name))

    # Join the GeoDataFrame and the Dataframe.
    botw_gdf_w_forest_deps = botw_gdf.merge(forest_dep_df, on='SISID')
    botw_gdf_w_forest_deps = _filter_gdf(botw_gdf_w_forest_deps)

    if len(botw_gdf_w_forest_deps) > 0:
        print_w_timestamp('Dissolving...', end=' ')
        dissolved = _dissolve(botw_gdf_w_forest_deps)
        print('Done.')

        # If a "rasters" directory exists, delete it (and all of its contents,
        # recursively). The "rasters" directory is deleted at the very end of this
        # script. Therefore, if the last execution of this script was aborted,
        # the "rasters" directory will probably be hanging around.
        _clear_dir(RASTER_DIR_PATH)

        _rasterise_gdf(dissolved)

        print_w_timestamp('Uploading to Google Earth Engine...')
        _upload_to_gee(RASTER_DIR_PATH, range_map_ic_gee_path)
        print('Done.')

        # Delete compressed rasters.
        shutil.rmtree(RASTER_DIR_PATH)
    else:
        print_w_timestamp('All rows filtered out. Moving on to next chunk.')

    no_rows_processed = len(botw_gdf.index)
    final_row_no_processed = start_row_no + no_rows_processed - 1
    return final_row_no_processed


def preprocess(geodatabase_path, layer_name, forest_dep_spreadsheet_path):
    """

    :param geodatabase_path: Path to an ESRI file geodatabase containing range maps
        to be analysed
    :param layer_name: Name of the layer in the geodatabase at geodatabase_path
        containing the range maps to be analysed.
    :param forest_dep_spreadsheet_path: Path to a spreadsheet containing species'
        forest dependency information.
    :return:
    """
    # TODO: This isn't the desired behaviour if the last execution of this script
    #  died halfway through. It makes more sense just to get rid of this. This
    #  mapping file should be deleted in gfc_calculator, I guess, after it's no
    #  longer needed. Although, unless I give this script the capability to start not
    #  from the very beginning, there isn't really any point in this. I suppose it
    #  might make sense to add a start row parameter to the parameter list of the
    #  program. The user would just need to read the row the last execution got up to
    #  from standard output and and then stick this is. However, the user might not
    #  get it exactly right. For example, what if the last chunk contained rows i to
    #  j, but died before processing all of them? It wouldn't be obvious to a user
    #  what row they need to start from and things would get messy. The solution,
    #  really, is just not to use this mapping file...
    if os.path.exists(SCI_NAME_RASTER_FILENAME_MAPPING_FP):
        os.remove(SCI_NAME_RASTER_FILENAME_MAPPING_FP)

    gee_home_folder_path = _get_gee_home_folder_path()

    range_map_ic_name = ''.join(random.choices(string.digits, k=10))
    range_map_ic_gee_path = gee_home_folder_path + '/' + range_map_ic_name

    ee.data.createAsset({'type': 'ImageCollection'}, range_map_ic_gee_path)

    forest_dep_df = _create_forest_dep_df(forest_dep_spreadsheet_path)

    with fiona.open(geodatabase_path) as botw_geodatabase_collection:
        no_rows = len(botw_geodatabase_collection)

    final_row_no_processed = -1

    try:
        while final_row_no_processed < no_rows - 1:
            start_row_no = final_row_no_processed + 1

            # "If this isn't the last chunk".
            if no_rows - 1 - final_row_no_processed > CHUNK_SIZE:
                no_rows_to_read = CHUNK_SIZE
                is_final_chunk = False
            else:
                no_rows_to_read = no_rows - 1 - final_row_no_processed
                is_final_chunk = True

            final_row_no_processed = _process_chunk(geodatabase_path, layer_name,
                                                    forest_dep_df, start_row_no,
                                                    no_rows_to_read,
                                                    range_map_ic_gee_path,
                                                    is_final_chunk)
    finally:
        print_w_timestamp('Waiting for all GEE tasks to complete...')
        wait_until_all_tasks_complete()
        print_w_timestamp('Done')
        # Empty the bucket.
        os.system('gsutil -m rm %s' % GCS_BUCKET_PATH + '/' + '**')

        return range_map_ic_gee_path


# NOTE: This is just here for testing purposes to make it easy to run this script on
#  its own. The CLI and GUI both do the analysis after they do the processing.
if __name__ == '__main__':
    ee.Initialize()

    BOTW_GEODATABASE_PATH = '../Data/BOTW/BOTW.gdb'
    FOREST_DEP_SPREADSHEET_PATH = '../Data/BL_Forest_Dependency_2019.xlsx'
    LAYER_NAME = 'All_Species'

    preprocess(BOTW_GEODATABASE_PATH, LAYER_NAME, FOREST_DEP_SPREADSHEET_PATH)
