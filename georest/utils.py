#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Utility functions for georest."""

import datetime as dt
import glob
import logging
import logging.config
import os
import shutil
import tempfile
import zipfile

import trollsift
import yaml

import georest

logger = logging.getLogger(__name__)


def read_config(fname):
    """Read configuration file."""
    with open(fname, 'r') as fid:
        config = yaml.load(fid, yaml.SafeLoader)
    if "user" not in config:
        config["user"] = os.environ.get("GEOSERVER_USER", "admin")
    if "passwd" not in config:
        config["passwd"] = os.environ.get("GEOSERVER_PASSWORD", "geoserver")
    return config


def delete_temp(temp_path):
    """Delete temporary directory."""
    shutil.rmtree(os.path.dirname(temp_path))
    logger.debug("Temporary file deleted")


def create_property_files(config, metadata=None):
    """Create .property files, save them to zip and return the path to it."""
    logger.debug("Creating property files")
    path = tempfile.mkdtemp()
    zip_path = os.path.join(path, "data.zip")
    properties = config["properties"]

    prop_paths = _write_property_files(properties, path, metadata)
    _write_property_zip(prop_paths, zip_path)

    return zip_path


def _write_property_files(properties, path, metadata):
    """Write *properties* to a file in *path*."""
    prop_paths = []
    for prop in properties:
        prop_path = os.path.join(path, prop)
        if prop == "files":
            for prop_path in properties[prop]:
                prop_paths.append(prop_path)
        else:
            with open(prop_path, 'w') as fid:
                for key, value in properties[prop].items():
                    data = "%s=%s\n" % (key, value)
                    if metadata:
                        data = trollsift.compose(data, metadata, allow_partial=True)
                    fid.write(data)
            logger.debug("Wrote '%s'", prop)
            prop_paths.append(prop_path)

    return prop_paths


def _write_property_zip(prop_paths, zip_path):
    """Put files in *prop_paths* in a zip file in *zip_path*."""
    with zipfile.ZipFile(zip_path, mode="w") as package:
        for prop in prop_paths:
            package.write(prop, os.path.basename(prop))
            logger.debug("Added '%s' to 'data.zip'", os.path.basename(prop))

    return zip_path


def convert_file_path(config, file_path, inverse=False):
    """Convert given file path to internal directory structure."""
    basename = os.path.basename(file_path)
    if inverse:
        new_dir = config["exposed_base_dir"]
    else:
        new_dir = config["geoserver_target_dir"]

    path = os.path.join(new_dir, basename)

    return path


def get_exposed_layer_directories(config):
    """Get full directory paths to each configured layer."""
    exposed_base_dir = config.get("exposed_base_dir")
    create_subdirectories = config.get("create_subdirectories", True)
    if exposed_base_dir is None:
        logger.warning("No 'exposed_base_dir' given in config, using "
                       "current directory")
        exposed_base_dir = os.path.curdir

    dirs = {}
    common_items = config.get("common_items", dict())
    for layer_config in config["layers"]:
        meta = common_items.copy()
        meta.update(layer_config)
        layer_name = trollsift.compose(
            meta.get("name", meta.get("layer_pattern")), meta)
        if create_subdirectories:
            path = os.path.join(exposed_base_dir, layer_name)
        else:
            path = exposed_base_dir
        dirs[layer_name] = path

    return dirs


def write_wkt(config, image_fname):
    """Write WKT text besides the image file.

    The WKT filename is the same as *image_fname*, but the ending is '.prj'.
    """
    wkt = config.get("write_wkt")
    if wkt:
        if os.path.exists(image_fname):
            wkt_fname = os.path.splitext(image_fname)[0] + '.prj'
        else:
            directory = config["exposed_target_dir"]
            fname = os.path.basename(image_fname)
            wkt_fname = os.path.join(directory, os.path.splitext(fname)[0] + '.prj')
        with open(wkt_fname, 'w') as fid:
            fid.write(wkt)
        logger.debug("Wrote projection file: %s", wkt_fname)


def write_wkt_for_files(config, path):
    """Write WKT text besides all files in *path*."""
    for fname in glob.glob(os.path.join(path, '*')):
        # Skip projection files and directories
        if fname.endswith('.prj') or os.path.isdir(fname):
            continue
        try:
            write_wkt(config, fname)
        except PermissionError:
            logger.warning("Could not write .prj file for %s", fname)


def file_in_granules(cat, workspace, store, file_path, identity_check_seconds, file_pattern):
    """Check if a file is already in the layer granules.

    cat: Geoserver Catalog object
    workspace: name of the used workspace
    store: name of the store/layer where file is added
    file_path: full path where the new file is in the geoserver host machine
    identity_check_seconds: compare for file time identity with this tolerance
                            with files already in Geoserver.
    file_pattern: Trollsift filename pattern.  If *identity_check_seconds* match,
                  also other filename parts are compared.  If all match, return True.
    """
    if identity_check_seconds is not None and file_pattern is not None:
        store_obj = cat.get_store(store, workspace)
        coverage = georest.get_layer_coverage(cat, store, store_obj)
        granules = georest.get_layer_granules(cat, coverage, store_obj)
        for granule in granules["features"]:
            if _file_equals_granule(file_path, granule, identity_check_seconds, file_pattern):
                return True
    return False


def _file_equals_granule(file_path, granule, identity_check_seconds, file_pattern):
    """Check if a file matches the given granule."""
    file_parts = trollsift.parse(file_pattern, os.path.basename(file_path))
    granule_path = granule["properties"]["location"]
    granule_parts = trollsift.parse(file_pattern, os.path.basename(granule_path))
    time_diff = file_parts.pop("start_time") - granule_parts.pop("start_time")
    if abs(time_diff.total_seconds()) > identity_check_seconds:
        return False
    else:
        all_identical = True
        for key in file_parts:
            if file_parts[key] != granule_parts[key]:
                all_identical = False
                break
        if all_identical:
            logger.info("Matching granule already exists. New: %s, old: %s",
                        file_path, granule_path)
            return True
    return False


def run_posttroll_adder(config, Subscribe):
    """Run granule adder using Posttroll messaging.

    Restart if configured restart timeout happens between incoming messages.
    """
    restart_timeout = config.get("restart_timeout")
    while True:
        logger.debug("Starting Posttroll adder loop")
        if _posttroll_adder_loop(config, Subscribe, restart_timeout):
            logger.info("Posttroll Geoserver updater stopped.")
            return


def _posttroll_adder_loop(config, Subscribe, restart_timeout):
    """Run adder until exit via KeyboardInterrupt happens.

    Return False if no messages have been received within given time.
    """
    cat = georest.connect_to_gs_catalog(config)

    latest_message_time = dt.datetime.utcnow()

    topics = config["topics"]
    services = config.get("services", "")
    nameserver = config.get("nameserver", "localhost")
    addresses = config.get("addresses")
    addr_listener = config.get("use_address_listener", True)
    return_value = False
    with Subscribe(services=services, topics=topics, nameserver=nameserver,
                   addresses=addresses, addr_listener=addr_listener) as sub:
        try:
            for msg in sub.recv(1):
                if restart_timeout:
                    time_since_last_msg = dt.datetime.utcnow() - latest_message_time
                    time_since_last_msg = time_since_last_msg.total_seconds() / 60.
                    if time_since_last_msg > restart_timeout:
                        logger.debug("%.0f minutes since last message",
                                     time_since_last_msg)
                        return return_value
                if msg is None:
                    continue
                logger.debug("New message received: %s", str(msg))
                latest_message_time = dt.datetime.utcnow()
                try:
                    _process_message(cat, config.copy(), msg)
                except ValueError:
                    logger.warning("Filename pattern doesn't match.")
            # This is a workaround for the unit tests
            return_value = True
        except KeyboardInterrupt:
            return_value = True
        finally:
            return return_value  # noqa:B012


def _process_message(cat, config, msg):
    """Process posttroll message."""
    prod = msg.data["productname"]
    store = config["layers"].get(prod)
    workspace = config["workspace"]
    config["store"] = store
    identity_check_seconds = config.get("identity_check_seconds")
    file_pattern = config.get("file_pattern")
    filesystem = config.get("filesystem", "posix")

    fname = convert_file_path(config, msg.data["uri"])
    if store is None:
        logger.error("No layer name for '%s'", prod)
        return
    if file_in_granules(cat, workspace, store, fname,
                        identity_check_seconds, file_pattern):
        return
    if filesystem == "posix":
        # Write WKT to file if configured
        write_wkt(config, fname)
        # Add the granule metadata to Geoserver
        georest.add_granule(cat, config["workspace"], store, fname)
    elif filesystem == "s3":
        meta = {
            'host': config['host'],
            'workspace': workspace,
            'layer_name': store,
            'prototype_image': fname,
        }
        georest.add_s3_granule(config, meta)
    else:
        raise NotImplementedError("Can't add granules to filesystem '%s'" % filesystem)
