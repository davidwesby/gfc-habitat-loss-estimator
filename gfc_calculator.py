#!/usr/bin/python

# Global Forest Change calculator for provided species' distributions maps

import csv
import os
import random
import string
import warnings
from configparser import ConfigParser

import ee
import collections

from ee.batch import Export

from utilities import SCI_NAME_RASTER_FILENAME_MAPPING_FP, \
    map_filename_to_sisid_breeding

MODULE_PARENT_DIR_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE_PATH = os.path.join(MODULE_PARENT_DIR_PATH, 'config.ini')

# Note that this is greater than the height in metres of the highest point on Earth.
MAX_ALT = 10000

# TODO: I wonder whether this should go in the config file, really.
SCALE = 600
MAX_PIXELS = 1e13
BEST_EFFORT = False

config_parser = ConfigParser()
config_parser.read(CONFIG_FILE_PATH)

GFC_IMG_ASSET_ID = config_parser['DEFAULT']['GFC image GEE asset ID']
GFC_FINAL_YR = config_parser.getint('DEFAULT', 'Final year covered by GFC dataset')
DEM_ASSET_ID = config_parser['DEFAULT']['DEM GEE asset ID']
BUCKET_NAME = config_parser['DEFAULT']['GCS bucket name for results']

GFC_IMG = None
DEM = None

RANGE_MAP_IC_GEE_PATH = ''
RANDOM_DIR_NAME = ''.join(random.choices(string.ascii_lowercase, k=8))


class _Species(object):

    def __init__(self, asset_id, min_alt, max_alt):
        """Initialise _Species object with the necessary information: a GEE asset ID
        and a minimum and maximum altitude.

        :param asset_id: GEE asset ID of a range map Image.
        :param min_alt: Minimum altitude of the species being analysed.
        :param max_alt: Maximum altitude of the species being analysed.
        """
        self._asset_id = asset_id
        self._min_alt = min_alt
        self._max_alt = max_alt

    def __call__(self, forest_change_img):
        """This function is mapped over the ImageCollection of GFC Images. It
        computes the area of forest_change_img within the range map which is being
        analysed.

        :param forest_change_img: An Image derived from the GFC Image.
        """
        species = ee.Image(RANGE_MAP_IC_GEE_PATH + '/' + self._asset_id)
        # Clip elevation map with species-specific altitude limits
        alt_range = DEM.gte(self._min_alt).And(DEM.lte(self._max_alt)).selfMask()

        forest_change_img_clipped = forest_change_img.And(alt_range).And(species)

        area = forest_change_img_clipped.reduceResolution(reducer=ee.Reducer.mean(),
                                                          maxPixels=6000). \
            reproject(crs='EPSG:4326', scale=SCALE). \
            multiply(ee.Image.pixelArea().divide(1000000)). \
            reduceRegion(reducer=ee.Reducer.sum(),
                         scale=SCALE,
                         maxPixels=MAX_PIXELS,
                         geometry=forest_change_img_clipped.geometry())

        # Copy over the properties of the original image.
        area_img = forest_change_img_clipped.copyProperties(forest_change_img)

        # Store the calculated area as a property of the image.
        gee_returns = forest_change_img.get('gee_returns')
        area_img = area_img.set(ee.String('area'), area.get(gee_returns))

        return area_img


def _initialise_gee_img_vars():
    """Initialise global variables whose values are GEE Images."""
    global GFC_IMG, DEM

    GFC_IMG = ee.Image(GFC_IMG_ASSET_ID)
    DEM = ee.Image(DEM_ASSET_ID)


def _populate_altitude_lims_dict(altitude_fp):
    """Create a mapping between scientific names to minimum and maximum altitudes.

    :param altitude_fp: Path to a CSV file which represents a table of altitude
        limits. There must be 4 columns. The first must contain scientific names; the
        second must contain minimum altitudes; the third must contain maximum altitudes,
        and the fourth can contain anything: its values are ignored. The reason this
        redundant column is expected is to allow this function to parse the altitude
        limits table that was sent to me by BirdLife ("Altitude_BL_Davies.csv"), in
        which the fourth column contains the sources of the altitude limits.
    :return:
    """
    # Read altitude limits
    Altitude = collections.namedtuple('Altitude', 'min max')

    # All this block does is populate alt_info.
    with open(altitude_fp, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        alt_info = {}
        for species, min_alt, max_alt, _ in reader:
            if min_alt == 'NA':
                # warnings.warn('Invalid minimum altitude ' + min_alt + ' for species ' +
                #               species + '. Setting minimum altitude to zero.',
                #               UserWarning)
                min_alt = 0
            if max_alt == 'NA':
                # warnings.warn('Invalid maximum altitude ' + max_alt + ' for species ' +
                #               species + '. Setting maximum altitude to ' + str(
                #     MAX_ALT) +
                #               '.', UserWarning)
                max_alt = MAX_ALT

            alt_info[species] = Altitude(min=float(min_alt), max=float(max_alt))

    return alt_info


def _create_gfc_ic(gfc_img, gfc_final_yr, canopy_cover_thresh):
    """Create an ImageCollection of Images derived from the GFC Image.

    :param gfc_img: The Hansen GFC Image being used.
    :param gfc_final_yr: The final year covered by the GFC Image being used.
    :param canopy_cover_thresh: Pixels in the "treecover2000" layer with an
        intensity less than this threshold are excluded from all computations: they
        are not counted as tree cover.
    :return: An ImageCollection containing a set of Images derived from bands of the
        Hansen GFC Image.
    """
    # treecover2000_img = gfc_img.select(['treecover2000']).divide(100).gte(
    #     canopy_cover_thresh)
    treecover2000_img = gfc_img.select(['treecover2000']).divide(100)
    lossyear_img = gfc_img.select(['lossyear']).mask(treecover2000_img)

    hansen = [treecover2000_img.multiply(ee.Image.pixelArea())
                  .set('forest', '2001_remaining', 'gee_returns',
                       'treecover2000')]
    hansen += [
        treecover2000_img.mask(lossyear_img.eq(year)).multiply(ee.Image.pixelArea())
            .set('forest', '20' + str(year).zfill(2) + '_loss',
                 'gee_returns',
                 'treecover2000') for year in range(1, gfc_final_yr - 2000 + 1)]
    gfc_ic = ee.ImageCollection.fromImages(hansen)

    return gfc_ic


def _populate_sci_name_raster_filename_mapping(sci_name_raster_filename_mapping_fp):
    """Populate a mapping which maps species' scientific names to raster filenames
    for the given species.

    :param sci_name_raster_filename_mapping_fp: A CSV file without column headings
        which associates scientific names with the names of rasters generated for the
        relevant species.
    :return: A list of 2-tuples mapping species' scientific names to raster filenames
        for the given species.
    """
    #   TODO: I'm not sure this is the best approach. I just need to iterate over the
    #    elements of the range_map_rasters ImageCollection. Instead of taking a path
    #    to this mapping file, all this function really needs is a path from the root
    #    of the GEE file system to the ImageCollection containing all the rasters.
    #    Then, I just need some way of getting a list of all the elements of an
    #    ImageCollection and then a way to map an image asset ID to a scientific name.
    # I think the obvious answer to the latter point is to make the scientific names
    # properties.
    with open(sci_name_raster_filename_mapping_fp, 'r') as snrfmf:
        reader = csv.reader(snrfmf)
        sci_name_raster_filename_mapping = [(row[0], row[1]) for row in reader]

        return sci_name_raster_filename_mapping


# TODO: I think it might be better for everything from min_alt to breeding to be made
#  Image properties.
def _run(asset_id, gfc_ic, min_alt, max_alt, sci_name, sisid, breeding, aoo_thresh):
    """Ask GEE to compute the tree cover loss estimates.

    :param asset_id: GEE asset ID of the range map being analysed.
    :param gfc_ic: ImageCollection containing GFC Images. The range map with GEE
        asset ID asset_id is laid on top of these Images.
    :param min_alt: The minimum altitude of the species with scientific name sci_name.
    :param max_alt: The maximum altitude of the species with scientific name sci_name.
    :param sci_name: The scientific name of the species being analysed.
    :param sisid: The SIS ID of the species with scientific name sci_name.
    :param breeding: 0 if the range map being analysed is the combined non-breeding
        range and 1 if it's the combined breeding range.
    :param aoo_thresh: 2km by 2km grid cells containing a proportion of
        tree cover greater than aoo_canopy_cover_thresh are counted as forested cells
        for the purpose of AOO estimation.
    :return:
    """
    species = _Species(asset_id, min_alt, max_alt)
    gfc_ic_with_areas = gfc_ic.map(species)

    result_names_gee_list = gfc_ic_with_areas.aggregate_array('forest')
    result_values_gee_list = gfc_ic_with_areas.aggregate_array('area')
    results_gee_dict = ee.Dictionary.fromLists(result_names_gee_list,
                                               result_values_gee_list)

    # aoo_dict = estimate_aoo(asset_id, min_alt, max_alt, aoo_thresh)
    # results_gee_dict = results_gee_dict.combine(aoo_dict)

    results_gee_dict = results_gee_dict.set('sci_name', sci_name)
    results_gee_dict = results_gee_dict.set('sisid', sisid)
    results_gee_dict = results_gee_dict.set('breeding', breeding)

    results_feat = ee.Feature(None, results_gee_dict)
    results_feat_collection = ee.FeatureCollection([results_feat])

    # FIXME: Again, this is a problem if two users want to use the application
    #  concurrently.
    export_task = Export.table.toCloudStorage(results_feat_collection,
                                              description=asset_id,
                                              bucket=BUCKET_NAME,
                                              fileNamePrefix=RANDOM_DIR_NAME + '/' +
                                              asset_id)
    export_task.start()


# NOTE: This function is unused but has been left in the code in case someone else
# would like to have a go at getting AOO estimation working in GEE.
def _estimate_aoo(asset_id, min_alt, max_alt, aoo_thresh):
    tc_2000_img = GFC_IMG.select('treecover2000')
    loss_img = GFC_IMG.select('loss')

    tc_2020_img = tc_2000_img.where(loss_img.unmask(), 0)

    range_img = ee.Image(RANGE_MAP_IC_GEE_PATH + '/' + asset_id)

    # Clip elevation map with species-specific altitude limits.
    alt_range_img = DEM.gte(min_alt).And(DEM.lte(max_alt))

    # Clip species range map with altitude information.
    alt_clipped_range_img = alt_range_img.And(range_img)

    aoo_img = tc_2020_img.multiply(alt_clipped_range_img). \
        reproject(tc_2000_img.projection().crs(), scale=2000). \
        divide(100). \
        gte(aoo_thresh). \
        multiply(ee.Image.pixelArea().divide(1000000))

    aoo_gee_dict = aoo_img.reduceRegion(reducer=ee.Reducer.unweighted(ee.Reducer.sum()),
                                        geometry=aoo_img.geometry(),
                                        scale=2000,
                                        maxPixels=MAX_PIXELS,
                                        bestEffort=BEST_EFFORT)

    return aoo_gee_dict.rename(['treecover2000'], ['aoo'])


def analyse(alt_lims_table_path, range_map_ic_gee_path, global_canopy_cover_thresh=0.5,
            aoo_thresh=0.2):
    """Create and start export tasks to get tree cover loss estimates for each
        species in the the scientific name, raster filename mapping file.

    :param alt_lims_table_path: Path to a CSV file containing species' minimum and
        maximum altitudes. See README for required format.
    :param range_map_ic_gee_path: GEE path to an ImageCollection containing range map
        rasters.
    :param global_canopy_cover_thresh: Pixels in the "treecover2000" layer with an
        intensity less than this threshold are excluded from all computations: they
        are not counted as tree cover.
    :param aoo_thresh: 2km by 2km grid cells containing a proportion of
        tree cover greater than aoo_canopy_cover_thresh are counted as forested cells
        for the purpose of AOO estimation.
    """
    _initialise_gee_img_vars()

    global RANGE_MAP_IC_GEE_PATH
    RANGE_MAP_IC_GEE_PATH = range_map_ic_gee_path

    alt_lims_dict = _populate_altitude_lims_dict(alt_lims_table_path)

    gfc_ic = _create_gfc_ic(GFC_IMG, GFC_FINAL_YR, global_canopy_cover_thresh)

    sci_name_raster_filename_mapping = _populate_sci_name_raster_filename_mapping(
        SCI_NAME_RASTER_FILENAME_MAPPING_FP)

    for sci_name, raster_filename in sci_name_raster_filename_mapping:
        print('Creating export task for %s (%s)...' % (raster_filename,
                                                       sci_name.lower()), end=' ')
        asset_id = raster_filename[:-4]
        if sci_name in alt_lims_dict:
            min_alt = alt_lims_dict[sci_name].min
            max_alt = alt_lims_dict[sci_name].max
        else:
            min_alt = 0
            max_alt = MAX_ALT

        sisid_breeding_dict = map_filename_to_sisid_breeding(raster_filename)
        sisid = sisid_breeding_dict['sisid']
        breeding = sisid_breeding_dict['breeding']

        _run(asset_id, gfc_ic, min_alt, max_alt, sci_name, sisid, breeding, aoo_thresh)
        print('Done.')


# NOTE: This is just here for testing. This makes it possible to run the analysis
#  without having to wait for preprocessing.
if __name__ == '__main__':
    ALTITUDE_FP = '../data/Altitude_BL_Davies.csv'

    analyse(ALTITUDE_FP)
