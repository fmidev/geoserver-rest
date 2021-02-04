#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Unittests for Geoserver REST methods."""

from unittest import mock


@mock.patch("georest.Catalog")
def test_connect_to_gs_catalog(Catalog):
    """Test connecting Geoserver catalog."""
    from georest import connect_to_gs_catalog

    config = {"host": "foo", "user": "user", "passwd": "passwd"}
    _ = connect_to_gs_catalog(config)

    Catalog.assert_called_with(config["host"], config["user"], config["passwd"])


def test_create_workspace():
    """Test creating a workspace."""
    from georest import create_workspace

    cat = mock.MagicMock()
    workspace = "workspace"

    create_workspace(workspace, cat)
    cat.get_workspace.assert_called_with(workspace)
    cat.create_workspace.assert_not_called()

    cat.get_workspace.return_value = None

    create_workspace(workspace, cat)
    cat.create_workspace.assert_called_with(workspace, workspace)


def test_collect_layer_metadata():
    """Test collecting metadata."""
    from georest import _collect_layer_metadata

    config = {}
    layer_config = {"bar": "bar2", "baz": "baz", "title_pattern": "title_pattern"}

    meta = _collect_layer_metadata(config, layer_config)
    assert meta["bar"] == layer_config["bar"]
    assert meta["baz"] == layer_config["baz"]
    assert meta["title"] == layer_config["title_pattern"]

    config = {"common_items": {"foo": "foo", "bar": "bar1", "baz": "baz", "title": "title"}}
    layer_config = {"bar": "bar2", "title_pattern": "title_pattern"}
    meta = _collect_layer_metadata(config, layer_config)
    assert meta["foo"] == config["common_items"]["foo"]
    assert meta["baz"] == config["common_items"]["baz"]
    assert meta["title"] == config["common_items"]["title"]


def _create_extra_files(tempdir, files):
    """Create some empty files."""
    import os

    out_files = []
    for fname in files:
        fname = os.path.join(tempdir, fname)
        with open(fname, "w") as fid:
            fid.write("")
        out_files.append(fname)

    return out_files


@mock.patch("georest.delete_granule")
@mock.patch("georest.DimensionInfo")
@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers(connect_to_gs_catalog, DimensionInfo, delete_granule):
    """Test creating layers."""
    from georest import create_layers
    import tempfile
    from geoserver.catalog import FailedRequestError

    cat = mock.MagicMock()
    connect_to_gs_catalog.return_value = cat

    config = {"workspace": "workspace",
              "properties": {"foo": {"bar": "baz"}},
              "time_dimension": {"name": "name",
                                 "enabled": "enabled",
                                 "presentation": "presentation",
                                 "resolution": "resolution",
                                 "units": "units",
                                 "nearestMatchEnabled": "nearestMatchEnabled"},
              "layers": [{"name": "colorized_ir_clouds",
                          "title": "Title text",
                          "abstract": "Abstract",
                          "keywords": ["kw1", "kw2"]},
                         ]
              }

    # The layers exist
    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.get_workspace.assert_called_with(config["workspace"])
    cat.get_store.assert_called_with(config["layers"][0]["name"],
                                     workspace=config["workspace"])
    cat.get_resource.assert_called_with(store=config["layers"][0]["name"],
                                        workspace=config["workspace"])
    cat.save.assert_called_once()

    # Layer exists, see that layer name is composed from a pattern
    cat.reset_mock()

    config["common_items"] = {"area_name": "europe",
                              "layer_pattern": "{area_name}_{product_name}"}
    config["layers"].append({"product_name": "layer2_name",
                             "title": "Title for layer2"})

    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.get_store.assert_called_with("europe_layer2_name",
                                     workspace=config["workspace"])
    cat.get_resource.assert_called_with(store="europe_layer2_name",
                                        workspace=config["workspace"])
    assert cat.save.call_count == 2

    # The layer doesn't exist, so create it
    cat.reset_mock()
    cat.get_store.return_value = None

    with tempfile.TemporaryDirectory() as tempdir:
        # Write extra file(s)
        files = ["file1.tif", "file2.tif"]
        files = _create_extra_files(tempdir, files)
        config["properties"]["files"] = files
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.create_imagemosaic.assert_called()
    # delete_granule() will be called once per file for each layer -> 2 x 2 = 4 calls
    assert delete_granule.call_count == 4

    # The layer doesn't exist, but creation fails
    cat.reset_mock()
    # We don't need the files anymore
    del config["properties"]["files"]
    cat.create_imagemosaic.side_effect = FailedRequestError

    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.create_imagemosaic.assert_called()


def test_get_layer_coverage():
    """Test retrieving layer coverage."""
    from georest import get_layer_coverage

    # This is the structure returned by cat.mosaic_coverages()
    coverages = {"coverages":
                 {"coverage": [{"name": "name1"},
                               {"name": "name2"}]
                  }
                 }
    cat = mock.MagicMock()
    cat.mosaic_coverages.return_value = coverages
    store_obj = mock.MagicMock()

    # Store does not exist
    res = get_layer_coverage(cat, "foo", store_obj)
    assert res is None

    res = get_layer_coverage(cat, "name2", store_obj)
    assert res == coverages["coverages"]["coverage"][1]


@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.connect_to_gs_catalog")
def test_add_file_to_mosaic(connect_to_gs_catalog, file_in_granules):
    """Test adding files to image mosaic."""
    from georest import add_file_to_mosaic
    from geoserver.catalog import FailedRequestError

    add_granule = mock.MagicMock()
    cat = mock.MagicMock(add_granule=add_granule)
    connect_to_gs_catalog.return_value = cat

    config = {"workspace": "satellite",
              "geoserver_target_dir": "/mnt/data",
              "file_pattern": "{area}_{productname}.tif",
              "layer_id": "productname",
              "layers": {"airmass": "airmass_store"},
              }
    fname_in = "/path/to/europe_airmass.tif"

    # The file is already added, should not re-add it
    file_in_granules.return_value = True
    add_file_to_mosaic(config, fname_in)
    add_granule.assert_not_called()

    # A new file
    file_in_granules.return_value = False
    add_file_to_mosaic(config, fname_in)

    connect_to_gs_catalog.assert_called_with(config)
    add_granule.assert_called_with("/mnt/data/europe_airmass.tif",
                                   "airmass_store", "satellite")
    add_file_to_mosaic(config, fname_in)

    # Check that failed request is handled
    add_granule.side_effect = FailedRequestError
    add_file_to_mosaic(config, fname_in)


@mock.patch("georest.connect_to_gs_catalog")
def test_delete_file_from_mosaic(connect_to_gs_catalog):
    """Test deleting files from image mosaic."""
    from georest import delete_file_from_mosaic

    # This is the structure returned by cat.mosaic_coverages()
    coverages = {"coverages":
                 {"coverage": [{"name": "airmass_store"},
                               ]
                  }
                 }
    cat = mock.MagicMock()
    cat.mosaic_coverages.return_value = coverages
    connect_to_gs_catalog.return_value = cat

    config = {"workspace": "satellite",
              "geoserver_target_dir": "/mnt/data",
              "file_pattern": "{area}_{productname}.tif",
              "layer_id": "productname",
              "layers": {"airmass": "airmass_store"}}
    fname = "europe_airmass.tif"

    delete_file_from_mosaic(config, fname)

    connect_to_gs_catalog.assert_called_with(config)
    cat.get_store.assert_called_with("airmass_store", "satellite")
    cat.list_granules.assert_called()
    cat.delete_granule.assert_not_called()

    # This is the structure returned by cat.list_granules()
    granules = {"features":
                [{"properties": {"location": "/mnt/data/europe_airmass.tif"},
                  "id": "file-id"}]
                }
    cat.list_granules.return_value = granules

    delete_file_from_mosaic(config, fname)
    cat.delete_granule.assert_called()
