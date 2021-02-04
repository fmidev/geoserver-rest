#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author(s):
#
#     Panu Lahtinen <panu.lahtinen@fmi.fi>

"""Unittests for Geoserver REST API utility functions."""


from unittest import mock


def test_read_config():
    """Test reading a config file."""
    from georest.utils import read_config
    import tempfile
    import os

    config = """foo: bar"""
    with tempfile.TemporaryDirectory() as tempdir:
        config_file = os.path.join(tempdir, "config.yaml")
        with open(config_file, "w") as fid:
            fid.write(config)
        res = read_config(config_file)
        assert res["foo"] == "bar"


def test_write_wkt():
    """Test that WKT files are written."""
    from georest.utils import write_wkt
    import tempfile
    import os

    config = {"write_wkt": "mock WKT string"}
    with tempfile.TemporaryDirectory() as tempdir:
        tif_fname = os.path.join(tempdir, "image.tif")
        write_wkt(config, tif_fname)
        prj_fname = os.path.join(tempdir, "image.prj")
        assert os.path.exists(prj_fname)


def test_write_wkt_for_files():
    """Test writing WKT files for existing files."""
    from georest.utils import write_wkt_for_files
    import tempfile
    import os
    import glob

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


@mock.patch("georest.utils.convert_file_path")
@mock.patch("georest.add_granule")
@mock.patch("georest.utils.write_wkt")
@mock.patch("georest.connect_to_gs_catalog")
def test_run_posttroll_adder(connect_to_gs_catalog, write_wkt, add_granule,
                             convert_file_path):
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

    run_posttroll_adder(config, Subscribe)
    write_wkt.assert_not_called()
    add_granule.assert_not_called()

    # Add "airmass" layer to config
    config["layers"]["airmass"] = "airmass_layer_name"
    Subscribe.return_value.__enter__.return_value.recv.return_value = [None, msg]

    run_posttroll_adder(config, Subscribe)
    write_wkt.assert_called_once()
    add_granule.assert_called_once()
