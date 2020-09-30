# GFC Habitat Loss Estimator

## Description
The GFC Habitat Loss Estimator helps inform bird extinction risk estimates using the the Global Forest Change (GFC) data, made available by Hansen et al.

## Installation
These instructions are written for users without knowledge of programming or using command-line interfaces. (This was the easiest I was able to make installation. Sorry!)

### Prerequisites
An installation of [Anaconda](https://docs.anaconda.com/anaconda/install/) is required.

### Method

#### Downloading the code
Press the green button above labelled "Code" and select "Download ZIP". Save the ZIP
 file somewhere appropriate. When the download finishes, unzip it.

#### Getting Conda ready
1. Open Anaconda Prompt.
2. Paste the following command line into Anaconda Prompt and press <kbd>Enter</kbd>.
    ```
    conda config --add channels conda-forge
    ```
3. Now do the same for the command line below.
    ```
    conda config --set channel_priority strict
    ```

#### Getting Anaconda Prompt running from the right place
For these steps, Anaconda Prompt needs to be running from inside the folder where you
downloaded the code. If you're not used to the command-line way of doing things, the
following steps should help you out.
 
1. To tell Anaconda Prompt to run from inside the folder where you downloaded the code, you need to know a _path_ to this folder. Open up File Explorer and navigate to the folder where you downloaded the code. When you get there, click on the folder icon in the address bar at the top. A path to the folder will appear. Copy this path. We'll paste it in a moment.
2. Open Anaconda Prompt (if it's not already open).
3. In Anaconda Prompt, type `cd`, hit the space bar and then paste the path you just copied. Press <kbd>Enter</kbd>.
4. We've now got Anaconda Prompt where we want it. Keep this window open!

#### Getting a Conda environment set up
1. Paste the following command line into Anaconda Prompt and press <kbd>Enter</kbd>.
    ```
    conda env create -f environment.yml
    ```
2. Now do the same for the command line below.
    ```
    conda activate Bird_Extinction_Risk_Project
    ```

#### Running it!
To launch the GUI, enter the following command line in Anaconda Prompt.
    ```
    python gui.py
    ```
If you're a bit more techy there's also a command-line interface, `cli.py`.

## Inputs
Unfortunately, the tool is very picky about the format of its inputs. It's designed to receive the necessary data in the formats used by BirdLife, hence the peculiarities. 

### Range map geodatabase
An ESRI file geodatabase containing the range maps to be analysed.

### Layer name
The name of the layer in the geodatabase containing the range maps.

### Forest dependency spreadsheet
An Excel spreadsheet specifying species' forest-dependency. The spreadsheet must contain a column titled "SIS ID" and a column titled "Forest dependency". These names must match exactly.

### Altitude limits table
A CSV file specifying species' minimum and maximum altitudes. It must contain 4 columns. The first must contain scientific names, the second minimum altitudes and the third maximum altitudes. The fourth column can contain anything: its values are ignored.

### Generation lengths table
A CSV file specifying species' generation lengths. It must contain two columns. The first must contain species' scientific names and the second must contain species' generation lengths.

### Global canopy cover threshold
This threshold is used throughout the analysis. All pixels in the 2000 tree cover layer of the GFC `Image` which represent areas in which the proportion of canopy cover is less than the global canopy cover threshold are excluded from all calculations.

### AOO tree cover threshold
Due to difficulties with Google Earth Engine and a lack of time, AOO estimates are no longer computed, so this value isn't used. It's still in the GUI to make it easier to add AOO estimation later, if desired.

## Making sense of the output
`breeding`
- `0` means the row corresponds to the species' combined non-breeding range.
- `1` means the row corresponds to the species' combined breeding range.

### Raw tree cover loss and remaining tree cover estimates
`20XY_loss`

The estimated area of tree cover that existed at the end of 2000 within the elevation-clipped range that was lost in 20XY.
 
`20XY_remaining`

The estimated area of tree cover that existed at the end of 2000 within the elevation-clipped range that remained in 20XY.

### Three-generation loss estimates

`3gl_loss`

For each altitude-clipped range map, the area of tree cover loss over three of the relevant species' generation lengths is estimated. Or, if three generation lengths is less than ten years, the loss over the last ten years is estimated instead. When three generation lengths is greater than ten years, the loss estimates are computed differently depending on whether three generation lengths is less than (Case 1) or greater than (Case 2) the length of time covered by the GFC dataset.

#### Case 1
The three-generation loss estimate is the difference between the estimated area of remaining tree cover at the end of the most recent year for which GFC data are available and the estimated area of remaining three generation lengths ago. The latter is computed using linear interpolation.

#### Case 2
The three-generation loss estimate is the difference between the estimated area of remaining tree cover three generation lengths after the end of 2000 and the estimated area of remaining tree cover at the end of 2000. The former is computed using linear regression, with two adjustments.
1. Where linear regression predicts a negative area of remaining tree cover, 0km is taken to be the estimate instead.
2. Where linear regression predicts an area of remaining tree cover which is greater than the estimated area of remaining tree cover in the most recent year, the latter is taken to be the estimate instead.
 
`3gl_start`

The start of the period of time over which the three-generation loss estimate is computed.

`3gl_finish`

The end of the period of time over which the three-generation loss estimate is computed.

`3gl_percent_loss` is the ratio of `3gl_loss` to the estimated area of remaining tree cover at `3gl_start`.

## Editing the configuration file
`config.ini` is a *configuration file*. It lets you change certain values without
 needing to touch the code. The phrases to the left of the `=` symbols are *keys* and
  those to the right of the `=` symbols are *values*. The keys should not be modified.
  
Here's a summary of what the entries in the configuration file mean, and when you
 might want to change them.
 
Key | What is it? | Why might I want to change it?
----|-------------|-------------------------------
`Pixel width` | The width of each pixel in the generated rasters in degrees longitude. | To change the raster resolution.
`Pixel height` | The height of each pixel in the generated rasters in degrees latitude. | To change the raster resolution.
`GFC image GEE asset ID` | The GEE asset ID of the GFC `Image`. | To update to the latest GFC `Image` when a new version becomes available.
`Final year covered by GFC dataset` | The final year for which tree cover loss data are available in the GFC `Image`. | To match an updated version of the GFC `Image`.
`DEM GEE asset ID` | The GEE asset ID of the digital elevation model which is used. | To change to a different digital elevation model.

The remaining keys are to do with Google Cloud Storage, and don't need to be changed
unless the Google Cloud Storage account is changed.

### Example 
To change the pixel width from 1/60 to 1/360, simply change the line:
```
Pixel width = 1/60
```
to
```
Pixel width = 1/360
```

## Granting access to new users
Two Google Cloud Storage _buckets_ are used: one for the rasters that are uploaded to GEE and one for the results that are downloaded from GEE. To use the tool, your account must have access to both. This can be achieved through the Google Cloud Platform Console.

## Known issues

## Authors and acknowledgement
The code in this repository is based on work by Lukasz Tracewski. Many thanks also to
 Hannah Wheatley at BirdLife, and Alison Beresford and Graeme Buchanan at the RSPB!
