#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Unittests for Geoserver REST methods."""

from copy import deepcopy
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


def test_collect_layer_metadata_no_common_items():
    """Test collecting metadata."""
    from georest import _collect_layer_metadata

    config = {"host": "hostname", "workspace": "workspace"}
    layer_config = {"bar": "bar2", "baz": "baz", "title_pattern": "title_pattern", "cache_age_max": 86400,
                    "layer_pattern": "layer_pattern"}

    meta = _collect_layer_metadata(config, layer_config)
    assert meta["bar"] == layer_config["bar"]
    assert meta["baz"] == layer_config["baz"]
    assert meta["title"] == layer_config["title_pattern"]
    assert meta["cache_age_max"] == 86400


def test_collect_layer_metadata_with_common_items():
    """Test collecting metadata."""
    from georest import _collect_layer_metadata

    config = {"host": "hostname", "workspace": "workspace",
              "common_items": {"foo": "foo", "bar": "bar1", "baz": "baz", "title": "title",
                               "cache_age_max": 86400, "layer_pattern": "layer_pattern"}}
    layer_config = {"bar": "bar2", "title_pattern": "title_pattern"}
    meta = _collect_layer_metadata(config, layer_config)
    assert meta["foo"] == config["common_items"]["foo"]
    assert meta["baz"] == config["common_items"]["baz"]
    assert meta["title"] == config["common_items"]["title"]
    assert meta["cache_age_max"] == config["common_items"]["cache_age_max"]


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


CREATE_LAYERS_CONFIG = {
    "host": "host",
    "workspace": "workspace",
    "common_items": {"cache_age_max": 86400, "projection_policy": "FORCE_DECLARED"},
    "properties": {"foo": {"bar": "baz"}},
    "dimensions": {
        "time_dimension": {
            "name": "name",
            "enabled": "enabled",
            "presentation": "presentation",
            "resolution": "resolution",
            "units": "units",
            "nearestMatchEnabled": "nearestMatchEnabled",
        },
    },
    "layers": [
        {"name": "colorized_ir_clouds", "title": "Title text", "abstract": "Abstract", "keywords": ["kw1", "kw2"]},
    ],
}

CREATE_LAYERS_WITH_STYLE_CONFIG = deepcopy(CREATE_LAYERS_CONFIG)
CREATE_LAYERS_WITH_STYLE_CONFIG["style"] = {
    "default_style": {"name": "style", "workspace": "workspace"},
    "additional_styles": [{"name": "additional_style1", "workspace": "workspace"}, {"name": "additional_style2", "workspace": "workspace"}],
}


@mock.patch("georest.DimensionInfo")
@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers(connect_to_gs_catalog, DimensionInfo):
    """Test creating layers when they already exist."""
    import tempfile

    from georest import create_layers

    config = deepcopy(CREATE_LAYERS_CONFIG)
    cat = mock.MagicMock()
    coverage = mock.MagicMock()
    cat.get_resource.return_value = coverage

    connect_to_gs_catalog.return_value = cat

    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.get_workspace.assert_called_with(config["workspace"])
    cat.get_store.assert_called_with(config["layers"][0]["name"],
                                     workspace=config["workspace"])
    cat.get_resource.assert_called_with(store=config["layers"][0]["name"],
                                        workspace=config["workspace"])
    cat.save.assert_called_once()
    assert "'cacheAgeMax', '86400'" in str(coverage.mock_calls)
    assert "'cachingEnabled', 'true'" in str(coverage.mock_calls)
    assert "'ProjectionPolicy', 'FORCE_DECLARED'" in str(coverage.mock_calls)


@mock.patch("georest.DimensionInfo")
@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers_already_exist(connect_to_gs_catalog, DimensionInfo):
    """Test creating layers when they already exist."""
    import tempfile

    from georest import create_layers

    config = deepcopy(CREATE_LAYERS_CONFIG)
    cat = mock.MagicMock()
    coverage = mock.MagicMock()
    cat.get_resource.return_value = coverage

    connect_to_gs_catalog.return_value = cat

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


@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers_with_style(connect_to_gs_catalog):
    """Test creating layers when they already exist."""
    import tempfile

    from georest import create_layers

    config = deepcopy(CREATE_LAYERS_WITH_STYLE_CONFIG)
    cat = mock.MagicMock()
    coverage = mock.MagicMock()
    cat.get_resource.return_value = coverage

    connect_to_gs_catalog.return_value = cat

    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    assert "call.get_style('style', workspace='workspace')" in str(cat.mock_calls)
    assert "call.get_style('additional_style1', workspace='workspace')" in str(cat.mock_calls)
    assert "call.get_style('additional_style1', workspace='workspace')" in str(cat.mock_calls)
    assert "_set_default_style" in str(cat.mock_calls)
    assert "_set_alternate_styles" in str(cat.mock_calls)


@mock.patch("georest.delete_granule")
@mock.patch("georest.DimensionInfo")
@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers_layer_with_extra_files(connect_to_gs_catalog, DimensionInfo, delete_granule):
    """Test creating layers when they already exist."""
    import tempfile

    from georest import create_layers

    config = deepcopy(CREATE_LAYERS_CONFIG)
    cat = mock.MagicMock()
    coverage = mock.MagicMock()
    cat.get_resource.return_value = coverage

    connect_to_gs_catalog.return_value = cat

    cat.get_store.return_value = None

    with tempfile.TemporaryDirectory() as tempdir:
        # Write extra file(s)
        files = ["file1.tif", "file2.tif"]
        files = _create_extra_files(tempdir, files)
        config["properties"]["files"] = files
        config["exposed_base_dir"] = tempdir
        create_layers(config.copy())

    cat.create_imagemosaic.assert_called()
    # delete_granule() will be called once per file for each layer
    assert delete_granule.call_count == 2


@mock.patch("georest.DimensionInfo")
@mock.patch("georest.connect_to_gs_catalog")
def test_create_layers_creation_fails(connect_to_gs_catalog, DimensionInfo):
    """Test creating layers when they already exist."""
    import tempfile

    from geoserver.catalog import FailedRequestError

    from georest import create_layers

    config = deepcopy(CREATE_LAYERS_CONFIG)
    cat = mock.MagicMock()
    coverage = mock.MagicMock()
    cat.get_resource.return_value = coverage
    cat.get_store.return_value = None

    connect_to_gs_catalog.return_value = cat
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


ADD_FILE_TO_MOSAIC_CONFIG = {
    "host": "http://host/",
    "user": "user",
    "passwd": "passwd",
    "workspace": "satellite",
    "geoserver_target_dir": "/mnt/data",
    "keep_subpath": False,
    "file_pattern": "{area}_{productname}.tif",
    "layer_id": "productname",
    "layers": {"airmass": "airmass_store"},
}


@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.connect_to_gs_catalog")
def test_add_file_to_mosaic(connect_to_gs_catalog, file_in_granules):
    """Test adding files to image mosaic."""
    from georest import add_file_to_mosaic

    config = deepcopy(ADD_FILE_TO_MOSAIC_CONFIG)

    # Returns False if the file isn't in database
    file_in_granules.return_value = False
    add_granule = mock.MagicMock()
    cat = mock.MagicMock(add_granule=add_granule)
    connect_to_gs_catalog.return_value = cat

    fname_in = "/path/to/europe_airmass.tif"

    add_file_to_mosaic(config, fname_in)

    connect_to_gs_catalog.assert_called_with(config)
    add_granule.assert_called_with("/mnt/data/europe_airmass.tif",
                                   "airmass_store", "satellite")
    add_file_to_mosaic(config, fname_in)


@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.connect_to_gs_catalog")
def test_add_file_to_mosaic_existing_file(connect_to_gs_catalog, file_in_granules):
    """Test adding an exisgint file to image mosaic."""
    from georest import add_file_to_mosaic

    config = deepcopy(ADD_FILE_TO_MOSAIC_CONFIG)

    add_granule = mock.MagicMock()
    cat = mock.MagicMock(add_granule=add_granule)
    connect_to_gs_catalog.return_value = cat

    fname_in = "/path/to/europe_airmass.tif"

    # The file is already added, should not re-add it
    file_in_granules.return_value = True
    add_file_to_mosaic(config, fname_in)
    add_granule.assert_not_called()


@mock.patch("georest.connect_to_gs_catalog")
def test_add_file_to_mosaic_failed_request(connect_to_gs_catalog):
    """Test that a failed file addition is handled."""
    from geoserver.catalog import FailedRequestError

    from georest import add_file_to_mosaic

    config = deepcopy(ADD_FILE_TO_MOSAIC_CONFIG)

    add_granule = mock.MagicMock()
    cat = mock.MagicMock(add_granule=add_granule)
    connect_to_gs_catalog.return_value = cat

    fname_in = "/path/to/europe_airmass.tif"

    # Check that failed request is handled
    add_granule.side_effect = FailedRequestError
    add_file_to_mosaic(config, fname_in)


@mock.patch("georest.requests")
@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.connect_to_gs_catalog")
def test_add_file_to_mosaic_s3(connect_to_gs_catalog, file_in_granules, requests):
    """Test adding a file to image mosaic when data are in S3 object storage."""
    from georest import add_file_to_mosaic

    config = deepcopy(ADD_FILE_TO_MOSAIC_CONFIG)

    # Returns False if the file isn't in database
    file_in_granules.return_value = False
    add_granule = mock.MagicMock()
    cat = mock.MagicMock(add_granule=add_granule)
    connect_to_gs_catalog.return_value = cat

    fname_in = "https://bucket.host/europe_airmass.tif"

    add_file_to_mosaic(config, fname_in, filesystem='s3')

    call = requests.mock_calls[0]
    assert call.args[0] == "http://host/workspaces/satellite/coveragestores/airmass_store/remote.imagemosaic"
    expected = {'data': '/mnt/data/europe_airmass.tif',
                'headers': {'Content-type': 'text/plain'},
                'auth': ('user', 'passwd')}
    assert call.kwargs == expected


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


@mock.patch("georest.requests")
def test_create_s3_layers(requests):
    """Test creating layers from S3 data."""
    from georest import create_s3_layers

    config = {
        "host": "http://host/",
        "user": "user",
        "passwd": "passwd",
        "workspace": "workspace",
        "common_items": {
            "layer_pattern": "layer_pattern",
            "title_pattern": "title_pattern",
        },
        "coverage_template": "coverage_template",
        "properties": {
            "property1": {"prop1": "prop1"},
            "property2": {"prop2": "prop2"},

        },
        "layers": [
            {
                "product_name": "product_name",
                "product_title": "product_title",
                "image_url": "https://bucket.host/image.tif",
                "abstract": "abstract",
            }
        ]
        }

    create_s3_layers(config)

    first_call = requests.mock_calls[0]
    url = 'http://host/workspaces/workspace/coveragestores/layer_pattern/file.imagemosaic?configure=none'
    assert first_call.args[0] == url
    assert 'data' in first_call.kwargs
    assert first_call.kwargs["headers"] == {'Content-type': 'application/zip'}
    assert first_call.kwargs["auth"] == ('user', 'passwd')
    second_call = requests.mock_calls[1]
    url = 'http://host/workspaces/workspace/coveragestores/layer_pattern/remote.imagemosaic'
    assert second_call.args[0] == url
    expected = {'data': 'https://bucket.host/image.tif',
                'headers': {'Content-type': 'text/plain'},
                'auth': ('user', 'passwd')}
    assert second_call.kwargs == expected
    # The next two calls are checking the request status, skip those
    last_call = requests.mock_calls[-1]
    url = 'http://host/workspaces/workspace/coveragestores/layer_pattern/coverages'
    assert last_call.args[0] == url
    expected = {'data': 'coverage_template',
                'headers': {'Content-type': 'text/xml'},
                'auth': ('user', 'passwd')}
    assert last_call.kwargs == expected
