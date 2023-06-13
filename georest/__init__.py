#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Interface to Geoserver REST API."""


import datetime as dt
import logging
import os

try:
    import requests
except ImportError:
    requests = None
import trollsift
from geoserver.catalog import Catalog, FailedRequestError
from geoserver.support import DimensionInfo

from georest import utils

__version__ = "0.8.0"

# These layer attributes can be set
LAYER_ATTRIBUTES = ["title", "abstract", "keywords"]
LAYER_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
S3_PROPERTY_URL = "{host}workspaces/{workspace}/coveragestores/{layer_name}/file.imagemosaic?configure=none"
S3_GRANULE_URL = "{host}workspaces/{workspace}/coveragestores/{layer_name}/remote.imagemosaic"
S3_COVERAGE_URL = "{host}workspaces/{workspace}/coveragestores/{layer_name}/coverages"

logger = logging.getLogger(__name__)


def connect_to_gs_catalog(config):
    """Connect to Geoserver."""
    cat = Catalog(config.get("host"),
                  config.get("user"),
                  config.get("passwd"))
    logger.debug("Connected to Geoserver at %s", config.get("host"))

    return cat


def create_workspace(workspace, cat):
    """Create workspace if not already available."""
    if cat.get_workspace(workspace) is None:
        cat.create_workspace(workspace, workspace)
        logger.info("Created workspace '%s'", workspace)


def create_layers(config):
    """Create all configured layers."""
    property_file = utils.create_property_files(config)
    try:
        cat = connect_to_gs_catalog(config)
        _create_layers(config, cat, property_file)
    finally:
        utils.delete_temp(property_file)


def _collect_layer_metadata(config, layer_config):
    """Collect metadata for adding it to a layer."""
    meta = config.get("common_items", dict()).copy()
    meta['host'] = config['host']
    meta.update(layer_config)
    if "title" not in meta and "title_pattern" in meta:
        meta["title"] = meta["title_pattern"]
    meta["layer_name"] = trollsift.compose(meta.get("name", meta.get("layer_pattern")), meta)
    meta["workspace"] = config["workspace"]
    return meta


def _create_layers(config, cat, property_file):
    """Create all configured layers."""
    workspace = config["workspace"]
    time_dim = config["time_dimension"]

    # Make sure the workspace exists
    create_workspace(workspace, cat)

    layer_directories = utils.get_exposed_layer_directories(config)

    # Create all the configured layers and add time dimension
    for layer_config in config["layers"]:
        meta = _collect_layer_metadata(config, layer_config)
        layer_name = meta['layer_name']
        if layer_name is None:
            logger.error("No layer name defined!")
            logger.error("Config items: %s", str(meta))
            continue

        # Write WKT to .prj for all existing files before creating the
        #   layer.  This is optional, and can help with files without
        #   embedded projection metadata, or the embedded metadata is in a format
        #   Geoserver doesn't understand.
        utils.write_wkt_for_files(config, layer_directories[layer_name])

        if _create_layer(cat, workspace, layer_name, property_file):
            if not add_layer_metadata(cat, workspace, layer_name, time_dim, meta):
                continue
            # Delete the empty image from database (does not remove the file)
            for fname in config["properties"].get("files", []):
                delete_granule(cat, workspace, layer_name, fname)


def add_layer_metadata(cat, workspace, layer_name, time_dim, meta):
    """Add metadata for the given layer."""
    coverage = cat.get_resource(workspace=workspace, store=layer_name)
    if coverage is None:
        logger.error("Could not get coverage for workspace '%s' and store '%s'",
                     workspace, layer_name)
        return False
    for attribute in LAYER_ATTRIBUTES:
        if attribute in meta:
            attr = _get_and_clean_attribute(meta[attribute])
            if isinstance(attr, str):
                attr = trollsift.compose(attr, meta)
            setattr(coverage, attribute, attr)

    coverage = _add_time_dimension(coverage, time_dim)
    coverage = _add_cache_age_max(coverage, meta.get("cache_age_max", None))

    # Save the added metadata
    cat.save(coverage)
    logger.info("Metadata written for layer '%s' on workspace '%s'",
                layer_name, workspace)
    return True


def _get_and_clean_attribute(attribute):
    """Get and clean attribute."""
    try:
        # The attribute can be in a text file
        with open(attribute, 'r') as fid:
            attribute = fid.read()
    except (FileNotFoundError, TypeError):
        pass
    try:
        # Or as a string
        attribute = attribute.strip()
    except AttributeError:
        pass

    return attribute


def _create_layer(cat, workspace, layer_name, property_file):
    """Create a layer."""
    if cat.get_store(layer_name, workspace=workspace) is None:
        try:
            create_layer(cat, workspace, layer_name, property_file)
        except FailedRequestError as err:
            logger.error("Failed to create layer '%s' to workspace '%s'",
                         layer_name, workspace)
            logger.error(err)
            return False
    return True


def create_layer(cat, workspace, layer, property_file):
    """Create an image mosaic to a workspace."""
    cat.create_imagemosaic(layer, property_file, workspace=workspace)
    logger.info("Layer '%s' created to workspace '%s'", layer, workspace)


def _add_time_dimension(coverage, time_dim):
    """Add time dimension for the layer."""
    metadata = coverage.metadata.copy()
    time_info = DimensionInfo(
        time_dim["name"],
        time_dim["enabled"],
        time_dim["presentation"],
        time_dim["resolution"],
        time_dim["units"],
        None,
        nearestMatchEnabled=time_dim["nearestMatchEnabled"])
    metadata['time'] = time_info
    coverage.metadata = metadata

    return coverage


def _add_cache_age_max(coverage, cache_age_max):
    """Add maximum cache age parameter to HTTP responses."""
    if cache_age_max is None:
        return coverage
    metadata = coverage.metadata.copy()
    metadata["cacheAgeMax"] = str(cache_age_max)
    metadata["cachingEnabled"] = "true"
    coverage.metadata = metadata

    return coverage


def create_s3_layers(config):
    """Create all configured layers for S3 based imagery."""
    for layer_config in config["layers"]:
        meta = _collect_layer_metadata(config, layer_config)
        property_file = utils.create_property_files(config, metadata=meta)
        try:
            _create_s3_layers(config, property_file, meta)
        finally:
            utils.delete_temp(property_file)


def _create_s3_layers(config, property_file, meta):
    if requests is None:
        raise ImportError("'requests' is needed for S3 layer creation.")
    _send_properties(config, property_file, meta)
    add_s3_granule(config, meta)
    _configure_coverage(config, meta)


def _send_properties(config, property_file, meta):
    url = trollsift.compose(S3_PROPERTY_URL, meta)
    headers = {'Content-type': 'application/zip'}
    auth = (config['user'], config['passwd'])
    with open(property_file, 'rb') as data:
        _ = requests.put(url, data=data, headers=headers, auth=auth)


def add_s3_granule(config, meta):
    """Add a file in S3 bucket to image mosaic."""
    url = trollsift.compose(S3_GRANULE_URL, meta)
    data = meta['image_url']
    headers = {'Content-type': 'text/plain'}
    auth = (config['user'], config['passwd'])
    req = requests.post(url, data=data, headers=headers, auth=auth)
    if req.status_code == requests.codes.ok:
        logger.info(f"Granule '{data} added to '{meta['workspace']}:{meta['layer_name']}'")
    else:
        logger.error("Adding granule '{data}' failed with status code {req.status_code}")


def _configure_coverage(config, meta):
    coverage_xml = _create_coverage_xml(config, meta)
    url = trollsift.compose(S3_COVERAGE_URL, meta)
    headers = {'Content-type': 'text/xml'}
    auth = (config['user'], config['passwd'])
    _ = requests.post(url, data=coverage_xml, headers=headers, auth=auth)


def _create_coverage_xml(config, meta):
    template = config['coverage_template']
    try:
        with open(template, 'r') as fid:
            template = fid.read()
    except (FileNotFoundError, TypeError):
        pass
    meta['title'] = trollsift.compose(meta['title_pattern'], meta)
    meta['abstract'] = trollsift.compose(_get_and_clean_attribute(meta['abstract']), meta)

    return trollsift.compose(template, meta)


def get_layer_coverage(cat, store, store_obj):
    """Get correct layer coverage from a store."""
    coverages = cat.mosaic_coverages(store_obj)

    # Find the correct coverage
    coverage = None
    for cov in coverages["coverages"]["coverage"]:
        if store == cov['name']:
            coverage = cov
            break

    if coverage is None:
        logger.warning("Layer '%s' not found", store)

    return coverage


def get_layer_granules(cat, coverage, store_obj):
    """Get all granules in a layer."""
    granules = cat.list_granules(coverage['name'], store_obj)

    return granules


def add_file_to_mosaic(config, fname_in, filesystem='posix'):
    """Add a file to image mosaic.

    This function wraps some boilerplate around adding a granule to a layer.

    """
    fname = utils.convert_file_path(config, fname_in)
    identity_check_seconds = config.get("identity_check_seconds")

    store = _get_store_name_from_filename(config, fname)

    cat = connect_to_gs_catalog(config)
    workspace = config["workspace"]
    if utils.file_in_granules(cat, workspace, store, fname,
                              identity_check_seconds, config["file_pattern"]):
        return

    # Add the granule metadata to Geoserver
    if filesystem == 'posix':
        # Write WKT to file if configured
        utils.write_wkt(config, fname_in)
        add_granule(cat, workspace, store, fname)
    elif filesystem == 's3':
        meta = {
            'host': config['host'],
            'workspace': workspace,
            'layer_name': store,
            'image_url': fname,
        }
        add_s3_granule(config, meta)
    else:
        raise NotImplementedError("Can't add granules to filesystem '%s'" % filesystem)


def add_granule(cat, workspace, store, file_path):
    """Add a file to image mosaic.

    cat: Geoserver Catalog object
    workspace: name of the used workspace
    store: name of the store/layer where file is added
    file_path: full path where the new file is in the geoserver host machine

    """
    try:
        cat.add_granule(file_path, store, workspace)
        logger.info("Granule '%s' added to '%s:%s'",
                    os.path.basename(file_path), workspace, store)
    except (FailedRequestError, ConnectionRefusedError) as err:
        logger.error("Adding granule '%s' failed: %s", file_path, str(err))


def _get_store_name_from_filename(config, fname):
    """Parse store name from filename."""
    file_pattern = config["file_pattern"]
    file_parts = trollsift.parse(file_pattern, os.path.basename(fname))
    layer_id = file_parts[config["layer_id"]]
    return config["layers"][layer_id]


def delete_file_from_mosaic(config, fname):
    """Delete a file from image mosaic.

    This functions wraps some boilerplate around deleting a granule from a layer.

    """
    store = _get_store_name_from_filename(config, fname)

    cat = connect_to_gs_catalog(config)
    delete_granule(cat, config["workspace"], store, fname)


def delete_granule(cat, workspace, store, fname):
    """Delete a file from image mosaic."""
    fname = os.path.basename(fname)
    store_obj = cat.get_store(store, workspace)

    coverage = get_layer_coverage(cat, store, store_obj)
    granules = get_layer_granules(cat, coverage, store_obj)
    # Find the ID for the file to be removed
    id_ = None
    for granule in granules['features']:
        if fname in granule['properties']['location']:
            id_ = granule['id']
            break
    if id_ is not None:
        cat.delete_granule(coverage['name'], store_obj, id_,
                           workspace)
        logger.info("Granule '%s' removed", fname)


def delete_old_files_from_mosaics_and_fs(config):
    """Delete a file from image mosaic.

    This functions wraps some boilerplate around deleting a granule from a layer.

    """
    cat = connect_to_gs_catalog(config)
    workspace = config["workspace"]
    max_age = dt.datetime.utcnow() - dt.timedelta(minutes=config["max_age"])
    for store in config["layers"].values():
        store_obj = cat.get_store(store, workspace)
        logger.debug("Getting coverage for %s", store)
        coverage = get_layer_coverage(cat, store, store_obj)
        logger.debug("Getting granules for %s", store)
        granules = get_layer_granules(cat, coverage, store_obj)
        for granule in granules['features']:
            tim = dt.datetime.strptime(granule["properties"]["time"], LAYER_TIME_FORMAT)
            if tim.replace(tzinfo=None) < max_age:
                _delete_id_from_gs(cat, workspace, store, store_obj, granule)
                _delete_files_from_fs(config, granule["properties"]["location"])


def _delete_id_from_gs(cat, workspace, store, store_obj, granule):
    id_ = granule["id"]
    fname = os.path.basename(granule["properties"]["location"])
    logger.debug("Removing granule '%s' from %s:%s", fname, workspace, store)
    cat.delete_granule(store, store_obj, id_, workspace)
    logger.info("Granule '%s' removed from %s:%s",
                fname, workspace, store)


def _delete_files_from_fs(config, gs_location):
    delete_files = config.get("delete_files", False)
    if not delete_files:
        return
    fs_path = utils.convert_file_path(config, gs_location, inverse=True)
    _delete_file_from_fs(config, fs_path)
    _delete_file_from_fs(config, fs_path, replace_extension="prj")


def _delete_file_from_fs(config, fs_path, replace_extension=None):
    if replace_extension:
        fs_path = os.path.splitext(fs_path)[0] + "." + replace_extension
    if os.path.exists(fs_path):
        os.remove(fs_path)
        logger.info("File %s deleted", fs_path)
    elif replace_extension is None:
        logger.warning("File %s not available on filesystem", fs_path)
