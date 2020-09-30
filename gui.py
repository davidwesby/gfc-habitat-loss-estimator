import tkinter as tk
from tkinter import filedialog
from tkinter.filedialog import askopenfilename

from main import main

FILE_LABELS_WRAPLENGTH = 250
FILE_LABELS_TEXT_COLOUR = 'gray'

gui = tk.Tk()

geodatabase_path = tk.StringVar(gui)
layer_name = tk.StringVar(gui)
forest_deps_path = tk.StringVar(gui)
alt_lims_path = tk.StringVar(gui)
gls_path = tk.StringVar(gui)
global_thresh = tk.DoubleVar(gui)
global_thresh.set(0.5)
aoo_thresh = tk.DoubleVar(gui)
aoo_thresh.set(0.2)


def call_main_with_args():
    main(range_map_geodatabase_path=geodatabase_path.get(),
         layer_name=layer_name.get(),
         forest_dependency_spreadsheet_path=forest_deps_path.get(),
         altitude_limits_table_path=alt_lims_path.get(),
         generation_lengths_table_path=gls_path.get(),
         global_canopy_cover_thresh=global_thresh.get(),
         aoo_canopy_cover_thresh=aoo_thresh.get())


geodatabase_btn = tk.Button(master=gui,
                            text='Select range map geodatabase',
                            command=lambda:
                            geodatabase_path.set(filedialog.askdirectory()))
geodatabase_labl = tk.Label(master=gui,
                            textvariable=geodatabase_path,
                            wraplength=FILE_LABELS_WRAPLENGTH,
                            fg=FILE_LABELS_TEXT_COLOUR)

layer_name_labl = tk.Label(master=gui,
                           text='Enter layer name')
layer_name_entr = tk.Entry(master=gui,
                           textvar=layer_name)

forest_deps_btn = tk.Button(master=gui,
                            text='Select forest dependency spreadsheet',
                            command=lambda: forest_deps_path.set(askopenfilename()))
forest_deps_labl = tk.Label(master=gui,
                            textvariable=forest_deps_path,
                            wraplength=FILE_LABELS_WRAPLENGTH,
                            fg=FILE_LABELS_TEXT_COLOUR)

alt_lims_btn = tk.Button(master=gui,
                         text='Select altitude limits table',
                         command=lambda: alt_lims_path.set(askopenfilename()))
alt_lims_labl = tk.Label(master=gui,
                         textvariable=alt_lims_path,
                         wraplength=FILE_LABELS_WRAPLENGTH,
                         fg=FILE_LABELS_TEXT_COLOUR)

gls_btn = tk.Button(master=gui,
                    text='Select generations lengths table',
                    command=lambda: gls_path.set(askopenfilename()))
gls_labl = tk.Label(master=gui,
                    textvariable=gls_path,
                    wraplength=FILE_LABELS_WRAPLENGTH,
                    fg=FILE_LABELS_TEXT_COLOUR)

global_thresh_labl = tk.Label(master=gui,
                              text='Enter global canopy cover threshold')
global_thresh_entr = tk.Entry(master=gui,
                              textvar=global_thresh)

aoo_thresh_labl = tk.Label(master=gui,
                           text='Enter AOO tree cover threshold')
aoo_thresh_entr = tk.Entry(master=gui,
                           textvar=aoo_thresh)

submit_btn = tk.Button(master=gui,
                       text='Submit',
                       command=call_main_with_args,
                       fg='green')


# Add widgets to the GUI.
row_no = 1
geodatabase_btn.grid(row=row_no, column=1, sticky='ew')
row_no += 1
geodatabase_labl.grid(row=row_no, column=1)
row_no += 1
layer_name_labl.grid(row=row_no, column=1)
row_no += 1
layer_name_entr.grid(row=row_no, column=1, sticky='ew')
row_no += 1
forest_deps_btn.grid(row=row_no, column=1, sticky='ew')
row_no += 1
forest_deps_labl.grid(row=row_no, column=1)
row_no += 1
alt_lims_btn.grid(row=row_no, column=1, sticky='ew')
row_no += 1
alt_lims_labl.grid(row=row_no, column=1)
row_no += 1
gls_btn.grid(row=row_no, column=1, sticky='ew')
row_no += 1
gls_labl.grid(row=row_no, column=1)
row_no += 1
global_thresh_labl.grid(row=row_no, column=1)
row_no += 1
global_thresh_entr.grid(row=row_no, column=1, sticky='ew')
row_no += 1
aoo_thresh_labl.grid(row=row_no, column=1)
row_no += 1
aoo_thresh_entr.grid(row=row_no, column=1, sticky='ew')
row_no += 1
submit_btn.grid(row=row_no, column=1, sticky='ew')

gui.title('GFC Habitat Loss Estimator')
gui.resizable(False, False)

gui.mainloop()
