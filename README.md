Wrapper library for interacting with Geoserver REST API

## Contribution

Found a bug? Want to implement a new feature? Your contribution is
very welcome!

Small changes and bug fixes can be submitted via pull request. In
larger contributions, premilinary plan is recommended (discussed in
GitHub issues).

CLA is required for larger contributions. Please contact us for more
information!

## Communication

You may contact us from following channels:
* Email: beta@fmi.fi
* GitHub: [issues](../../issues)

# Installation

Below we use Conda to install the dependencies, but also pip and the system package managers can be used.

    conda install requests gisdata six future pyyaml trollsift
    pip install geoserver-restconfig
    pip install https://github.com/fmidev/geoserver-rest.git

# Usage

We assume that the user already has

- installed `georest` (see above) with all the requirements
- an instance of Geoserver running
- credentials to the Geoserver with permissions to add workspaces (optional) and layers

## Creating new image layers

There are two scipts related to layer creation:

- `create_layer_directories.py` - used to create the optional sub-directories with configurable naming to the filesystem on the Geoserver host system
    - The sub-directory creation is optional, but might be useful for splitting the data to reduce the amount of files in a single directory. This script is just a helper to create them programmatically via a configuration file
    - If used, should be run before the layers are created
- `create_layers.py` - creates ImageMosaic layers to Geoserver
- `create_s3_layers.py` - creates ImageMosaic layers to Geoserver when the imagery are in an S3 bucket

The first to scripts can use the same configuration file.

### Configuration file template

The example configuration file can be found from the [`examples/create_layers.yaml`](./examples/create_layers.yaml) file. The inline comments should have all the required information.
Similarly for the S3 case, there is [`examples/create_s3_layers.yaml`](./examples/create_s3_layers.yaml) example config with inline comments.

#### Layer description template

The description text, known by Geoserver as abstract, can be located on a text file. An example is included in [`example/abstract_text.txt`](./examples/abstract_text.txt). In this file, there are placeholders enclosed in curly braces. When used, these placeholders are replaced with the key/value pairs listed in `common_items` dictionary in `create_layers.yaml` (or `create_s3_layers.yaml`). As an example `Sensor: {sensor_title}` would be composed to `Sensor: SEVIRI`. The sole exception is the human readable name, aka. "title",  of the layer (`{product_title}` as placeholder) which will be replaced with the layer's `title` setting in the configuration YAML file or formed from `title_pattern`.

NOTE: After the composition, the abstract text will be as-is, so the comments (lines starting with `#`) should be removed!

### Layer sub-directory creation

As stated above, this step is optional. It is just a configurable programmatical way to create directories.

To create the sub-directories, simply run

    create_layer_directoriesl /path/to/create_layers.yaml

This script doesn't interact with Geoserver in any way. Also, note that after this the directory permissions might need to be adjusted so that Geoserver can use them.

### Creating ImageMosaic layers

When creating ImageMosaic layers, there needs to be at least one image in each of the directories so that Geoserver can determine the projection and extent of the layer. The images can be either proper images pre-copied to the directories, or uploaded by the layer creation script (see keyword `files` in `properties` section of [`examples/create_layers.yaml](./examples/create_layers.yaml) for an example). For S3 case, the prototype image is used from the linked bucket and given per-layer in the `layers` portion of `create_s3_layers.yaml`. If uploaded with the script, it is better to use empty images so the files are smaller. If the image does not have a geolocation information within, additional file containing a single-line WKT1 string with identical filename but with an ending `.prj` needs to be also supplied. As the S3 case uses COG plugin, valid cloud-optimized geotiff images are expected, and no `.prj` files should be necessary.

The layers are created with

    create_layers.py /path/to/create_layers.yaml

or for S3 case

    create_s3_layers.py /path/to/create_s3_layers.yaml

If there are any errors, the erroring layers and all the associated files need to be deleted from Geoserver before attempting again with a fixed configuration file. The layers can be removed via the web UI, but the remaining files need to be cleaned via commandline filesystem access. Possibly also the linked database need to be cleaned.

Any existing layers are left as-is, and will not be overwritten. The scripts will also create the workspace if it doesn't exist.

## Adding new images to existing layers

There are two existing scripts that can be used to add images to existing Geoserver layers. The first `add_granule.py` can be used within other scripts. The other, `posttroll_adder.py`, is run as a daemon and adds images to layers as it receives Posttroll messages.

### `add_granule.py`

This script is ideally used at the end of production or transfer scripts. The command takes two arguments, the configuration filename and the image to be added:

    add_granule.py seviri_europe_15min_granule_config.yaml 20200812_0911_Meteosat-10_EPSG3035_airmass.tif

Both arguments should be given with either a absolute or relative paths. An example configuration file is given in [`examples/granules.yaml`](./examples/granules.yaml), and it should describe all the necessary options.

### `posttroll_adder.py`

The script is used in conjunction of Pytroll production chains. The images are added when a Posttroll message is received, eg. from Trollflow2 (if the data are written directly to the directories seen by Geoserver) or Trollmoves Client or Dispatcher (if the file needs to be first transferred to another location). The script is run, typically via Supervisord, like this:

    posttroll_adder.py /path/to/posttroll_adder.yaml

An example config explaining different options are available in [`examples/posttroll_adder.yaml`](./examples/posttroll_adder.yaml).
