import csv
import os
from configparser import ConfigParser

import numpy as np
from sklearn.linear_model import LinearRegression

MODULE_PARENT_DIR_PATH = os.path.dirname(os.path.realpath(__file__))
RESULTS_FILE_PATH = os.path.join(MODULE_PARENT_DIR_PATH, 'combined_results.csv')


def _populate_gl_dict(gl_fp):
    """Read the generation lengths table and return a mapping from species to
    generation lengths.

    :param gl_fp: Path to a CSV file containing species' generation lengths. See
        README for required format.
    :return: A dictionary mapping species to generation lengths.
    """
    with open(gl_fp, newline='') as gl_file:
        gl_file_reader = csv.DictReader(gl_file, fieldnames=['sci_name', 'gl'])
        gl_dict = {row['sci_name']: row['gl'] for row in gl_file_reader}

    return gl_dict


def _estimate_3gl_tc_area_loss(sci_name, remaining, gl_dict, gfc_final_yr):
    """Estimate the area of three cover loss within the range map being analysed over
    three generation lengths of the corresponding species. Where three generation
    lengths falls within the time period covered by the GFC data, the loss is
    interpolated. Where this is not the case, extrapolation is used.

    :param sci_name: The scientific name of the species being analysed.
    :param remaining: A dictionary in which each entry maps a year to the estimated
        area of remaining tree cover within the range map being analysed.
    :param gl_dict: A dictionary in which each entry maps the scientific name of a
        species to its average generation length.
    :param gfc_final_yr: The final year covered by the GFC Image being used.
    :return: A tuple (start, finish, loss, percentage_loss) in which loss is equal to
        (the estimated area of remaining tree cover at finish) - (the estimated area of
        remaining tree cover at start), and percentage_loss is equal to loss / (the
        estimated area of remaining tree cover at start).
    """
    #   Estimate tree cover loss within three generations.
    gl = float(gl_dict[sci_name])
    if 3 * gl > gfc_final_yr - 2000:
        start = 2001
        finish = 2001 + 3 * gl

        #   Perform (an adaptation of) linear regression.
        lin_reg = LinearRegression()
        lin_reg.fit(np.fromiter(remaining.keys(), dtype=int).reshape(-1, 1),
                    np.fromiter(remaining.values(), dtype=float).reshape(-1, 1))

        #   Estimate must be less than or equal to the area of tree cover which
        #   existed in 2000 and remains in 2020 and greater than or equal to 0.
        loss = min(max(lin_reg.predict(np.array(finish).reshape(-1, 1)), 0),
                   remaining[gfc_final_yr + 1])

        start_tc_area = remaining[start]

    else:
        start = min(gfc_final_yr + 1 - 3 * gl, gfc_final_yr + 1 - 10)
        finish = gfc_final_yr + 1
        offset = start - np.floor(start)

        lower_pt = remaining[np.floor(start)]
        upper_pt = remaining[np.ceil(start)]

        start_tc_area = lower_pt + (upper_pt - lower_pt) * offset

        loss = start_tc_area - remaining[finish]

    percentage_loss = (loss / start_tc_area) * 100

    return start, finish, loss, percentage_loss


def _postprocess_results_set_write_to_file(results_dict, gl_table_path, fields,
                                           gfc_final_yr):
    """Derive estimates of remaining tree cover from the loss estimates returned by
    GEE, use them to compute three-generation-length estimates and write a row
    containing all the results to the output file.

    :param results_dict: A dictionary containing the results returned by GEE.
    :param gl_table_path: Path to a CSV file containing species' generation
        lengths. See README for required format.
    :param fields: A list of strings which are used as column headings in the output
        CSV file.
    :param gfc_final_yr: The final year covered by the GFC Image being used.
    :return:
    """
    with open(RESULTS_FILE_PATH, 'a') as combined_results_file:
        dw = csv.DictWriter(combined_results_file, fieldnames=fields)

        gl_dict = _populate_gl_dict(gl_table_path)

        #   Add estimates of remaining tree cover to loss_dict.
        remaining_value = float(results_dict['2001_remaining'])

        remaining_dict = {2001: remaining_value}
        results_dict['2000_remaining'] = remaining_value

        for year in range(2002, gfc_final_yr + 2):
            loss_key = str(year - 1) + '_loss'
            remaining_value -= float(results_dict[loss_key])
            remaining_dict[year] = remaining_value

            remaining_key = str(year - 1) + '_remaining'
            results_dict[remaining_key] = remaining_value

        sci_name = results_dict['sci_name']

        start, finish, loss, percent_loss = _estimate_3gl_tc_area_loss(
            sci_name, remaining_dict, gl_dict, gfc_final_yr)

        results_dict['3gl_start'] = start
        results_dict['3gl_finish'] = finish
        results_dict['3gl_loss'] = loss
        results_dict['3gl_percent_loss'] = percent_loss

        # Write results
        dw.writerow(results_dict)


def postprocess(gl_table_path):
    """Post-process the results for every range map which was analysed: process the
    results files in the storage bucket, derive additional results and write
    everything to an output file.

    :param gl_table_path: Path to a CSV file containing species' generation
        lengths. See README for required format.
    :return:
    """
    # NOTE: Here it's being assumed that all the results are already
    #  in the bucket. I doubt there's much to be gained by doing things one by one when
    #  each set of results becomes available, and it would be a lot more complex.
    # Read bucket name from configuration file.
    module_parent_dir_path = os.path.dirname(os.path.realpath(__file__))
    config_file_path = os.path.join(module_parent_dir_path, 'config.ini')
    config_parser = ConfigParser()
    config_parser.read(config_file_path)
    BUCKET_NAME = config_parser['DEFAULT']['GCS bucket name for results']
    LOCAL_RESULTS_DIR_PATH = 'gee-results'

    # Copy contents of bucket to LOCAL_RESULTS_DIR_PATH.
    if not os.path.exists(LOCAL_RESULTS_DIR_PATH):
        os.mkdir(LOCAL_RESULTS_DIR_PATH)
    os.system('gsutil -m cp gs://%s/** %s' % (BUCKET_NAME, LOCAL_RESULTS_DIR_PATH))
    # Empty bucket.
    # os.system('gsutil rm gs://%s' % BUCKET_NAME)

    results_filenames = os.listdir(LOCAL_RESULTS_DIR_PATH)
    # Read value for gfc_final_yr from config file.
    config_parser = ConfigParser()
    config_parser.read(config_file_path)
    gfc_final_yr = config_parser.getint('DEFAULT', 'Final year covered by GFC dataset')

    fields = ['sisid', 'sci_name', 'breeding'] + \
             ['20%s_loss' % str(n).zfill(2) for n in range(1, gfc_final_yr - 2000 +
                                                           1)] + \
             ['20%s_remaining' % str(n).zfill(2) for n in range(0, gfc_final_yr -
                                                                2000 + 1)] + \
             ['3gl_start', '3gl_finish', '3gl_loss', '3gl_percent_loss']

    with open('combined_results.csv', 'w') as combined_results_file:
        dw = csv.DictWriter(combined_results_file, fieldnames=fields)
        dw.writeheader()

    for results_filename in results_filenames:
        results_file_path = os.path.join(LOCAL_RESULTS_DIR_PATH, results_filename)
        with open(results_file_path, newline='') as results_file:
            results_reader = csv.DictReader(results_file)
            for results_dict in results_reader:
                del results_dict['system:index']
                del results_dict['.geo']

                _postprocess_results_set_write_to_file(results_dict, gl_table_path,
                                                       fields, gfc_final_yr)

        os.remove(results_file_path)
