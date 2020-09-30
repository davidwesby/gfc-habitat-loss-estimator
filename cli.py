import argparse

from main import main

arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('range_map_geodatabase_path',
                        help='Path to ESRI file geodatabase containing species range '
                             'maps')
arg_parser.add_argument('layer_name',
                        help='Name of layer in geodatabase containing range maps')
arg_parser.add_argument('forest_dependency_spreadsheet_path',
                        help='Path to Excel spreadsheet containing forest dependency '
                             'information')
arg_parser.add_argument('altitude_limits_table_path',
                        help='Path to CSV file containing species altitude limits')
arg_parser.add_argument('generation_lengths_table_path',
                        help='Path to CSV file containing species generation lengths')
arg_parser.add_argument('global_canopy_cover_threshold',
                        help='Global canopy cover threshold')
arg_parser.add_argument('aoo_canopy_cover_threshold',
                        help='AOO canopy cover threshold')

args = arg_parser.parse_args()

main(args.range_map_geodatabase_path,
     args.layer_name,
     args.forest_dependency_spreadsheet_path,
     args.global_canopy_cover_threshold,
     args.aoo_canopy_cover_threshold,
     args.altitude_limits_table_path,
     args.generation_lengths_table_path)
