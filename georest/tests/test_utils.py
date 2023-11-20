#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Unittests for Geoserver REST API utility functions."""


from unittest import mock

import pytest


def test_read_config():
    """Test reading a config file."""
    import os
    import tempfile

    from georest.utils import read_config

    config = """
        foo: bar
        user: user1
        passwd: passwd1
    """
    with tempfile.TemporaryDirectory() as tempdir:
        config_file = os.path.join(tempdir, "config.yaml")
        with open(config_file, "w") as fid:
            fid.write(config)
        res = read_config(config_file)
        assert res["foo"] == "bar"
        assert res["user"] == "user1"
        assert res["passwd"] == "passwd1"


def test_read_config_credentials_in_env():
    """Test reading a config file when user/passwd are given in environment variables."""
    import os
    import tempfile

    from georest.utils import read_config

    os.environ["GEOSERVER_USER"] = "user1"
    os.environ["GEOSERVER_PASSWORD"] = "passwd1"
    config = """
        foo: bar
    """
    with tempfile.TemporaryDirectory() as tempdir:
        config_file = os.path.join(tempdir, "config.yaml")
        with open(config_file, "w") as fid:
            fid.write(config)
        res = read_config(config_file)
        assert res["foo"] == "bar"
        assert res["user"] == "user1"
        assert res["passwd"] == "passwd1"


def test_read_config_default_credentials():
    """Test reading a config file when user/passwd are not given."""
    import os
    import tempfile

    from georest.utils import read_config

    os.environ.pop("GEOSERVER_USER", None)
    os.environ.pop("GEOSERVER_PASSWORD", None)

    config = """
        foo: bar
    """
    with tempfile.TemporaryDirectory() as tempdir:
        config_file = os.path.join(tempdir, "config.yaml")
        with open(config_file, "w") as fid:
            fid.write(config)
        res = read_config(config_file)
        assert res["foo"] == "bar"
        assert res["user"] == "admin"
        assert res["passwd"] == "geoserver"


def test_write_wkt():
    """Test that WKT files are written."""
    import os
    import tempfile

    from georest.utils import write_wkt

    config = {"write_wkt": "mock WKT string"}
    with tempfile.TemporaryDirectory() as tempdir:
        config["exposed_target_dir"] = tempdir
        tif_fname = os.path.join(tempdir, "image.tif")
        write_wkt(config, tif_fname)
        prj_fname = os.path.join(tempdir, "image.prj")
        assert os.path.exists(prj_fname)


def test_write_wkt_for_files():
    """Test writing WKT files for existing files."""
    import glob
    import os
    import tempfile

    from georest.utils import write_wkt_for_files

    config = {"write_wkt": "mock WKT string"}

    with tempfile.TemporaryDirectory() as tempdir:
        tif_fname = os.path.join(tempdir, "image.tif")
        with open(tif_fname, "w") as fid:
            fid.write("image")
        write_wkt_for_files(config, tempdir)
        files = glob.glob(os.path.join(tempdir, "image.*"))
        assert len(files) == 2
        assert os.path.join(tempdir, "image.prj") in files
        # .prj files and directories should be ignored
        os.mkdir(os.path.join(tempdir, "image"))
        write_wkt_for_files(config, tempdir)
        files = glob.glob(os.path.join(tempdir, "image.*"))
        assert len(files) == 2


@mock.patch("georest.utils.georest")
def test_file_in_granules(georest):
    """Test that existing files are recogniced in the store."""
    from georest.utils import file_in_granules

    cat = mock.MagicMock()
    workspace = "satellite"
    store = "airmass"
    file_path = "/path/to/20200818_1200_europe_airmass.tif"
    file_pattern = "{start_time:%Y%m%d_%H%M}_{area}_{product}.tif"
    identity_check_seconds = None

    # Do not test if identity_check_seconds is None
    assert not file_in_granules(
        cat, workspace, store, file_path, identity_check_seconds, file_pattern)
    cat.get_store.assert_not_called()
    georest.get_layer_coverage.assert_not_called()
    georest.get_layer_granules.assert_not_called()

    # Image not in layer -> returns False
    identity_check_seconds = 60
    granules = {"features":
                [{"properties": {"location": "/mnt/data/20200818_1100_europe_airmass.tif"},
                  "id": "file-id"}]
                }
    georest.get_layer_granules.return_value = granules
    assert not file_in_granules(
        cat, workspace, store, file_path, identity_check_seconds, file_pattern)

    # Exact image in layer -> returns True
    identity_check_seconds = 60
    granules = {"features":
                [{"properties": {"location": "/mnt/data/20200818_1200_europe_airmass.tif"},
                  "id": "file-id"}]
                }
    georest.get_layer_granules.return_value = granules
    assert file_in_granules(
        cat, workspace, store, file_path, identity_check_seconds, file_pattern)

    # Image time within tolerance in layer -> returns True
    identity_check_seconds = 60
    granules = {"features":
                [{"properties": {"location": "/mnt/data/20200818_1201_europe_airmass.tif"},
                  "id": "file-id"}]
                }
    georest.get_layer_granules.return_value = granules
    assert file_in_granules(
        cat, workspace, store, file_path, identity_check_seconds, file_pattern)

    # Only product differs
    identity_check_seconds = 60
    granules = {"features":
                [{"properties": {"location": "/mnt/data/20200818_1200_europe_ash.tif"},
                  "id": "file-id"}]
                }
    georest.get_layer_granules.return_value = granules
    assert not file_in_granules(
        cat, workspace, store, file_path, identity_check_seconds, file_pattern)

    # Filepattern and filename do not match
    file_path = "/path/to/20200818_1200_europe_airmass.l1b"
    with pytest.raises(ValueError):
        file_in_granules(cat, workspace, store, file_path, identity_check_seconds, file_pattern)


@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.utils.convert_file_path")
@mock.patch("georest.add_granule")
@mock.patch("georest.utils.write_wkt")
@mock.patch("georest.connect_to_gs_catalog")
def test_run_posttroll_adder(connect_to_gs_catalog, write_wkt, add_granule,
                             convert_file_path, file_in_granules):
    """Test running posttroll adder."""
    from georest.utils import run_posttroll_adder

    # No "airmass" layer configured
    config = {"workspace": "satellite",
              "topics": ["/topic1", "/topic2"],
              "layers": {},
              }
    convert_file_path.return_value = "/mnt/data/image.tif"
    msg = mock.MagicMock(data={"productname": "airmass", "uri": "/path/to/image.tif"})
    Subscribe = mock.MagicMock()
    Subscribe.return_value.__enter__.return_value.recv.return_value = [None, msg]
    file_in_granules.return_value = False

    # Test with missing layers
    run_posttroll_adder(config, Subscribe)
    write_wkt.assert_not_called()
    add_granule.assert_not_called()
    file_in_granules.assert_not_called()

    # Add "airmass" layer to config
    config["layers"]["airmass"] = "airmass_layer_name"
    run_posttroll_adder(config, Subscribe)
    write_wkt.assert_called_once()
    add_granule.assert_called_once()
    file_in_granules.assert_called_once_with(
        connect_to_gs_catalog.return_value,
        config["workspace"],
        config["layers"]["airmass"],
        convert_file_path.return_value,
        None,  # No "identity_check_seconds" set
        None)  # No "file_pattern" in config

    # Set "identity_check_seconds" and "file_pattern" to config
    config["identity_check_seconds"] = 60
    config["file_pattern"] = "{base_filename}.{format}"
    run_posttroll_adder(config, Subscribe)
    file_in_granules.assert_called_with(
        connect_to_gs_catalog.return_value,
        config["workspace"],
        config["layers"]["airmass"],
        convert_file_path.return_value,
        config["identity_check_seconds"],
        config["file_pattern"])


@mock.patch("georest.utils._process_message")
@mock.patch("georest.connect_to_gs_catalog")
def test_posttroll_adder_loop_return_value(connect_to_gs_catalog, process_message):
    """Test running posttroll adder."""
    from georest.utils import _posttroll_adder_loop

    config = {"workspace": "satellite",
              "topics": ["/topic1", "/topic2"],
              "layers": {"airmass": "airmass_layer_name"},
              }
    msg = mock.MagicMock(data={"productname": "airmass", "uri": "/path/to/image.tif"})
    Subscribe = mock.MagicMock()
    Subscribe.return_value.__enter__.return_value.recv.return_value = [msg]

    # Timeout occurs
    restart_timeout = -1.0
    res = _posttroll_adder_loop(config, Subscribe, restart_timeout)
    assert res is False

    # Unhandled exception
    process_message.side_effect = IOError
    res = _posttroll_adder_loop(config, Subscribe, None)
    assert res is False

    # KeyboardInterrupt is the only that should return True
    process_message.side_effect = KeyboardInterrupt
    res = _posttroll_adder_loop(config, Subscribe, None)
    assert res is True


@mock.patch("georest.utils._process_message")
@mock.patch("georest.connect_to_gs_catalog")
def test_posttroll_adder_loop_subscribe_config_options(connect_to_gs_catalog, process_message):
    """Test that the Subscriber options are read from config."""
    from georest.utils import _posttroll_adder_loop

    msg = mock.MagicMock(data={"productname": "airmass", "uri": "/path/to/image.tif"})
    Subscribe = mock.MagicMock()
    Subscribe.return_value.__enter__.return_value.recv.return_value = [msg]

    # Check that the config has been accessed for required info
    config = mock.MagicMock()
    _posttroll_adder_loop(config, Subscribe, None)
    assert mock.call('services', '') in config.get.mock_calls
    assert mock.call('nameserver', 'localhost') in config.get.mock_calls
    assert mock.call('addresses') in config.get.mock_calls
    assert mock.call('use_address_listener', True) in config.get.mock_calls


@mock.patch("georest.utils.file_in_granules")
@mock.patch("georest.utils.convert_file_path")
@mock.patch("georest.add_s3_granule")
@mock.patch("georest.connect_to_gs_catalog")
def test_run_posttroll_adder_s3(connect_to_gs_catalog, add_s3_granule,
                                convert_file_path, file_in_granules):
    """Test running posttroll adder."""
    from georest.utils import run_posttroll_adder

    # No "airmass" layer configured
    config = {"workspace": "satellite",
              "topics": ["/topic1", "/topic2"],
              "layers": {"airmass": "airmass_layer_name"},
              "filesystem": "s3",
              "host": "hostname",
              }
    convert_file_path.return_value = "/mnt/data/image.tif"
    msg = mock.MagicMock(data={"productname": "airmass", "uri": "/path/to/image.tif"})
    Subscribe = mock.MagicMock()
    Subscribe.return_value.__enter__.return_value.recv.return_value = [None, msg]
    file_in_granules.return_value = False

    run_posttroll_adder(config, Subscribe)
    add_s3_granule.assert_called_once()
    # The store is added to the config
    config["store"] = config["layers"]["airmass"]
    expected_meta = {
        'host': 'hostname',
        'workspace': 'satellite',
        'layer_name': 'airmass_layer_name',
        'image_url': '/mnt/data/image.tif'}
    add_s3_granule.assert_called_once_with(
        config,
        expected_meta
    )


def test_convert_file_path():
    """Test the file path conversion for the default case."""
    from georest.utils import convert_file_path

    config = {"geoserver_target_dir": "/geoserver/internal/path/"}
    res = convert_file_path(config, "/external/path/file.tif")

    assert res == "/geoserver/internal/path/file.tif"


def test_convert_file_path_inverse():
    """Test the file path conversion for the inverse case."""
    from georest.utils import convert_file_path

    config = {"exposed_base_dir": "/external/path/"}
    res = convert_file_path(config, "/geoserver/internal/path/file.tif", inverse=True)

    assert res == "/external/path/file.tif"


def test_convert_file_path_keep_subpath():
    """Test the file path conversion when keeping the subpath of the file."""
    from georest.utils import convert_file_path

    config = {"geoserver_target_dir": "/geoserver/internal/path/"}
    res = convert_file_path(config, "subpath/file.tif", keep_subpath=True)

    assert res == "/geoserver/internal/path/subpath/file.tif"


def test_convert_file_path_keep_subpath_inverse():
    """Test the file path conversion when keeping the subpath of the file for the inverse case."""
    from georest.utils import convert_file_path

    config = {"exposed_base_dir": "/external/path/",
              "geoserver_target_dir": "/geoserver/internal/path/"}
    res = convert_file_path(config, "/geoserver/internal/path/subpath/file.tif", inverse=True, keep_subpath=True)

    assert res == "/external/path/subpath/file.tif"


def test_get_layers_for_delete_granules():
    """Test the function that provides layer names for delete granules."""
    from georest.utils import get_layers_for_delete_granules

    # Case 1: layer_id and layers provided
    config = {"layer_id": "layer_id", "layers": {"layer_1": "layer_name_1", "layer_2": "layer_name_2"}}
    res = get_layers_for_delete_granules(config)

    assert res == ["layer_name_1", "layer_name_2"]

    # Case 2: layer_name_template and delete_granule_layer_options provided
    config = {
        "layer_name_template": "{opt1}_{opt2}",
        "delete_granule_layer_options": {"opt1": ["option1_1", "option1_2"], "opt2": ["layer_name_2"]},
    }
    res = get_layers_for_delete_granules(config)

    assert res == ["option1_1_layer_name_2", "option1_2_layer_name_2"]

    # Case 3: no layer_id or layer_name_template provided
    config = {}
    with pytest.raises(ValueError):
        get_layers_for_delete_granules(config)
